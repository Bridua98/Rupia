"""Comandas: abrir, cargar, enviar a cocina o barra, anular y pedir la cuenta.

Las vistas exigen los permisos; acá se cuidan las reglas del negocio.
"""

from collections import OrderedDict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from inventario.models import TipoItem
from inventario.stock import stock_actual
from inventario.unidades import convertir_a_base, redondear_cantidad
from mesas.models import (
    ESTADOS_ACTIVOS,
    Comanda,
    ComandaAnulacion,
    ComandaDetalle,
    EnvioSector,
    EnvioSectorLinea,
    EstadoComanda,
    Mesa,
    Ronda,
    TipoEnvio,
)
from mesas.ruteo import sector_de
from ventas.cobro import precio_en_unidad

CERO = Decimal("0")
UNO = Decimal("1")


@dataclass
class Carga:
    detalle: ComandaDetalle
    aviso: str = ""


# --- Consultas ---------------------------------------------------------------


def comandas_activas():
    return Comanda.objects.filter(estado__in=ESTADOS_ACTIVOS)


def comanda_de_mesa(mesa):
    return comandas_activas().filter(mesa=mesa).first()


def lineas_vigentes(comanda):
    return comanda.detalles.filter(anulado=False)


def total(comanda) -> Decimal:
    return sum(
        (detalle.precio * detalle.cantidad for detalle in lineas_vigentes(comanda)),
        CERO,
    )


def tiene_pendientes(comanda) -> bool:
    return lineas_vigentes(comanda).filter(ronda__isnull=True).exists()


def tiene_enviados(comanda) -> bool:
    return lineas_vigentes(comanda).filter(ronda__isnull=False).exists()


# --- Abrir -------------------------------------------------------------------


def abrir(*, usuario, mesa=None, nombre="", cliente=None, personas=None) -> Comanda:
    nombre = (nombre or "").strip()
    if mesa is None and not nombre and cliente is None:
        raise ValidationError(
            "Elegí una mesa o escribí a nombre de quién va la cuenta.", code="sin_destino"
        )
    if personas is not None and personas < 1:
        raise ValidationError("La cantidad de personas tiene que ser al menos 1.", code="personas")
    with transaction.atomic():
        if mesa is not None:
            # Bloquear la mesa: dos mozos no pueden abrirla a la vez.
            mesa = Mesa.objects.select_for_update().get(pk=mesa.pk)
            if not mesa.activa:
                raise ValidationError("Esa mesa no está activa.", code="mesa_inactiva")
            if comanda_de_mesa(mesa):
                raise ValidationError(
                    f"La mesa {mesa.nombre} ya está ocupada.", code="mesa_ocupada"
                )
        return Comanda.objects.create(
            mesa=mesa,
            nombre=nombre,
            cliente=cliente,
            personas=personas,
            mozo=usuario,
            estado=EstadoComanda.ABIERTA,
            abierta_en=timezone.now(),
        )


def _bloquear(comanda) -> Comanda:
    comanda = Comanda.objects.select_for_update().get(pk=comanda.pk)
    if not comanda.activa:
        raise ValidationError("Esa cuenta ya está cerrada.", code="cerrada")
    return comanda


def _reabrir_si_pidio_cuenta(comanda):
    if comanda.estado == EstadoComanda.CUENTA_PEDIDA:
        comanda.estado = EstadoComanda.ABIERTA
        comanda.save(update_fields=["estado"])


# --- Cargar ------------------------------------------------------------------


def _validar_item(item):
    # Las mismas reglas que el punto de venta: si no, después no se podría cobrar.
    if item.tipo != TipoItem.PRODUCTO or not item.activo:
        raise ValidationError("Ese producto no está a la venta.", code="item")
    if item.precio is None:
        raise ValidationError("Ese producto no tiene precio.", code="sin_precio")


def _interpretar_cantidad(valor) -> Decimal:
    try:
        cantidad = Decimal(str(valor).replace(",", ".").strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError("Escribí la cantidad en números.", code="cantidad") from exc
    return redondear_cantidad(cantidad)


def aviso_stock(item, unidad, cantidad_extra=CERO) -> str:
    """Avisa si lo cargado en cuentas abiertas supera el stock. No bloquea."""
    stock, _omitidos = stock_actual(item)
    comprometido = CERO
    for detalle in ComandaDetalle.objects.filter(
        item=item,
        anulado=False,
        comanda__estado__in=ESTADOS_ACTIVOS,
    ).select_related("unidad_medida"):
        try:
            comprometido += convertir_a_base(item, detalle.unidad_medida, detalle.cantidad)
        except ValidationError:
            continue
    if cantidad_extra:
        comprometido += convertir_a_base(item, unidad, cantidad_extra)
    if comprometido > stock:
        return f"Ojo: no hay stock suficiente de {item.descripcion}. Se cargó igual."
    return ""


def agregar(comanda, item, *, usuario, cantidad=UNO, nota="") -> Carga:
    _validar_item(item)
    cantidad = _interpretar_cantidad(cantidad)
    if cantidad <= 0:
        raise ValidationError("La cantidad tiene que ser mayor que cero.", code="cantidad")
    nota = (nota or "").strip()[:120]
    unidad = item.unidad_medida
    precio = precio_en_unidad(item, unidad)
    with transaction.atomic():
        comanda = _bloquear(comanda)
        _reabrir_si_pidio_cuenta(comanda)
        # Lo que todavía no se envió y es igual se suma en la misma línea.
        detalle = comanda.detalles.filter(
            item=item,
            unidad_medida=unidad,
            nota=nota,
            ronda__isnull=True,
            anulado=False,
        ).first()
        if detalle:
            detalle.cantidad = redondear_cantidad(detalle.cantidad + cantidad)
            detalle.save(update_fields=["cantidad"])
        else:
            detalle = ComandaDetalle.objects.create(
                comanda=comanda,
                item=item,
                unidad_medida=unidad,
                cantidad=cantidad,
                precio=precio,
                tasa_iva=item.tasa_iva,
                nota=nota,
                cargado_por=usuario,
                cargado_en=timezone.now(),
            )
    return Carga(detalle=detalle, aviso=aviso_stock(item, unidad))


def _exigir_pendiente(detalle):
    if detalle.enviado:
        raise ValidationError(
            "Eso ya se envió. Para sacarlo hay que anularlo con un motivo.",
            code="enviado",
        )
    if detalle.anulado:
        raise ValidationError("Esa línea ya está anulada.", code="anulado")


def cambiar_pendiente(detalle, *, cantidad=None, nota=None):
    """Corrige una línea que todavía no se envió. Cantidad 0 la saca."""
    with transaction.atomic():
        _bloquear(detalle.comanda)
        detalle = ComandaDetalle.objects.select_for_update().get(pk=detalle.pk)
        _exigir_pendiente(detalle)
        campos = []
        if cantidad is not None:
            cantidad = _interpretar_cantidad(cantidad)
            if cantidad <= 0:
                detalle.delete()
                return None
            detalle.cantidad = cantidad
            campos.append("cantidad")
        if nota is not None:
            detalle.nota = nota.strip()[:120]
            campos.append("nota")
        if campos:
            detalle.save(update_fields=campos)
        return detalle


def quitar_pendiente(detalle):
    return cambiar_pendiente(detalle, cantidad=0)


# --- Enviar ------------------------------------------------------------------


def _descripcion(detalle) -> str:
    return detalle.item.descripcion


def enviar(comanda, *, usuario) -> Ronda:
    """Manda lo pendiente: arma la ronda y un envío por cada sector."""
    with transaction.atomic():
        comanda = _bloquear(comanda)
        pendientes = list(
            comanda.detalles.select_for_update()
            .filter(ronda__isnull=True, anulado=False)
            .select_related("item", "unidad_medida")
            .order_by("id")
        )
        if not pendientes:
            raise ValidationError("No hay nada nuevo para enviar.", code="vacia")
        ahora = timezone.now()
        ultimo = comanda.rondas.aggregate(ultimo=Max("numero"))["ultimo"] or 0
        ronda = Ronda.objects.create(
            comanda=comanda,
            numero=ultimo + 1,
            enviada_por=usuario,
            enviada_en=ahora,
        )
        por_sector = OrderedDict()
        for detalle in pendientes:
            sector = sector_de(detalle.item)
            detalle.ronda = ronda
            detalle.sector = sector
            detalle.save(update_fields=["ronda", "sector"])
            if sector is not None:
                por_sector.setdefault(sector, []).append(detalle)
        for sector, detalles in por_sector.items():
            envio = EnvioSector.objects.create(
                comanda=comanda,
                ronda=ronda,
                sector=sector,
                tipo=TipoEnvio.PEDIDO,
                usuario=usuario,
                creado_en=ahora,
            )
            EnvioSectorLinea.objects.bulk_create(
                [
                    EnvioSectorLinea(
                        envio=envio,
                        detalle=detalle,
                        descripcion=_descripcion(detalle),
                        cantidad=detalle.cantidad,
                        unidad=detalle.unidad_medida.simbolo,
                        nota=detalle.nota,
                    )
                    for detalle in detalles
                ]
            )
        return ronda


# --- Anular ------------------------------------------------------------------


def _motivo(motivo) -> str:
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError("Escribí el motivo.", code="motivo")
    return motivo[:200]


def anular_linea(detalle, *, usuario, motivo, cantidad=None) -> ComandaDetalle:
    """Saca algo ya enviado: queda registrado y el sector recibe la anulación."""
    motivo = _motivo(motivo)
    with transaction.atomic():
        comanda = _bloquear(detalle.comanda)
        detalle = (
            ComandaDetalle.objects.select_for_update()
            .select_related("item", "unidad_medida", "sector")
            .get(pk=detalle.pk)
        )
        if not detalle.enviado:
            raise ValidationError("Eso todavía no se envió: sacalo directamente.", code="pendiente")
        if detalle.anulado:
            raise ValidationError("Esa línea ya está anulada.", code="anulado")
        _exigir_fuera_de_caja(detalle)
        cantidad = detalle.cantidad if cantidad in (None, "") else _interpretar_cantidad(cantidad)
        if cantidad <= 0 or cantidad > detalle.cantidad:
            raise ValidationError(
                "La cantidad a anular tiene que ser entre 1 y lo pedido.", code="cantidad"
            )
        ahora = timezone.now()
        ComandaAnulacion.objects.create(
            detalle=detalle,
            cantidad=cantidad,
            motivo=motivo,
            usuario=usuario,
            fecha=ahora,
        )
        detalle.cantidad = redondear_cantidad(detalle.cantidad - cantidad)
        if detalle.cantidad <= 0:
            detalle.cantidad = CERO
            detalle.anulado = True
        detalle.save(update_fields=["cantidad", "anulado"])
        if detalle.sector_id:
            _avisar_anulacion(comanda, detalle, cantidad, motivo, usuario, ahora)
        return detalle


def _exigir_fuera_de_caja(detalle):
    if detalle.venta_detalle_id is not None:
        raise ValidationError(
            "Eso ya está en la caja para cobrarse: devolvelo desde el punto de venta "
            "antes de anularlo.",
            code="en_caja",
        )


def _avisar_anulacion(comanda, detalle, cantidad, motivo, usuario, ahora):
    envio = EnvioSector.objects.create(
        comanda=comanda,
        ronda=detalle.ronda,
        sector=detalle.sector,
        tipo=TipoEnvio.ANULACION,
        usuario=usuario,
        creado_en=ahora,
    )
    EnvioSectorLinea.objects.create(
        envio=envio,
        detalle=detalle,
        descripcion=_descripcion(detalle),
        cantidad=cantidad,
        unidad=detalle.unidad_medida.simbolo,
        nota=motivo[:120],
    )


def anular_comanda(comanda, *, usuario, motivo) -> Comanda:
    """Cierra la cuenta sin cobrar. Lo enviado se anula en cada sector."""
    motivo = _motivo(motivo)
    with transaction.atomic():
        comanda = _bloquear(comanda)
        enviados = (
            comanda.detalles.select_for_update()
            .filter(anulado=False, ronda__isnull=False)
            .select_related("item", "unidad_medida", "sector", "ronda")
        )
        for detalle in enviados:
            _exigir_fuera_de_caja(detalle)
        for detalle in enviados:
            anular_linea(detalle, usuario=usuario, motivo=motivo)
        comanda.detalles.filter(ronda__isnull=True).delete()
        comanda.estado = EstadoComanda.ANULADA
        comanda.motivo_anulacion = motivo
        comanda.anulada_por = usuario
        comanda.cerrada_en = timezone.now()
        comanda.save(update_fields=["estado", "motivo_anulacion", "anulada_por", "cerrada_en"])
        return comanda


def descartar(comanda):
    """Borra una cuenta abierta por error, si nunca se envió nada."""
    with transaction.atomic():
        comanda = _bloquear(comanda)
        if comanda.detalles.filter(ronda__isnull=False).exists():
            raise ValidationError(
                "Esta cuenta ya tiene cosas enviadas: hay que anularla con un motivo.",
                code="enviada",
            )
        comanda.delete()


# --- Cuenta ------------------------------------------------------------------


def pedir_cuenta(comanda) -> Comanda:
    with transaction.atomic():
        comanda = _bloquear(comanda)
        if tiene_pendientes(comanda):
            raise ValidationError(
                "Hay cosas sin enviar: enviálas o sacalas antes de pedir la cuenta.",
                code="pendientes",
            )
        if not tiene_enviados(comanda):
            raise ValidationError("La cuenta no tiene consumo.", code="vacia")
        comanda.estado = EstadoComanda.CUENTA_PEDIDA
        comanda.save(update_fields=["estado"])
        return comanda


def cambiar_datos(comanda, *, nombre=None, cliente=None, personas=None, quitar_cliente=False):
    with transaction.atomic():
        comanda = _bloquear(comanda)
        campos = []
        if nombre is not None:
            nombre = nombre.strip()[:80]
            if (
                not nombre
                and comanda.mesa_id is None
                and (quitar_cliente or (cliente is None and comanda.cliente_id is None))
            ):
                raise ValidationError(
                    "Una cuenta sin mesa necesita un nombre o un cliente.", code="sin_destino"
                )
            comanda.nombre = nombre
            campos.append("nombre")
        if cliente is not None:
            comanda.cliente = cliente
            campos.append("cliente")
        elif quitar_cliente:
            if comanda.mesa_id is None and not comanda.nombre:
                raise ValidationError(
                    "Una cuenta sin mesa necesita un nombre o un cliente.", code="sin_destino"
                )
            comanda.cliente = None
            campos.append("cliente")
        if personas is not None:
            if personas < 1:
                raise ValidationError(
                    "La cantidad de personas tiene que ser al menos 1.", code="personas"
                )
            comanda.personas = personas
            campos.append("personas")
        if campos:
            comanda.save(update_fields=campos)
        return comanda

"""Lectura del servicio: de qué mesa o pedido salió una venta, y en qué orden."""

from collections import OrderedDict
from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.cantidad import formatear_cantidad
from core.enlaces import url_ver_registro
from mesas.models import ComandaDetalle, EstadoComanda
from ventas.models import EstadoVenta

MOSTRADOR = "Mostrador"
CERO = Decimal("0")


def nombre_usuario(usuario) -> str:
    if usuario is None:
        return ""
    return (usuario.get_full_name() or "").strip() or usuario.username


def expresion_total():
    """Suma de lo pedido que sigue vigente. Lo anulado no entra."""
    return Coalesce(
        Sum(
            ExpressionWrapper(
                F("detalles__precio") * F("detalles__cantidad"),
                output_field=DecimalField(max_digits=18, decimal_places=3),
            ),
            filter=Q(detalles__anulado=False),
        ),
        Value(CERO, output_field=DecimalField(max_digits=18, decimal_places=3)),
    )


def _cuando(valor) -> str:
    if valor is None:
        return "—"
    return timezone.localtime(valor).strftime("%d/%m/%Y %H:%M")


def _hora(valor) -> str:
    if valor is None:
        return ""
    return timezone.localtime(valor).strftime("%H:%M")


def texto_origen(comandas) -> str:
    if not comandas:
        return MOSTRADOR
    titulos = []
    vistos = set()
    for comanda in comandas:
        titulo = comanda.titulo
        if titulo not in vistos:
            vistos.add(titulo)
            titulos.append(titulo)
    return ", ".join(titulos)


def texto_mozo(comandas) -> str:
    nombres = []
    vistos = set()
    for comanda in comandas:
        nombre = nombre_usuario(comanda.mozo)
        if nombre and nombre not in vistos:
            vistos.add(nombre)
            nombres.append(nombre)
    return ", ".join(nombres) if nombres else "—"


def _lineas_venta(venta):
    return (
        ComandaDetalle.objects.filter(venta_detalle__venta=venta)
        .select_related(
            "comanda__mesa",
            "comanda__cliente",
            "comanda__mozo",
            "item",
            "sector",
            "ronda",
            "ronda__enviada_por",
        )
        .prefetch_related("anulaciones")
        .order_by("comanda_id", "ronda__numero", "id")
    )


def origen_por_detalle(detalle_ids) -> dict[int, tuple[str, str]]:
    """Origen y mozo de cada línea de venta que salió de una comanda."""
    if not detalle_ids:
        return {}
    lineas = (
        ComandaDetalle.objects.filter(venta_detalle_id__in=detalle_ids)
        .select_related("comanda__mesa", "comanda__cliente", "comanda__mozo")
        .order_by("id")
    )
    grupos = OrderedDict()
    for linea in lineas:
        comandas = grupos.setdefault(linea.venta_detalle_id, OrderedDict())
        comandas.setdefault(linea.comanda_id, linea.comanda)
    return {
        detalle_id: (texto_origen(list(comandas.values())), texto_mozo(list(comandas.values())))
        for detalle_id, comandas in grupos.items()
    }


def origen_impreso(venta) -> str:
    """Texto para el ticket y la factura. El mostrador no se imprime."""
    comandas = list(dict.fromkeys(linea.comanda for linea in _lineas_venta(venta)))
    if not comandas:
        return ""
    return texto_origen(comandas)


def _cantidad_visible(linea):
    if linea.anulado:
        total = sum((anulacion.cantidad for anulacion in linea.anulaciones.all()), CERO)
        if total > 0:
            return total
    return linea.cantidad


def _cuenta(comanda, lineas) -> dict:
    rondas = OrderedDict()
    anulaciones = []
    for linea in lineas:
        ronda = linea.ronda
        clave = ronda.pk if ronda is not None else 0
        bloque = rondas.get(clave)
        if bloque is None:
            bloque = {
                "titulo": f"Ronda {ronda.numero}" if ronda is not None else "Sin enviar",
                "cuando": _hora(ronda.enviada_en) if ronda is not None else "",
                "quien": nombre_usuario(ronda.enviada_por) if ronda is not None else "",
                "lineas": [],
            }
            rondas[clave] = bloque
        bloque["lineas"].append(
            {
                "cantidad": formatear_cantidad(_cantidad_visible(linea)),
                "item": linea.item.descripcion,
                "nota": linea.nota,
                "sector": linea.sector.nombre if linea.sector_id else "",
                "anulado": linea.anulado,
            }
        )
        for anulacion in linea.anulaciones.all():
            anulaciones.append(
                {
                    "cantidad": formatear_cantidad(anulacion.cantidad),
                    "item": linea.item.descripcion,
                    "motivo": anulacion.motivo,
                    "cuando": _hora(anulacion.fecha),
                    "ronda": f"Ronda {ronda.numero}" if ronda is not None else "",
                }
            )
    cerrada = comanda.estado in (EstadoComanda.CERRADA, EstadoComanda.ANULADA)
    return {
        "origen": comanda.titulo,
        "mozo": nombre_usuario(comanda.mozo) or "—",
        "personas": str(comanda.personas) if comanda.personas else "—",
        "abierta": _cuando(comanda.abierta_en),
        "cerrada": _cuando(comanda.cerrada_en) if comanda.cerrada_en else "—",
        "estado": comanda.get_estado_display(),
        "motivo": comanda.motivo_anulacion,
        "rondas": list(rondas.values()),
        "anulaciones": anulaciones,
        "url": url_ver_registro("servicio_historial", "servicio", comanda.pk) if cerrada else "",
    }


def _comprobantes(lineas) -> list[dict]:
    vistos = OrderedDict()
    for linea in lineas:
        detalle = linea.venta_detalle
        if detalle is None:
            continue
        venta = detalle.venta
        if venta.pk in vistos:
            continue
        numero = venta.numero_completo or f"Venta {venta.pk}"
        visible = venta.estado in (EstadoVenta.COBRADA, EstadoVenta.ANULADA)
        vistos[venta.pk] = {
            "texto": f"{venta.get_tipo_comprobante_display()} {numero}",
            "estado": venta.get_estado_display(),
            "url": url_ver_registro("venta_list", "venta", venta.pk) if visible else "",
        }
    return list(vistos.values())


def relato_venta(venta) -> dict:
    """Rondas y líneas que esta venta cobró. El mostrador se indica aparte."""
    lineas = list(_lineas_venta(venta))
    grupos = OrderedDict()
    for linea in lineas:
        grupos.setdefault(linea.comanda_id, {"comanda": linea.comanda, "lineas": []})
        grupos[linea.comanda_id]["lineas"].append(linea)
    cuentas = [_cuenta(grupo["comanda"], grupo["lineas"]) for grupo in grupos.values()]
    vinculadas = {linea.venta_detalle_id for linea in lineas}
    sueltas = venta.detalles.exclude(pk__in=vinculadas).exists()
    aviso = ""
    if cuentas and venta.estado == EstadoVenta.ANULADA:
        aviso = "La venta está anulada. La cuenta no se vuelve a abrir."
    return {
        "solo_mostrador": not cuentas,
        "mostrador": bool(cuentas) and sueltas,
        "aviso": aviso,
        "cuentas": cuentas,
        "comprobantes": [],
    }


def relato_cuenta(comanda) -> dict:
    """Todo el servicio, con lo anulado y los comprobantes que lo cobraron."""
    lineas = list(
        comanda.detalles.select_related(
            "item",
            "sector",
            "ronda",
            "ronda__enviada_por",
            "venta_detalle__venta",
        )
        .prefetch_related("anulaciones")
        .order_by("ronda__numero", "id")
    )
    return {
        "solo_mostrador": False,
        "mostrador": False,
        "aviso": "",
        "cuentas": [_cuenta(comanda, lineas)],
        "comprobantes": _comprobantes(lineas),
    }

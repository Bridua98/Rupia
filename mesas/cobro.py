"""Cobro de comandas: pasar la cuenta al punto de venta y cerrarla al confirmar.

La venta se cobra con el flujo de siempre (ticket o factura, medio de pago,
timbrado y stock). Acá solo se copian las líneas y se cierra la cuenta.
"""

from collections import OrderedDict
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from mesas.comandas import _bloquear
from mesas.models import Comanda, ComandaDetalle, EstadoComanda
from ventas.cobro import actualizar_cabecera, borrador, importe_linea
from ventas.models import EstadoVenta, VentaDetalle

CERO_DESCUENTO = 0


def _por_cobrar(comanda):
    """Líneas enviadas, vigentes y que todavía no se cobraron."""
    return comanda.detalles.filter(anulado=False, ronda__isnull=False).exclude(
        venta_detalle__venta__estado=EstadoVenta.COBRADA
    )


def venta_en_caja(comanda):
    """La venta en curso (de cualquier caja) que tiene líneas de esta cuenta."""
    detalle = (
        comanda.detalles.filter(venta_detalle__venta__estado=EstadoVenta.EN_CURSO)
        .select_related("venta_detalle__venta__usuario")
        .first()
    )
    return detalle.venta_detalle.venta if detalle else None


def pasar_a_venta(comanda, *, usuario):
    """Copia lo consumido a la venta en curso del cajero y la devuelve."""
    with transaction.atomic():
        comanda = _bloquear(comanda)
        if comanda.detalles.filter(anulado=False, ronda__isnull=True).exists():
            raise ValidationError(
                "Hay cosas sin enviar: enviálas o sacalas antes de cobrar.",
                code="pendientes",
            )
        venta = borrador(usuario)
        otra = venta_en_caja(comanda)
        if otra is not None and otra.pk != venta.pk:
            cajero = otra.usuario.first_name or otra.usuario.username
            raise ValidationError(
                f"Esta cuenta ya se está cobrando en la caja de {cajero}.",
                code="en_otra_caja",
            )
        lineas = list(
            _por_cobrar(comanda)
            .filter(venta_detalle__isnull=True)
            .select_for_update()
            .select_related("item", "unidad_medida")
            .order_by("id")
        )
        if not lineas:
            if otra is not None:
                # Ya estaba en esta caja: se sigue cobrando ahí.
                return venta
            raise ValidationError("La cuenta no tiene nada para cobrar.", code="vacia")
        if venta.detalles.exists():
            raise ValidationError(
                "Tenés una venta empezada en el punto de venta. "
                "Terminala o cancelala antes de cobrar la cuenta.",
                code="venta_ocupada",
            )
        grupos = OrderedDict()
        for linea in lineas:
            clave = (linea.item_id, linea.unidad_medida_id, linea.precio, linea.tasa_iva)
            grupos.setdefault(clave, []).append(linea)
        for (_item, _unidad, precio, tasa), grupo in grupos.items():
            cantidad = sum((linea.cantidad for linea in grupo), Decimal("0"))
            detalle = VentaDetalle.objects.create(
                venta=venta,
                item=grupo[0].item,
                unidad_medida=grupo[0].unidad_medida,
                cantidad=cantidad,
                precio=precio,
                tasa_iva=tasa,
                descuento_porcentaje=CERO_DESCUENTO,
                subtotal=importe_linea(precio, cantidad),
            )
            ComandaDetalle.objects.filter(pk__in=[linea.pk for linea in grupo]).update(
                venta_detalle=detalle
            )
        if comanda.cliente_id:
            actualizar_cabecera(venta, cliente=comanda.cliente)
        return venta


def cerrar_cobradas(venta):
    """Cierra las cuentas que esta venta terminó de cobrar."""
    comandas = Comanda.objects.filter(
        detalles__venta_detalle__venta=venta,
        estado__in=(EstadoComanda.ABIERTA, EstadoComanda.CUENTA_PEDIDA),
    ).distinct()
    ahora = timezone.now()
    for comanda in comandas:
        queda = comanda.detalles.filter(anulado=False).exclude(
            venta_detalle__venta__estado=EstadoVenta.COBRADA
        )
        if not queda.exists():
            comanda.estado = EstadoComanda.CERRADA
            comanda.cerrada_en = ahora
            comanda.save(update_fields=["estado", "cerrada_en"])


def al_confirmar_venta(sender, venta, **kwargs):
    cerrar_cobradas(venta)

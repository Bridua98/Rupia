from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from compras.cuotas import cuotas_abiertas_proveedor
from compras.models import (
    CompraCuota,
    EstadoPagoProveedor,
    PagoCuota,
    PagoProveedor,
)
from inventario.precios import redondear_guarani
from personas.models import Persona

CERO = Decimal("0")


def _parse_aplicaciones(datos: dict) -> list[tuple[int, Decimal]]:
    aplicaciones = []
    for clave, valor in datos.items():
        if not clave.startswith("aplicar_"):
            continue
        try:
            cuota_id = int(clave.removeprefix("aplicar_"))
        except ValueError:
            continue
        if valor in (None, ""):
            continue
        from core.moneda import interpretar_guaranies

        texto = interpretar_guaranies(valor)
        if not texto:
            continue
        importe = redondear_guarani(Decimal(texto))
        if importe <= 0:
            continue
        aplicaciones.append((cuota_id, importe))
    return aplicaciones


def confirmar_pago(
    *,
    usuario,
    proveedor: Persona,
    cuenta,
    fecha,
    observacion="",
    aplicaciones: list[tuple[int, Decimal]],
) -> PagoProveedor:
    if not proveedor.es_proveedor:
        raise ValidationError("Esa persona no es proveedor.", code="proveedor")
    if not aplicaciones:
        raise ValidationError("Indicá el importe a aplicar en al menos una cuota.", code="vacío")
    importe_total = redondear_guarani(sum((par[1] for par in aplicaciones), CERO))
    if importe_total <= 0:
        raise ValidationError("El importe del pago tiene que ser mayor a cero.", code="importe")

    cuota_ids = [par[0] for par in aplicaciones]
    with transaction.atomic():
        # Bloquear las cuotas antes de leer su saldo: dos pagos simultáneos sobre
        # la misma cuota no pueden pasar los dos el control de saldo.
        cuotas = {
            c.pk: c
            for c in CompraCuota.objects.select_for_update()
            .filter(pk__in=sorted(set(cuota_ids)))
            .select_related("compra")
            .order_by("pk")
        }
        if len(cuotas) != len(set(cuota_ids)):
            raise ValidationError("Hay cuotas que no existen.", code="cuota")

        abiertas = {c.pk: saldo for c, saldo in cuotas_abiertas_proveedor(proveedor.pk)}
        pago = PagoProveedor.objects.create(
            fecha=fecha,
            proveedor=proveedor,
            cuenta=cuenta,
            importe=importe_total,
            observacion=(observacion or "").strip(),
            usuario=usuario,
            estado=EstadoPagoProveedor.CONFIRMADO,
        )
        for cuota_id, importe in aplicaciones:
            cuota = cuotas[cuota_id]
            if cuota.compra.proveedor_id != proveedor.pk:
                raise ValidationError(
                    "Todas las cuotas tienen que ser del mismo proveedor.",
                    code="proveedor",
                )
            saldo = abiertas.get(cuota_id)
            if saldo is None:
                raise ValidationError(
                    f"La cuota {cuota.numero} ya no está abierta (compra anulada, "
                    "sin confirmar o ya pagada).",
                    code="cuota",
                )
            if importe > saldo:
                raise ValidationError(
                    f"El importe en la cuota {cuota.numero} supera el saldo ({saldo}).",
                    code="saldo",
                )
            PagoCuota.objects.create(pago=pago, cuota=cuota, importe=importe)
    return pago


def confirmar_pago_desde_post(usuario, post) -> PagoProveedor:
    from cuentas.models import Cuenta

    proveedor_id = post.get("proveedor")
    if not proveedor_id:
        raise ValidationError("Elegí un proveedor.", code="proveedor")
    proveedor = Persona.objects.get(pk=proveedor_id)
    cuenta_id = post.get("cuenta")
    if not cuenta_id:
        raise ValidationError("Elegí una cuenta.", code="cuenta")
    cuenta = Cuenta.objects.get(pk=cuenta_id)
    fecha_raw = post.get("fecha")
    if not fecha_raw:
        raise ValidationError("Elegí la fecha.", code="fecha")
    from datetime import datetime

    try:
        fecha = datetime.strptime(str(fecha_raw), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValidationError("Elegí una fecha válida.", code="fecha") from exc
    aplicaciones = _parse_aplicaciones(post)
    return confirmar_pago(
        usuario=usuario,
        proveedor=proveedor,
        cuenta=cuenta,
        fecha=fecha,
        observacion=post.get("observacion", ""),
        aplicaciones=aplicaciones,
    )


def anular(pago, usuario=None):
    with transaction.atomic():
        pago = PagoProveedor.objects.select_for_update().get(pk=pago.pk)
        if pago.estado == EstadoPagoProveedor.ANULADO:
            raise ValidationError("Ese pago ya está anulado.", code="anulado")
        if pago.estado != EstadoPagoProveedor.CONFIRMADO:
            raise ValidationError("Solo se puede anular un pago confirmado.", code="estado")
        pago.estado = EstadoPagoProveedor.ANULADO
        pago.anulado_en = timezone.now()
        pago.anulado_por = usuario
        pago.save(update_fields=["estado", "anulado_en", "anulado_por"])
    return pago

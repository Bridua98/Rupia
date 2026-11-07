from datetime import datetime, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import DecimalField
from django.utils import timezone

from compras.models import CompraCuota, EstadoPagoProveedor, PagoCuota, TipoCompra
from core.moneda import formatear_guaranies, mostrar_guaranies
from inventario.precios import redondear_guarani

CERO = Decimal("0")
IMPORTE = DecimalField(max_digits=15, decimal_places=3)


def _exige_borrador(compra):
    from compras.models import EstadoCompra

    if compra.estado != EstadoCompra.EN_CURSO:
        raise ValidationError("Esa compra ya está confirmada.", code="confirmada")


def _parse_fecha(valor):
    if not valor:
        raise ValidationError("Elegí el vencimiento.", code="vencimiento")
    if hasattr(valor, "year"):
        return valor
    try:
        return datetime.strptime(str(valor), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValidationError("Elegí una fecha válida.", code="vencimiento") from exc


def cuotas_vista(compra) -> list[dict]:
    filas = []
    for cuota in compra.cuotas.order_by("numero"):
        filas.append(
            {
                "pk": cuota.pk,
                "numero": cuota.numero,
                "vencimiento": cuota.vencimiento,
                "vencimiento_txt": cuota.vencimiento.strftime("%d/%m/%Y"),
                "importe": cuota.importe,
                "importe_txt": _dinero(cuota.importe),
            }
        )
    return filas


def _dinero(valor):
    return formatear_guaranies(redondear_guarani(valor or CERO))


def resumen_cuotas(compra, total: Decimal) -> dict:
    filas = cuotas_vista(compra)
    suma = redondear_guarani(sum((fila["importe"] for fila in filas), CERO))
    total = redondear_guarani(total or CERO)
    restante = redondear_guarani(total - suma)
    ultima = compra.cuotas.order_by("-numero").first()
    if ultima:
        sugerido_vence = ultima.vencimiento + timedelta(days=30)
    else:
        sugerido_vence = timezone.localdate()
    sugerido_importe = restante if restante > 0 else CERO
    return {
        "filas": filas,
        "suma": suma,
        "suma_txt": mostrar_guaranies(suma),
        "restante": restante,
        "restante_txt": mostrar_guaranies(abs(restante)),
        "completa": bool(filas) and restante == 0,
        "sugerido_vence": sugerido_vence.isoformat(),
        "sugerido_importe_txt": _dinero(sugerido_importe) if sugerido_importe > 0 else "",
    }


def _renumerar(compra):
    for orden, cuota in enumerate(compra.cuotas.order_by("numero", "id"), start=1):
        if cuota.numero != orden:
            cuota.numero = orden
            cuota.save(update_fields=["numero"])


def agregar_cuota(compra, *, vencimiento, importe: Decimal):
    _exige_borrador(compra)
    if compra.tipo != TipoCompra.FACTURA_CREDITO:
        raise ValidationError("Las cuotas son solo para factura crédito.", code="tipo")
    vencimiento = _parse_fecha(vencimiento)
    importe = redondear_guarani(importe)
    if importe <= 0:
        raise ValidationError("El importe tiene que ser mayor a cero.", code="importe")
    max_num = compra.cuotas.order_by("-numero").values_list("numero", flat=True).first() or 0
    return CompraCuota.objects.create(
        compra=compra,
        numero=max_num + 1,
        vencimiento=vencimiento,
        importe=importe,
    )


def actualizar_cuota(cuota, *, vencimiento=None, importe=None):
    _exige_borrador(cuota.compra)
    campos = []
    if vencimiento is not None:
        cuota.vencimiento = _parse_fecha(vencimiento)
        campos.append("vencimiento")
    if importe is not None:
        importe = redondear_guarani(importe)
        if importe <= 0:
            raise ValidationError("El importe tiene que ser mayor a cero.", code="importe")
        cuota.importe = importe
        campos.append("importe")
    if campos:
        cuota.save(update_fields=campos)
    return cuota


def quitar_cuota(cuota):
    _exige_borrador(cuota.compra)
    compra = cuota.compra
    cuota.delete()
    _renumerar(compra)


def limpiar_cuotas(compra):
    compra.cuotas.all().delete()


def validar_cuotas_credito(compra, total: Decimal):
    if compra.tipo != TipoCompra.FACTURA_CREDITO:
        return
    cuotas = list(compra.cuotas.order_by("numero"))
    if not cuotas:
        raise ValidationError("Agregá al menos una cuota.", code="cuotas")
    suma = CERO
    for cuota in cuotas:
        if cuota.importe <= 0:
            raise ValidationError(
                f"La cuota {cuota.numero} tiene que tener importe mayor a cero.",
                code="cuotas",
            )
        suma += cuota.importe
    suma = redondear_guarani(suma)
    total = redondear_guarani(total)
    if suma != total:
        raise ValidationError(
            f"La suma de las cuotas ({_dinero(suma)}) tiene que coincidir con el total "
            f"({_dinero(total)}).",
            code="cuotas",
        )


def compra_tiene_pagos(compra) -> bool:
    return PagoCuota.objects.filter(
        cuota__compra_id=compra.pk,
        pago__estado=EstadoPagoProveedor.CONFIRMADO,
    ).exists()


def cuotas_abiertas_proveedor(proveedor_id):
    """Cuotas con saldo pendiente de facturas crédito confirmadas."""
    from compras.models import Compra, EstadoCompra

    cuotas = (
        CompraCuota.objects.filter(
            compra__estado=EstadoCompra.CONFIRMADA,
            compra__tipo=TipoCompra.FACTURA_CREDITO,
            compra__proveedor_id=proveedor_id,
        )
        .select_related("compra", "compra__proveedor")
        .order_by("vencimiento", "compra_id", "numero")
    )
    abiertas = []
    for cuota in cuotas:
        saldo = cuota.saldo_pendiente()
        if saldo > 0:
            abiertas.append((cuota, saldo))
    return abiertas


def total_saldo_pendiente() -> Decimal:
    from compras.models import Compra, EstadoCompra

    cuotas = CompraCuota.objects.filter(
        compra__estado=EstadoCompra.CONFIRMADA,
        compra__tipo=TipoCompra.FACTURA_CREDITO,
    )
    total = CERO
    for cuota in cuotas:
        saldo = cuota.saldo_pendiente()
        if saldo > 0:
            total += saldo
    return redondear_guarani(total)

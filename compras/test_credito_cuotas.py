from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from compras.models import (
    Compra,
    CompraCuota,
    EstadoCompra,
    EstadoPagoProveedor,
    PagoProveedor,
    TipoCompra,
)
from compras.test_compra import _cabecera, _cuota_total, _preparar
from cuentas.disponibilidad import mayor_disponibilidad
from inventario.models import ItemMovimiento, TipoMovimiento


def _confirmar_credito(ingresada, cuenta, proveedor, *, costo="8.000", cuotas=None):
    from compras.models import CompraDetalle

    ingresada.post("/compras/nueva/agregar/", {"q": "PROD-001"})
    detalle = CompraDetalle.objects.get()
    ingresada.post(
        f"/compras/nueva/lineas/{detalle.pk}/",
        {"accion": "costo", "costo": costo},
    )
    ingresada.post(
        "/compras/nueva/",
        _cabecera(cuenta, proveedor, tipo=TipoCompra.FACTURA_CREDITO),
    )
    compra = Compra.objects.get(estado=EstadoCompra.EN_CURSO)
    total = sum((d.subtotal for d in compra.detalles.all()), Decimal("0"))
    if cuotas:
        for vence, importe in cuotas:
            ingresada.post(
                "/compras/nueva/cuotas/",
                {
                    "accion": "agregar",
                    "vencimiento": vence,
                    "importe": str(int(importe)),
                },
            )
    else:
        _cuota_total(ingresada, total, cuenta=cuenta, proveedor=proveedor)
    ingresada.post(
        "/compras/nueva/confirmar/",
        _cabecera(cuenta, proveedor, tipo=TipoCompra.FACTURA_CREDITO),
    )
    return Compra.objects.filter(estado=EstadoCompra.CONFIRMADA).order_by("-id").first()


@pytest.mark.django_db
def test_credito_sin_cuotas_no_confirma(ingresada):
    cuenta, proveedor, _item = _preparar()
    ingresada.post("/compras/nueva/agregar/", {"q": "PROD-001"})
    from compras.models import CompraDetalle

    detalle = CompraDetalle.objects.get()
    ingresada.post(
        f"/compras/nueva/lineas/{detalle.pk}/",
        {"accion": "costo", "costo": "8.000"},
    )
    ingresada.post(
        "/compras/nueva/",
        _cabecera(cuenta, proveedor, tipo=TipoCompra.FACTURA_CREDITO),
    )
    ingresada.post(
        "/compras/nueva/confirmar/",
        _cabecera(cuenta, proveedor, tipo=TipoCompra.FACTURA_CREDITO),
    )
    assert Compra.objects.filter(estado=EstadoCompra.CONFIRMADA).count() == 0


@pytest.mark.django_db
def test_credito_suma_cuotas_distinta_no_confirma(ingresada):
    cuenta, proveedor, _item = _preparar()
    ingresada.post("/compras/nueva/agregar/", {"q": "PROD-001"})
    from compras.models import CompraDetalle

    detalle = CompraDetalle.objects.get()
    ingresada.post(
        f"/compras/nueva/lineas/{detalle.pk}/",
        {"accion": "costo", "costo": "8.000"},
    )
    _cuota_total(ingresada, Decimal("5000"), cuenta=cuenta, proveedor=proveedor)
    ingresada.post(
        "/compras/nueva/confirmar/",
        _cabecera(cuenta, proveedor, tipo=TipoCompra.FACTURA_CREDITO),
    )
    assert Compra.objects.filter(estado=EstadoCompra.CONFIRMADA).count() == 0


@pytest.mark.django_db
def test_credito_confirma_sin_mover_caja(ingresada):
    cuenta, proveedor, _item = _preparar()
    compra = _confirmar_credito(ingresada, cuenta, proveedor)
    assert compra.tipo == TipoCompra.FACTURA_CREDITO
    assert compra.cuenta_id is None
    assert CompraCuota.objects.filter(compra=compra).count() == 1
    assert ItemMovimiento.objects.filter(tipo=TipoMovimiento.COMPRA).exists()
    _, _, totales = mayor_disponibilidad(cuenta_id=cuenta.pk)
    assert totales["salida"] == Decimal("0")


@pytest.mark.django_db
def test_pago_parcial_y_disponibilidad(ingresada):
    cuenta, proveedor, _item = _preparar()
    hoy = timezone.localdate()
    compra = _confirmar_credito(
        ingresada,
        cuenta,
        proveedor,
        cuotas=[(hoy.isoformat(), Decimal("5000")), ((hoy + timedelta(days=30)).isoformat(), Decimal("3000"))],
    )
    cuotas = list(CompraCuota.objects.filter(compra=compra).order_by("numero"))
    ingresada.post(
        "/compras/pagos/nueva/",
        {
            "proveedor": str(proveedor.pk),
            "fecha": hoy.isoformat(),
            "cuenta": str(cuenta.pk),
            f"aplicar_{cuotas[0].pk}": "3000",
            f"aplicar_{cuotas[1].pk}": "2000",
        },
    )
    pago = PagoProveedor.objects.get()
    assert pago.importe == Decimal("5000")
    cuotas[0].refresh_from_db()
    assert cuotas[0].saldo_pendiente() == Decimal("2000")
    assert cuotas[1].saldo_pendiente() == Decimal("1000")
    _, _, totales = mayor_disponibilidad(cuenta_id=cuenta.pk)
    assert totales["salida"] == Decimal("5000")


@pytest.mark.django_db
def test_anular_pago_y_compra_con_pago(ingresada):
    cuenta, proveedor, _item = _preparar()
    compra = _confirmar_credito(ingresada, cuenta, proveedor)
    cuota = CompraCuota.objects.get(compra=compra)
    hoy = timezone.localdate()
    ingresada.post(
        "/compras/pagos/nueva/",
        {
            "proveedor": str(proveedor.pk),
            "fecha": hoy.isoformat(),
            "cuenta": str(cuenta.pk),
            f"aplicar_{cuota.pk}": "8000",
        },
    )
    pago = PagoProveedor.objects.get()
    ingresada.post(f"/compras/{compra.pk}/anular/")
    assert Compra.objects.get(pk=compra.pk).estado == EstadoCompra.CONFIRMADA
    ingresada.post(f"/compras/pagos/{pago.pk}/anular/")
    assert PagoProveedor.objects.get().estado == EstadoPagoProveedor.ANULADO
    assert cuota.saldo_pendiente() == Decimal("8000")
    _, _, totales = mayor_disponibilidad(cuenta_id=cuenta.pk)
    assert totales["salida"] == Decimal("0")


@pytest.mark.django_db
def test_formulario_credito_muestra_cuotas_y_total_junto_a_acciones(ingresada):
    cuenta, proveedor, _item = _preparar()
    ingresada.post("/compras/nueva/agregar/", {"q": "PROD-001"})
    ingresada.post(
        "/compras/nueva/",
        _cabecera(cuenta, proveedor, tipo=TipoCompra.FACTURA_CREDITO),
    )
    respuesta = ingresada.get("/compras/nueva/")
    assert respuesta.status_code == 200
    cuerpo = respuesta.content.decode()
    assert 'class="pos-totals"' in cuerpo
    assert 'class="pos-side-scroll"' in cuerpo
    assert 'class="pos-card pos-cuotas"' in cuerpo
    assert "Agregar cuota" in cuerpo
    assert 'class="pos-card pos-summary"' not in cuerpo


@pytest.mark.django_db
def test_reporte_cuentas_pagar(ingresada):
    cuenta, proveedor, _item = _preparar()
    hoy = timezone.localdate()
    ayer = hoy - timedelta(days=5)
    _confirmar_credito(
        ingresada,
        cuenta,
        proveedor,
        cuotas=[(ayer.isoformat(), Decimal("8000"))],
    )
    respuesta = ingresada.get("/compras/reportes/cuentas-a-pagar/?situacion=vencida")
    assert respuesta.status_code == 200
    cuerpo = respuesta.content.decode()
    assert proveedor.razon_social in cuerpo
    assert "Vencida" in cuerpo or "vencida" in cuerpo.lower()

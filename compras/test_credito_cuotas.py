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
from compras.cuotas import total_saldo_pendiente
from compras.test_compra import _cabecera, _cuota_total, _preparar
from cuentas.disponibilidad import mayor_disponibilidad
from inventario.models import ItemMovimiento, TipoMovimiento
from personas.models import Genero, Persona, TipoDocumento


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
def test_listado_pago_abre_formulario_visible(ingresada):
    listado = ingresada.get("/compras/pagos/")
    assert listado.status_code == 200
    cuerpo = listado.content.decode()
    assert 'href="/compras/pagos/nueva/"' in cuerpo
    assert "Nuevo pago" in cuerpo

    formulario = ingresada.get("/compras/pagos/nueva/")
    assert formulario.status_code == 200
    cuerpo = formulario.content.decode()
    assert "Nuevo pago a proveedor" in cuerpo
    assert 'id="pago-proveedor"' in cuerpo
    assert 'id="pago-cuenta"' in cuerpo
    assert 'id="pago-fecha"' in cuerpo
    assert "Cuotas a cancelar" in cuerpo
    assert "Elegí un proveedor para ver las cuotas abiertas." in cuerpo


@pytest.mark.django_db
def test_formulario_pago_muestra_cuotas_y_acepta_miles(ingresada):
    cuenta, proveedor, _item = _preparar()
    compra = _confirmar_credito(ingresada, cuenta, proveedor)
    cuota = CompraCuota.objects.get(compra=compra)
    respuesta = ingresada.get(f"/compras/pagos/nueva/?proveedor={proveedor.pk}")
    assert respuesta.status_code == 200
    cuerpo = respuesta.content.decode()
    assert f'name="aplicar_{cuota.pk}"' in cuerpo
    assert 'data-moneda="guarani"' in cuerpo
    hoy = timezone.localdate()
    ingresada.post(
        "/compras/pagos/nueva/",
        {
            "proveedor": str(proveedor.pk),
            "fecha": hoy.isoformat(),
            "cuenta": str(cuenta.pk),
            f"aplicar_{cuota.pk}": "8.000",
        },
    )
    assert PagoProveedor.objects.get().importe == Decimal("8000")
    assert cuota.saldo_pendiente() == Decimal("0")


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
    compra = _confirmar_credito(
        ingresada,
        cuenta,
        proveedor,
        cuotas=[(ayer.isoformat(), Decimal("8000"))],
    )
    cuota = CompraCuota.objects.get(compra=compra)
    respuesta = ingresada.get(
        "/compras/reportes/cuentas-a-pagar/"
        f"?situacion=vencida&vencimiento_desde={ayer.isoformat()}&vencimiento_hasta={hoy.isoformat()}"
    )
    assert respuesta.status_code == 200
    cuerpo = respuesta.content.decode().replace("&amp;", "&")
    assert proveedor.razon_social in cuerpo
    assert "Vencida" in cuerpo or "vencida" in cuerpo.lower()
    assert f"/compras/?compra={compra.pk}&ver=1" in cuerpo
    assert "data-href" not in cuerpo

    seleccion = ingresada.get(
        f"/compras/reportes/cuentas-a-pagar/?reporte_sel={cuota.pk}"
        f"&vencimiento_desde={ayer.isoformat()}&vencimiento_hasta={hoy.isoformat()}"
    )
    assert seleccion.status_code == 200


def _proveedor_nombre(nombre, documento):
    return Persona.objects.create(
        tipo_documento=TipoDocumento.RUC,
        documento=documento,
        razon_social=nombre,
        genero=Genero.SIN_DEFINIR,
        direccion="Centro",
        es_proveedor=True,
    )


def _cuota_credito(usuario, proveedor, *, numero, vencimiento, importe):
    compra = Compra.objects.create(
        fecha=vencimiento,
        estado=EstadoCompra.CONFIRMADA,
        tipo=TipoCompra.FACTURA_CREDITO,
        proveedor=proveedor,
        usuario=usuario,
        timbrado="12345678",
        establecimiento="001",
        punto_codigo="001",
        secuencial=int(numero.split("-")[-1]),
        numero_completo=numero,
    )
    return CompraCuota.objects.create(
        compra=compra,
        numero=1,
        vencimiento=vencimiento,
        importe=importe,
    )


@pytest.mark.django_db
def test_reporte_cuentas_pagar_por_defecto_filtra_el_mes(ingresada, usuario):
    hoy = timezone.localdate()
    mes_anterior = hoy.replace(day=1) - timedelta(days=1)
    actual = _proveedor_nombre("Proveedor mes", "80003333-4")
    viejo = _proveedor_nombre("Proveedor viejo", "80004444-5")
    _cuota_credito(
        usuario, actual, numero="001-001-0000101", vencimiento=hoy, importe=Decimal("8000")
    )
    _cuota_credito(
        usuario,
        viejo,
        numero="001-001-0000102",
        vencimiento=mes_anterior,
        importe=Decimal("1500"),
    )

    content = ingresada.get("/compras/reportes/cuentas-a-pagar/").content.decode()
    cuerpo = content.split("<tbody>")[1].split("</tbody>")[0]
    assert "Proveedor mes" in cuerpo
    assert "Proveedor viejo" not in cuerpo
    assert f'value="{hoy.replace(day=1).isoformat()}"' in content
    assert f'value="{hoy.isoformat()}"' in content


@pytest.mark.django_db
def test_reporte_cuentas_pagar_agrupa_saldo_por_proveedor(ingresada, usuario):
    hoy = timezone.localdate()
    alfa = _proveedor_nombre("Alfa SA", "80005555-6")
    beta = _proveedor_nombre("Beta SRL", "80006666-7")
    _cuota_credito(
        usuario, alfa, numero="001-001-0000201", vencimiento=hoy, importe=Decimal("3000")
    )
    _cuota_credito(
        usuario, alfa, numero="001-001-0000202", vencimiento=hoy, importe=Decimal("2000")
    )
    _cuota_credito(
        usuario, beta, numero="001-001-0000203", vencimiento=hoy, importe=Decimal("4000")
    )

    detalle = ingresada.get("/compras/reportes/cuentas-a-pagar/").content.decode()
    thead_detalle = detalle.split("<thead>")[1].split("</thead>")[0]
    cuerpo_detalle = detalle.split("<tbody>")[1].split("</tbody>")[0]
    assert "Alfa SA" in cuerpo_detalle
    assert "Beta SRL" in cuerpo_detalle
    assert "3 cuotas" in detalle
    assert "Factura" in thead_detalle
    assert "Vencimiento" in thead_detalle

    agrupado = ingresada.get("/compras/reportes/cuentas-a-pagar/?agrupar=proveedor")
    content = agrupado.content.decode()
    thead = content.split("<thead>")[1].split("</thead>")[0]
    cuerpo = content.split("<tbody>")[1].split("</tbody>")[0]
    assert agrupado.status_code == 200
    assert "Por proveedor" in content
    assert "Alfa SA" in cuerpo
    assert "Beta SRL" in cuerpo
    assert "2 filas" in content
    assert "5.000" in cuerpo
    assert "4.000" in cuerpo
    assert "Factura" not in thead
    assert "Vencimiento" not in thead


@pytest.mark.django_db
def test_pago_cae_en_disponibilidad_cuentas_pagar_y_tablero(ingresada):
    cuenta, proveedor, _item = _preparar()
    hoy = timezone.localdate()
    compra = _confirmar_credito(
        ingresada,
        cuenta,
        proveedor,
        cuotas=[(hoy.isoformat(), Decimal("8000"))],
    )
    cuota = CompraCuota.objects.get(compra=compra)
    assert total_saldo_pendiente() == Decimal("8000")
    ingresada.post(
        "/compras/pagos/nueva/",
        {
            "proveedor": str(proveedor.pk),
            "fecha": hoy.isoformat(),
            "cuenta": str(cuenta.pk),
            f"aplicar_{cuota.pk}": "5.000",
        },
    )
    pago = PagoProveedor.objects.get()
    assert cuota.saldo_pendiente() == Decimal("3000")
    assert total_saldo_pendiente() == Decimal("3000")

    periodo = f"fecha_desde={hoy.isoformat()}&fecha_hasta={hoy.isoformat()}"
    disponibilidad = ingresada.get(f"/cuentas/disponibilidad/?{periodo}").content.decode()
    assert "Pago proveedor" in disponibilidad
    assert f"/compras/pagos/?pago={pago.pk}" in disponibilidad.replace("&amp;", "&")
    assert "5.000" in disponibilidad

    cuentas_pagar = ingresada.get("/compras/reportes/cuentas-a-pagar/").content.decode()
    assert proveedor.razon_social in cuentas_pagar
    assert "Parcial" in cuentas_pagar
    assert "3.000" in cuentas_pagar
    assert "5.000" in cuentas_pagar

    inicio = ingresada.get("/").content.decode()
    assert "Cuentas a pagar" in inicio
    assert "Gs. 3.000" in inicio


@pytest.mark.django_db
def test_pago_rechaza_cuota_de_compra_anulada(ingresada):
    cuenta, proveedor, _item = _preparar()
    compra = _confirmar_credito(ingresada, cuenta, proveedor)
    cuota = CompraCuota.objects.get(compra=compra)
    ingresada.post(f"/compras/{compra.pk}/anular/")
    assert Compra.objects.get(pk=compra.pk).estado == EstadoCompra.ANULADA

    ingresada.post(
        "/compras/pagos/nueva/",
        {
            "proveedor": str(proveedor.pk),
            "fecha": timezone.localdate().isoformat(),
            "cuenta": str(cuenta.pk),
            f"aplicar_{cuota.pk}": "8000",
        },
    )

    assert not PagoProveedor.objects.exists()
    _, _, totales = mayor_disponibilidad(cuenta_id=cuenta.pk)
    assert totales["salida"] == Decimal("0")

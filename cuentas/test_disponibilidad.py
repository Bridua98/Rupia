from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook

from compras.models import Compra, CompraDetalle, EstadoCompra, TipoCompra
from cuentas.disponibilidad import mayor_disponibilidad
from cuentas.models import Cuenta
from inventario.models import Item, ItemCategoria, Marca, TasaIva, TipoItem, UnidadMedida
from negocio.models import UnidadNegocio
from ventas.models import EstadoVenta, MedioPago, Venta, VentaDetalle


def _cuenta(descripcion="Caja 01", **extra):
    datos = {"nombre_corto": descripcion[:10].upper().replace(" ", "")}
    datos.update(extra)
    return Cuenta.objects.create(descripcion=descripcion, **datos)


def _item():
    marca, _ = Marca.objects.get_or_create(descripcion="Genérica")
    categoria, _ = ItemCategoria.objects.get_or_create(descripcion="Alimentos")
    unidad, _ = UnidadMedida.objects.get_or_create(
        descripcion="Unidad", defaults={"simbolo": "Un"}
    )
    negocio, _ = UnidadNegocio.objects.get_or_create(
        abreviado="DEP",
        defaults={"descripcion": "Depósito"},
    )
    item = Item.objects.filter(descripcion="Producto disponibilidad").first()
    if item:
        return item
    return Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        unidad_negocio=negocio,
        descripcion="Producto disponibilidad",
        tipo=TipoItem.PRODUCTO,
        activo=True,
        precio=Decimal("10000"),
        tasa_iva=TasaIva.DIEZ,
    )


def _venta(usuario, cuenta, *, fecha, importe, numero, descuento=0):
    item = _item()
    venta = Venta.objects.create(
        fecha=fecha,
        estado=EstadoVenta.COBRADA,
        caja=cuenta,
        cuenta_cobro=cuenta,
        usuario=usuario,
        medio=MedioPago.EFECTIVO,
        descuento=Decimal(descuento),
        numero_completo=numero,
    )
    VentaDetalle.objects.create(
        venta=venta,
        item=item,
        unidad_medida=item.unidad_medida,
        cantidad=Decimal("1"),
        precio=Decimal(importe),
        tasa_iva=TasaIva.DIEZ,
        subtotal=Decimal(importe),
    )
    return venta


def _compra(
    usuario,
    cuenta,
    *,
    fecha,
    importe,
    numero=None,
    tipo=TipoCompra.FACTURA_CONTADO,
    estado=EstadoCompra.CONFIRMADA,
):
    item = _item()
    compra = Compra.objects.create(
        fecha=fecha,
        estado=estado,
        tipo=tipo,
        cuenta=cuenta,
        usuario=usuario,
        numero_completo=numero,
        timbrado="12345678" if tipo != TipoCompra.EGRESO else "",
    )
    CompraDetalle.objects.create(
        compra=compra,
        item=item,
        unidad_medida=item.unidad_medida,
        cantidad=Decimal("1"),
        costo=Decimal(importe),
        tasa_iva=TasaIva.DIEZ,
        subtotal=Decimal(importe),
    )
    return compra


@pytest.mark.django_db
def test_disponibilidad_pide_ingreso(client):
    response = client.get("/cuentas/disponibilidad/")

    assert response.status_code == 302
    assert response.url.startswith("/login/")


@pytest.mark.django_db
def test_menu_muestra_disponibilidad(ingresada):
    response = ingresada.get("/")

    content = response.content.decode()
    assert response.status_code == 200
    assert 'href="/cuentas/disponibilidad/"' in content
    assert "Disponibilidad" in content


@pytest.mark.django_db
def test_venta_entra_en_el_debe(ingresada, usuario):
    caja = _cuenta()
    _venta(usuario, caja, fecha=date(2026, 11, 4), importe="15000", numero="001-001-0000001")

    response = ingresada.get("/cuentas/disponibilidad/")

    content = response.content.decode()
    assert response.status_code == 200
    assert "001-001-0000001" in content
    assert "Venta" in content
    assert "15.000" in content
    assert "Caja 01" in content
    totales = content.split("sheet-total")[1]
    assert "15.000" in totales
    assert totales.count("15.000") >= 2


@pytest.mark.django_db
def test_detalle_totaliza_saldo(ingresada, usuario):
    caja = _cuenta()
    _venta(usuario, caja, fecha=date(2026, 11, 4), importe="10000", numero="001-001-0000001")
    _compra(
        usuario,
        caja,
        fecha=date(2026, 11, 4),
        importe="3000",
        numero="001-001-0000200",
    )

    response = ingresada.get("/cuentas/disponibilidad/")

    content = response.content.decode()
    totales = content.split("sheet-total")[1]
    assert "7.000" in totales


@pytest.mark.django_db
def test_compra_contado_entra_en_el_haber(ingresada, usuario):
    caja = _cuenta()
    _compra(
        usuario,
        caja,
        fecha=date(2026, 11, 4),
        importe="8000",
        numero="001-001-0000099",
    )

    response = ingresada.get("/cuentas/disponibilidad/")

    content = response.content.decode()
    assert response.status_code == 200
    assert "001-001-0000099" in content
    assert "Compra" in content
    assert "8.000" in content


@pytest.mark.django_db
def test_egreso_usa_numero_de_egreso(ingresada, usuario):
    caja = _cuenta()
    egreso = _compra(
        usuario,
        caja,
        fecha=date(2026, 11, 4),
        importe="3000",
        tipo=TipoCompra.EGRESO,
    )

    response = ingresada.get("/cuentas/disponibilidad/")

    content = response.content.decode()
    assert f"Egreso {egreso.pk}" in content
    assert "Egreso" in content


@pytest.mark.django_db
def test_credito_y_anuladas_no_entran(ingresada, usuario):
    caja = _cuenta()
    _compra(
        usuario,
        caja,
        fecha=date(2026, 11, 4),
        importe="5000",
        numero="001-001-0000100",
        tipo=TipoCompra.FACTURA_CREDITO,
    )
    _compra(
        usuario,
        caja,
        fecha=date(2026, 11, 4),
        importe="4000",
        numero="001-001-0000101",
        estado=EstadoCompra.ANULADA,
    )
    venta = _venta(usuario, caja, fecha=date(2026, 11, 4), importe="2000", numero="001-001-0000002")
    venta.estado = EstadoVenta.ANULADA
    venta.save(update_fields=["estado"])

    response = ingresada.get("/cuentas/disponibilidad/")

    content = response.content.decode()
    assert "001-001-0000100" not in content
    assert "001-001-0000101" not in content
    assert "001-001-0000002" not in content
    assert "No hay movimientos para los filtros elegidos." in content


@pytest.mark.django_db
def test_saldo_anterior_y_saldo_corrido(usuario):
    caja = _cuenta()
    _venta(usuario, caja, fecha=date(2026, 10, 30), importe="10000", numero="001-001-0000001")
    _compra(
        usuario,
        caja,
        fecha=date(2026, 11, 4),
        importe="3000",
        numero="001-001-0000200",
    )

    detalle, resumen, totales = mayor_disponibilidad(fecha_desde=date(2026, 11, 1))

    assert detalle[0].es_saldo_anterior
    assert detalle[0].comprobante == "Saldo anterior"
    assert detalle[0].saldo == Decimal("10000")
    assert detalle[1].comprobante == "001-001-0000200"
    assert detalle[1].haber == Decimal("3000")
    assert detalle[1].saldo == Decimal("7000")
    assert totales["debe"] == Decimal("0")
    assert totales["haber"] == Decimal("3000")
    assert totales["saldo_anterior"] == Decimal("10000")
    assert totales["saldo"] == Decimal("7000")
    assert resumen[0].saldo_anterior == Decimal("10000")
    assert resumen[0].saldo == Decimal("7000")


@pytest.mark.django_db
def test_filtro_cuenta(ingresada, usuario):
    caja = _cuenta("Caja A")
    banco = _cuenta(
        "Banco B",
        es_banco=True,
        numero="123",
        nombre_corto="BANCO",
    )
    _venta(usuario, caja, fecha=date(2026, 11, 4), importe="1000", numero="001-001-0000001")
    _venta(usuario, banco, fecha=date(2026, 11, 4), importe="5000", numero="001-001-0000002")

    response = ingresada.get(f"/cuentas/disponibilidad/?cuenta={caja.pk}")

    content = response.content.decode()
    assert "001-001-0000001" in content
    assert "001-001-0000002" not in content
    assert "Caja A" in content


@pytest.mark.django_db
def test_resumen_por_cuentas(ingresada, usuario):
    caja = _cuenta("Caja A")
    banco = _cuenta(
        "Banco B",
        es_banco=True,
        numero="123",
        nombre_corto="BANCO",
    )
    _venta(usuario, caja, fecha=date(2026, 11, 4), importe="10000", numero="001-001-0000001")
    _compra(
        usuario,
        banco,
        fecha=date(2026, 11, 4),
        importe="4000",
        numero="001-001-0000300",
    )

    response = ingresada.get("/cuentas/disponibilidad/?vista=cuenta")

    content = response.content.decode()
    assert response.status_code == 200
    assert "Por cuenta" in content
    assert "Caja A" in content
    assert "Banco B" in content
    assert "001-001-0000001" not in content
    assert "2 cuentas" in content
    totales = content.split("sheet-total")[1]
    assert "10.000" in totales
    assert "4.000" in totales


@pytest.mark.django_db
def test_excel_incluye_fila_total(ingresada, usuario):
    caja = _cuenta()
    _venta(usuario, caja, fecha=date(2026, 11, 4), importe="12000", numero="001-001-0000001")

    response = ingresada.get("/cuentas/disponibilidad/exportar.xlsx")

    assert response.status_code == 200
    libro = load_workbook(BytesIO(response.content))
    hoja = libro.active
    ultima = hoja.max_row
    assert hoja.cell(ultima, 1).value == "Total"
    assert hoja.cell(2, 3).value == "001-001-0000001"
    assert "Gs. 12.000" in str(hoja.cell(2, 5).value)
    assert "Gs. 12.000" in str(hoja.cell(ultima, 5).value)
    assert "Gs. 12.000" in str(hoja.cell(ultima, 7).value)

from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook

from compras.models import Compra, CompraDetalle, EstadoCompra, TipoCompra
from cuentas.disponibilidad import mayor_disponibilidad
from cuentas.models import Cuenta, EstadoTransferencia, Transferencia
from inventario.models import Item, ItemCategoria, Marca, TasaIva, TipoItem, UnidadMedida
from negocio.models import UnidadNegocio
from ventas.models import EstadoVenta, MedioPago, Venta, VentaDetalle

PERIODO = "fecha_desde=2026-11-01&fecha_hasta=2026-11-30"


def _disponibilidad(extra=""):
    if extra:
        return f"/cuentas/disponibilidad/?{PERIODO}&{extra}"
    return f"/cuentas/disponibilidad/?{PERIODO}"


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

    response = ingresada.get(_disponibilidad())

    content = response.content.decode()
    assert response.status_code == 200
    assert "Entra" in content
    assert "Salida" in content
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

    response = ingresada.get(_disponibilidad())

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

    response = ingresada.get(_disponibilidad())

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

    response = ingresada.get(_disponibilidad())

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

    response = ingresada.get(_disponibilidad())

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
    assert detalle[0].entra == Decimal("10000")
    assert detalle[0].salida == Decimal("0")
    assert detalle[1].salida == Decimal("3000")
    assert detalle[1].saldo == Decimal("7000")
    assert totales["entra"] == Decimal("0")
    assert totales["salida"] == Decimal("3000")
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

    response = ingresada.get(_disponibilidad(f"cuenta={caja.pk}"))

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

    response = ingresada.get(_disponibilidad("vista=cuenta"))

    content = response.content.decode()
    assert response.status_code == 200
    assert "Por cuenta" in content
    assert "Caja A" in content
    assert "Banco B" in content
    assert "001-001-0000001" not in content
    assert "Saldo anterior" in content
    assert "2 cuentas" in content
    totales = content.split("sheet-total")[1]
    assert "10.000" in totales
    assert "4.000" in totales


@pytest.mark.django_db
def test_excel_incluye_fila_total(ingresada, usuario):
    caja = _cuenta()
    _venta(usuario, caja, fecha=date(2026, 11, 4), importe="12000", numero="001-001-0000001")

    response = ingresada.get(f"/cuentas/disponibilidad/exportar.xlsx?{PERIODO}")

    assert response.status_code == 200
    libro = load_workbook(BytesIO(response.content))
    hoja = libro.active
    ultima = hoja.max_row
    assert hoja.cell(ultima, 1).value == "Total"
    assert hoja.cell(2, 3).value == "001-001-0000001"
    assert "Gs. 12.000" in str(hoja.cell(2, 5).value)
    assert "Gs. 12.000" in str(hoja.cell(ultima, 5).value)
    assert "Gs. 12.000" in str(hoja.cell(ultima, 7).value)


def _transferencia(usuario, origen, destino, *, fecha, importe, comprobante="", estado=None):
    return Transferencia.objects.create(
        fecha=fecha,
        cuenta_origen=origen,
        cuenta_destino=destino,
        importe=Decimal(importe),
        comprobante=comprobante,
        usuario=usuario,
        estado=estado or EstadoTransferencia.CONFIRMADA,
    )


@pytest.mark.django_db
def test_transferencia_sale_y_entra(ingresada, usuario):
    caja = _cuenta("Caja A")
    banco = _cuenta("Banco B", es_banco=True, numero="123", nombre_corto="BANCO")
    _transferencia(
        usuario,
        caja,
        banco,
        fecha=date(2026, 11, 4),
        importe="7000",
        comprobante="DEP-99",
    )

    response = ingresada.get(_disponibilidad())
    content = response.content.decode()
    assert "DEP-99" in content
    assert "Transferencia" in content
    assert content.count("DEP-99") == 2
    totales = content.split("sheet-total")[1]
    assert "7.000" in totales
    assert totales.count("7.000") >= 2

    detalle, resumen, totales = mayor_disponibilidad()
    por_cuenta = {fila.cuenta: fila for fila in resumen}
    assert por_cuenta["Caja A"].salida == Decimal("7000")
    assert por_cuenta["Caja A"].entra == Decimal("0")
    assert por_cuenta["Caja A"].saldo == Decimal("-7000")
    assert por_cuenta["Banco B"].entra == Decimal("7000")
    assert por_cuenta["Banco B"].salida == Decimal("0")
    assert por_cuenta["Banco B"].saldo == Decimal("7000")
    assert totales["entra"] == Decimal("7000")
    assert totales["salida"] == Decimal("7000")
    assert totales["saldo"] == Decimal("0")


@pytest.mark.django_db
def test_transferencia_anulada_no_entra(ingresada, usuario):
    caja = _cuenta("Caja A")
    banco = _cuenta("Banco B", es_banco=True, numero="123", nombre_corto="BANCO")
    _transferencia(
        usuario,
        caja,
        banco,
        fecha=date(2026, 11, 4),
        importe="7000",
        comprobante="DEP-ANULA",
        estado=EstadoTransferencia.ANULADA,
    )

    response = ingresada.get(_disponibilidad())
    content = response.content.decode()
    assert "DEP-ANULA" not in content
    assert "No hay movimientos para los filtros elegidos." in content


@pytest.mark.django_db
def test_filtro_cuenta_muestra_un_lado_de_la_transferencia(ingresada, usuario):
    caja = _cuenta("Caja A")
    banco = _cuenta("Banco B", es_banco=True, numero="123", nombre_corto="BANCO")
    _transferencia(
        usuario,
        caja,
        banco,
        fecha=date(2026, 11, 4),
        importe="5000",
        comprobante="DEP-50",
    )

    response = ingresada.get(_disponibilidad(f"cuenta={caja.pk}"))
    content = response.content.decode()
    assert "DEP-50" in content
    assert content.count("DEP-50") == 1
    assert "Caja A" in content


@pytest.mark.django_db
def test_sin_fechas_no_muestra_movimientos(ingresada, usuario):
    caja = _cuenta()
    _venta(usuario, caja, fecha=date(2026, 11, 4), importe="15000", numero="001-001-0000001")

    response = ingresada.get("/cuentas/disponibilidad/")

    content = response.content.decode()
    assert "Elegí las fechas desde y hasta" in content
    assert "001-001-0000001" not in content
    assert 'name="fecha_desde"' in content
    assert "required" in content


@pytest.mark.django_db
def test_agrupado_muestra_saldo_anterior_por_cuenta(ingresada, usuario):
    caja = _cuenta("Caja A")
    banco = _cuenta("Banco B", es_banco=True, numero="123", nombre_corto="BANCO")
    _venta(usuario, caja, fecha=date(2026, 10, 30), importe="10000", numero="001-001-0000001")
    _venta(usuario, banco, fecha=date(2026, 10, 20), importe="2000", numero="001-001-0000002")
    _compra(
        usuario,
        caja,
        fecha=date(2026, 11, 4),
        importe="3000",
        numero="001-001-0000200",
    )

    response = ingresada.get(_disponibilidad("vista=cuenta"))

    content = response.content.decode()
    assert "Saldo anterior" in content
    assert "Caja A" in content
    assert "Banco B" in content
    assert "001-001-0000001" not in content
    assert "10.000" in content
    assert "2.000" in content
    assert "7.000" in content


@pytest.mark.django_db
def test_comprobante_abre_el_registro_de_origen(ingresada, usuario):
    caja = _cuenta()
    banco = _cuenta("Banco B", es_banco=True, numero="123", nombre_corto="BANCO")
    venta = _venta(
        usuario, caja, fecha=date(2026, 11, 4), importe="15000", numero="001-001-0000001"
    )
    compra = _compra(
        usuario,
        caja,
        fecha=date(2026, 11, 4),
        importe="8000",
        numero="001-001-0000099",
    )
    transferencia = _transferencia(
        usuario,
        caja,
        banco,
        fecha=date(2026, 11, 4),
        importe="1000",
        comprobante="DEP-01",
    )

    content = ingresada.get(_disponibilidad()).content.decode()

    assert f'href="/ventas/?venta={venta.pk}&amp;ver=1"' in content
    assert f'href="/compras/?compra={compra.pk}&amp;ver=1"' in content
    assert f'href="/cuentas/transferencias/?transferencia={transferencia.pk}&amp;ver=1"' in content
    assert "sheet-origen" in content


@pytest.mark.django_db
def test_saldo_anterior_no_tiene_enlace(ingresada, usuario):
    caja = _cuenta()
    _venta(usuario, caja, fecha=date(2026, 10, 30), importe="10000", numero="001-001-0000001")

    content = ingresada.get(_disponibilidad()).content.decode()
    cuerpo = content.split("<tbody>")[1].split("</tbody>")[0]
    fila_anterior = [fila for fila in cuerpo.split("<tr") if "Saldo anterior" in fila][0]

    assert "Saldo anterior" in fila_anterior
    assert "sheet-origen" not in fila_anterior
    assert "href=" not in fila_anterior


@pytest.mark.django_db
def test_saldo_corre_entra_menos_salida(usuario):
    caja = _cuenta()
    _venta(usuario, caja, fecha=date(2026, 11, 2), importe="10000", numero="001-001-0000001")
    _compra(
        usuario,
        caja,
        fecha=date(2026, 11, 4),
        importe="3000",
        numero="001-001-0000200",
    )

    detalle, _, _totales = mayor_disponibilidad(
        fecha_desde=date(2026, 11, 1),
        fecha_hasta=date(2026, 11, 30),
    )

    assert detalle[0].es_saldo_anterior is False
    assert detalle[0].entra == Decimal("10000")
    assert detalle[0].saldo == Decimal("10000")
    assert detalle[1].salida == Decimal("3000")
    assert detalle[1].saldo == Decimal("7000")

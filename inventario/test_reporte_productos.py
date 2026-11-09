from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from django.utils import timezone
from openpyxl import load_workbook

from cuentas.models import Cuenta
from inventario.models import (
    AjusteStock,
    Item,
    ItemCategoria,
    ItemMovimiento,
    Marca,
    TasaIva,
    TipoItem,
    TipoMovimiento,
    UnidadMedida,
)
from negocio.models import UnidadNegocio
from ventas.models import EstadoVenta, MedioPago, Venta


def _unidad_negocio():
    unidad, _ = UnidadNegocio.objects.get_or_create(
        abreviado="DEP",
        defaults={"descripcion": "Depósito central"},
    )
    return unidad


def _producto(descripcion, marca, categoria, unidad):
    return Item.objects.create(
        descripcion=descripcion,
        tipo=TipoItem.PRODUCTO,
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        unidad_negocio=_unidad_negocio(),
        precio=Decimal("1000"),
        tasa_iva=TasaIva.DIEZ,
        activo=True,
    )


def _gasto(descripcion, marca, categoria, unidad):
    return Item.objects.create(
        descripcion=descripcion,
        tipo=TipoItem.GASTO,
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        precio=Decimal("500"),
        tasa_iva=TasaIva.DIEZ,
        activo=True,
    )


def _movimiento(
    item,
    unidad,
    *,
    pk,
    cantidad,
    subtotal,
    fecha=None,
    tipo=TipoMovimiento.VENTA,
    secuencia=None,
):
    return ItemMovimiento.objects.create(
        id=pk,
        item=item,
        unidad_medida=unidad,
        tipo=tipo,
        fecha_movimiento=fecha or timezone.localdate(),
        cantidad=Decimal(cantidad),
        precio=Decimal("1000"),
        costo=Decimal("800"),
        subtotal=Decimal(subtotal),
        secuencia_origen=secuencia,
    )


@pytest.mark.django_db
def test_reporte_pide_ingreso(client):
    response = client.get("/inventario/reportes/productos/")

    assert response.status_code == 302
    assert response.url.startswith("/login/")


@pytest.mark.django_db
def test_menu_muestra_reporte(ingresada):
    response = ingresada.get("/")

    assert response.status_code == 200
    assert 'href="/inventario/reportes/productos/"' in response.content.decode()
    assert "Reporte de productos" in response.content.decode()


@pytest.mark.django_db
def test_solo_productos_vigentes(ingresada):
    marca = Marca.objects.create(descripcion="M1")
    categoria = ItemCategoria.objects.create(descripcion="C1")
    unidad = UnidadMedida.objects.create(descripcion="Unidad", simbolo="UND")
    producto = _producto("Prod A", marca, categoria, unidad)
    gasto = _gasto("Gasto B", marca, categoria, unidad)
    _movimiento(producto, unidad, pk=1, cantidad="2", subtotal="2000")
    _movimiento(gasto, unidad, pk=2, cantidad="5", subtotal="5000")
    ItemMovimiento.objects.filter(pk=2).update(es_vigente=False)

    response = ingresada.get("/inventario/reportes/productos/")

    content = response.content.decode()
    assert response.status_code == 200
    assert "Prod A" in content
    assert "Gasto B" not in content
    assert "1 movimiento" in content


@pytest.mark.django_db
def test_filtro_marca(ingresada):
    marca_a = Marca.objects.create(descripcion="Alpha")
    marca_b = Marca.objects.create(descripcion="Beta")
    categoria = ItemCategoria.objects.create(descripcion="Cat")
    unidad = UnidadMedida.objects.create(descripcion="Unidad", simbolo="UND")
    prod_a = _producto("Item A", marca_a, categoria, unidad)
    prod_b = _producto("Item B", marca_b, categoria, unidad)
    _movimiento(prod_a, unidad, pk=10, cantidad="1", subtotal="1000")
    _movimiento(prod_b, unidad, pk=11, cantidad="1", subtotal="2000")

    response = ingresada.get(f"/inventario/reportes/productos/?item__marca={marca_a.pk}")

    content = response.content.decode()
    cuerpo = content.split("<tbody>")[1].split("</tbody>")[0]
    assert "Item A" in cuerpo
    assert "Item B" not in cuerpo


@pytest.mark.django_db
def test_agrupado_por_marca_una_fila_y_totales(ingresada):
    marca = Marca.objects.create(descripcion="Unica")
    categoria = ItemCategoria.objects.create(descripcion="Cat")
    unidad = UnidadMedida.objects.create(descripcion="Unidad", simbolo="UND")
    prod_a = _producto("Item A", marca, categoria, unidad)
    prod_b = _producto("Item B", marca, categoria, unidad)
    _movimiento(prod_a, unidad, pk=20, cantidad="2", subtotal="2000")
    _movimiento(prod_b, unidad, pk=21, cantidad="3", subtotal="3000")

    response = ingresada.get("/inventario/reportes/productos/?agrupar=marca")

    content = response.content.decode()
    cuerpo = content.split("<tbody>")[1].split("</tbody>")[0]
    assert response.status_code == 200
    assert "Por marca" in content
    assert "Unica" in cuerpo
    assert "Item A" not in cuerpo
    assert "1 fila" in content
    assert "5" in content
    assert "sheet-total" in content
    assert "Total" in content


@pytest.mark.django_db
def test_imprimir_incluye_totales(ingresada):
    marca = Marca.objects.create(descripcion="M")
    categoria = ItemCategoria.objects.create(descripcion="C")
    unidad = UnidadMedida.objects.create(descripcion="Unidad", simbolo="UND")
    producto = _producto("Prod", marca, categoria, unidad)
    _movimiento(producto, unidad, pk=30, cantidad="4", subtotal="4000")

    response = ingresada.get("/inventario/reportes/productos/imprimir/")

    content = response.content.decode()
    assert response.status_code == 200
    assert "Reporte de productos" in content
    assert "Total" in content
    assert "Prod" in content


@pytest.mark.django_db
def test_excel_incluye_fila_total(ingresada):
    marca = Marca.objects.create(descripcion="M")
    categoria = ItemCategoria.objects.create(descripcion="C")
    unidad = UnidadMedida.objects.create(descripcion="Unidad", simbolo="UND")
    producto = _producto("Prod", marca, categoria, unidad)
    _movimiento(producto, unidad, pk=40, cantidad="2", subtotal="2000")

    response = ingresada.get("/inventario/reportes/productos/exportar.xlsx")

    assert response.status_code == 200
    libro = load_workbook(BytesIO(response.content))
    hoja = libro.active
    ultima = hoja.max_row
    headers = [celda.value for celda in hoja[1]]
    cantidad = headers.index("Cantidad") + 1
    subtotal = headers.index("Subtotal") + 1
    origen = headers.index("Origen") + 1
    assert hoja.cell(ultima, 1).value == "Total"
    assert hoja.cell(2, cantidad).value == "-2"
    assert hoja.cell(2, subtotal).value == "-Gs. 2.000"
    assert hoja.cell(2, origen).value in (None, "")
    assert hoja.cell(ultima, cantidad).value == "-2"
    assert hoja.cell(ultima, subtotal).value == "-Gs. 2.000"


@pytest.mark.django_db
def test_entradas_positivas_salidas_negativas_y_gs_a_la_izquierda(ingresada):
    marca = Marca.objects.create(descripcion="M")
    categoria = ItemCategoria.objects.create(descripcion="C")
    unidad = UnidadMedida.objects.create(descripcion="Unidad", simbolo="UND")
    producto = _producto("Prod Mix", marca, categoria, unidad)
    _movimiento(
        producto,
        unidad,
        pk=50,
        cantidad="5",
        subtotal="5000",
        tipo=TipoMovimiento.COMPRA,
    )
    _movimiento(
        producto,
        unidad,
        pk=51,
        cantidad="2",
        subtotal="2000",
        tipo=TipoMovimiento.VENTA,
    )

    response = ingresada.get("/inventario/reportes/productos/")

    content = response.content.decode()
    assert response.status_code == 200
    assert "valor-gs is-pos" in content
    assert "valor-gs is-neg" in content
    assert "valor-num is-pos" in content
    assert "valor-num is-neg" in content
    assert "rupia-badge is-entrada" in content
    assert "rupia-badge is-salida" in content
    assert 'class="valor-gs-simbolo">Gs.</span>' in content
    assert "5.000" in content
    assert "2.000" in content
    assert "sheet-col-moneda" in content
    assert 'dir="ltr"' in content

    totales = content.split("sheet-total")[1]
    assert "valor-num is-pos" in totales
    assert "3" in totales
    assert "3.000" in totales


@pytest.mark.django_db
def test_agrupado_compensa_entrada_y_salida(ingresada):
    marca = Marca.objects.create(descripcion="Unica")
    categoria = ItemCategoria.objects.create(descripcion="Cat")
    unidad = UnidadMedida.objects.create(descripcion="Unidad", simbolo="UND")
    producto = _producto("Item Mix", marca, categoria, unidad)
    _movimiento(
        producto, unidad, pk=60, cantidad="10", subtotal="10000", tipo=TipoMovimiento.COMPRA
    )
    _movimiento(
        producto, unidad, pk=61, cantidad="4", subtotal="4000", tipo=TipoMovimiento.VENTA
    )

    response = ingresada.get("/inventario/reportes/productos/?agrupar=item")

    content = response.content.decode()
    cuerpo = content.split("<tbody>")[1].split("</tbody>")[0]
    assert "Item Mix" in cuerpo
    assert "valor-num is-pos" in cuerpo
    assert ">6</span>" in cuerpo or ">6<" in cuerpo
    assert "6.000" in content


@pytest.mark.django_db
def test_origen_abre_venta_compra_y_ajuste(ingresada, usuario):
    marca = Marca.objects.create(descripcion="M")
    categoria = ItemCategoria.objects.create(descripcion="C")
    unidad = UnidadMedida.objects.create(descripcion="Unidad", simbolo="UND")
    producto = _producto("Prod Origen", marca, categoria, unidad)
    caja = Cuenta.objects.create(descripcion="Caja origen", nombre_corto="CORIGEN")
    venta = Venta.objects.create(
        fecha=date(2026, 10, 1),
        estado=EstadoVenta.COBRADA,
        caja=caja,
        cuenta_cobro=caja,
        usuario=usuario,
        medio=MedioPago.EFECTIVO,
        numero_completo="001-001-0000777",
    )
    _movimiento(
        producto,
        unidad,
        pk=70,
        cantidad="1",
        subtotal="1000",
        tipo=TipoMovimiento.VENTA,
        secuencia=venta.numero_completo,
    )
    _movimiento(
        producto,
        unidad,
        pk=71,
        cantidad="2",
        subtotal="2000",
        tipo=TipoMovimiento.COMPRA,
        secuencia="C88",
    )
    AjusteStock.objects.create(fecha=date(2026, 10, 1), observacion="Conteo", id=12)
    _movimiento(
        producto,
        unidad,
        pk=72,
        cantidad="3",
        subtotal="3000",
        tipo=TipoMovimiento.AJUSTE_POSITIVO,
        secuencia="A12",
    )

    content = ingresada.get("/inventario/reportes/productos/").content.decode()
    cuerpo = content.split("<tbody>")[1].split("</tbody>")[0]

    assert "Origen" in content
    assert f'href="/ventas/?venta={venta.pk}&amp;ver=1"' in cuerpo
    assert 'href="/compras/?compra=88&amp;ver=1"' in cuerpo
    assert 'href="/inventario/ajustes/?ajuste=12&amp;ver=1"' in cuerpo
    assert "sheet-origen" in cuerpo

    libro = load_workbook(
        BytesIO(ingresada.get("/inventario/reportes/productos/exportar.xlsx").content)
    )
    hoja = libro.active
    headers = [celda.value for celda in hoja[1]]
    origen = headers.index("Origen") + 1
    valores = {hoja.cell(fila, origen).value for fila in range(2, hoja.max_row)}
    assert "001-001-0000777" in valores
    assert "C88" in valores
    assert "A12" in valores
    assert all("<a" not in str(valor or "") for valor in valores)


@pytest.mark.django_db
def test_por_defecto_filtra_el_mes_en_curso(ingresada):
    marca = Marca.objects.create(descripcion="M")
    categoria = ItemCategoria.objects.create(descripcion="C")
    unidad = UnidadMedida.objects.create(descripcion="Unidad", simbolo="UND")
    producto = _producto("Prod periodo", marca, categoria, unidad)
    hoy = timezone.localdate()
    mes_anterior = hoy.replace(day=1) - timedelta(days=1)
    _movimiento(producto, unidad, pk=80, cantidad="1", subtotal="1000", fecha=hoy)
    _movimiento(
        producto, unidad, pk=81, cantidad="9", subtotal="9000", fecha=mes_anterior
    )

    content = ingresada.get("/inventario/reportes/productos/").content.decode()
    cuerpo = content.split("<tbody>")[1].split("</tbody>")[0]
    assert "1.000" in cuerpo
    assert "9.000" not in cuerpo
    assert f'value="{hoy.replace(day=1).isoformat()}"' in content
    assert f'value="{hoy.isoformat()}"' in content

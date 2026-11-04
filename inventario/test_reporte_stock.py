from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook

from inventario.models import (
    Item,
    ItemCategoria,
    ItemMovimiento,
    ItemUnidad,
    Marca,
    RelacionUnidad,
    TasaIva,
    TipoItem,
    TipoMovimiento,
    UnidadMedida,
)
from inventario.reporte_stock import stock_desde_movimientos
from negocio.models import UnidadNegocio




def _unidad_negocio():
    unidad, _ = UnidadNegocio.objects.get_or_create(
        abreviado="DEP",
        defaults={"descripcion": "Depósito central"},
    )
    return unidad


def _producto(descripcion, marca, categoria, unidad, **extra):
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
        **extra,
    )


def _movimiento(item, unidad, *, pk, cantidad, tipo=TipoMovimiento.COMPRA, vigente=True):
    mov = ItemMovimiento.objects.create(
        id=pk,
        item=item,
        unidad_medida=unidad,
        tipo=tipo,
        fecha_movimiento=date(2026, 10, 1),
        cantidad=Decimal(cantidad),
        precio=Decimal("1000"),
        costo=Decimal("800"),
        subtotal=Decimal("1000"),
    )
    if not vigente:
        ItemMovimiento.objects.filter(pk=pk).update(es_vigente=False)
    return mov


@pytest.mark.django_db
def test_reporte_stock_pide_ingreso(client):
    response = client.get("/inventario/reportes/stock/")

    assert response.status_code == 302
    assert response.url.startswith("/login/")


@pytest.mark.django_db
def test_menu_muestra_stock(ingresada):
    response = ingresada.get("/")

    content = response.content.decode()
    assert response.status_code == 200
    assert 'href="/inventario/reportes/stock/"' in content
    assert "Stock" in content


@pytest.mark.django_db
def test_una_fila_por_producto_y_sin_gastos(ingresada):
    marca = Marca.objects.create(descripcion="M1")
    categoria = ItemCategoria.objects.create(descripcion="C1")
    unidad = UnidadMedida.objects.create(descripcion="Unidad", simbolo="UND")
    producto = _producto("Prod A", marca, categoria, unidad)
    Item.objects.create(
        descripcion="Gasto B",
        tipo=TipoItem.GASTO,
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        precio=Decimal("500"),
        tasa_iva=TasaIva.DIEZ,
    )
    _movimiento(producto, unidad, pk=1, cantidad="3")

    response = ingresada.get("/inventario/reportes/stock/")

    content = response.content.decode()
    assert response.status_code == 200
    assert "Prod A" in content
    assert "Gasto B" not in content
    assert 'class="record-count"' in content
    assert "producto" in content
    cuerpo = content.split("<tbody>")[1].split("</tbody>")[0]
    assert cuerpo.count("<tr") == 1


@pytest.mark.django_db
def test_producto_sin_movimientos_muestra_cero(ingresada):
    marca = Marca.objects.create(descripcion="M")
    categoria = ItemCategoria.objects.create(descripcion="C")
    unidad = UnidadMedida.objects.create(descripcion="Unidad", simbolo="UND")
    _producto("Sin movimientos", marca, categoria, unidad)

    response = ingresada.get("/inventario/reportes/stock/")

    content = response.content.decode()
    assert "Sin movimientos" in content
    assert ">0<" in content or "0," in content or ">0," in content


@pytest.mark.django_db
def test_stock_signos_y_conversion(ingresada):
    marca = Marca.objects.create(descripcion="M")
    categoria = ItemCategoria.objects.create(descripcion="C")
    unidad = UnidadMedida.objects.create(descripcion="Unidad", simbolo="un")
    caja = UnidadMedida.objects.create(descripcion="Caja", simbolo="cja")
    item = _producto("Vaso", marca, categoria, unidad)
    ItemUnidad.objects.create(
        item=item,
        unidad_medida=caja,
        relacion=RelacionUnidad.MAYOR,
        valor=Decimal("12"),
    )
    _movimiento(item, unidad, pk=10, cantidad="5", tipo=TipoMovimiento.COMPRA)
    _movimiento(item, caja, pk=11, cantidad="1", tipo=TipoMovimiento.COMPRA)
    _movimiento(item, unidad, pk=12, cantidad="2", tipo=TipoMovimiento.VENTA)

    movimientos = list(
        ItemMovimiento.objects.filter(item=item, es_vigente=True).select_related("unidad_medida")
    )
    stock, omitidos = stock_desde_movimientos(item, movimientos)
    assert omitidos is False
    assert stock == Decimal("15.000")

    response = ingresada.get("/inventario/reportes/stock/")
    content = response.content.decode()
    assert "15" in content


@pytest.mark.django_db
def test_no_cuenta_movimiento_no_vigente(ingresada):
    marca = Marca.objects.create(descripcion="M")
    categoria = ItemCategoria.objects.create(descripcion="C")
    unidad = UnidadMedida.objects.create(descripcion="Unidad", simbolo="UND")
    item = _producto("Prod", marca, categoria, unidad)
    _movimiento(item, unidad, pk=20, cantidad="10")
    _movimiento(item, unidad, pk=21, cantidad="99", vigente=False)

    response = ingresada.get("/inventario/reportes/stock/")

    content = response.content.decode()
    assert "10" in content
    assert "99" not in content.split("<tbody>")[1].split("</tbody>")[0]


@pytest.mark.django_db
def test_filtro_marca(ingresada):
    marca_a = Marca.objects.create(descripcion="Alpha")
    marca_b = Marca.objects.create(descripcion="Beta")
    categoria = ItemCategoria.objects.create(descripcion="Cat")
    unidad = UnidadMedida.objects.create(descripcion="Unidad", simbolo="UND")
    prod_a = _producto("Item A", marca_a, categoria, unidad)
    prod_b = _producto("Item B", marca_b, categoria, unidad)
    _movimiento(prod_a, unidad, pk=30, cantidad="1")
    _movimiento(prod_b, unidad, pk=31, cantidad="1")

    response = ingresada.get(f"/inventario/reportes/stock/?marca={marca_a.pk}")

    content = response.content.decode()
    cuerpo = content.split("<tbody>")[1].split("</tbody>")[0]
    assert "Item A" in cuerpo
    assert "Item B" not in cuerpo


@pytest.mark.django_db
def test_imprimir_lista_stock(ingresada):
    marca = Marca.objects.create(descripcion="M")
    categoria = ItemCategoria.objects.create(descripcion="C")
    unidad = UnidadMedida.objects.create(descripcion="Unidad", simbolo="UND")
    producto = _producto("Prod", marca, categoria, unidad)
    _movimiento(producto, unidad, pk=40, cantidad="4")

    response = ingresada.get("/inventario/reportes/stock/imprimir/")

    content = response.content.decode()
    assert response.status_code == 200
    assert "Stock" in content
    assert "Prod" in content


@pytest.mark.django_db
def test_excel_exporta_stock(ingresada):
    marca = Marca.objects.create(descripcion="M")
    categoria = ItemCategoria.objects.create(descripcion="C")
    unidad = UnidadMedida.objects.create(descripcion="Unidad", simbolo="UND")
    producto = _producto("Prod", marca, categoria, unidad)
    _movimiento(producto, unidad, pk=50, cantidad="2")

    response = ingresada.get("/inventario/reportes/stock/exportar.xlsx")

    assert response.status_code == 200
    libro = load_workbook(BytesIO(response.content))
    hoja = libro.active
    assert hoja.cell(1, 1).value == "Producto"
    assert hoja.cell(2, 1).value == "Prod"

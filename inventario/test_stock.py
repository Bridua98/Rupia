from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

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
from inventario.stock import (
    cantidad_en_unidad,
    stock_actual,
    stock_desde_movimientos,
    unidades_con_stock,
)
from negocio.models import UnidadNegocio


def _negocio():
    unidad, _ = UnidadNegocio.objects.get_or_create(
        abreviado="DEP",
        defaults={"descripcion": "Depósito central"},
    )
    return unidad


def _producto(*, descripcion="Producto", unidad=None):
    marca = Marca.objects.create(descripcion=f"Marca {descripcion}")
    categoria = ItemCategoria.objects.create(descripcion=f"Categoría {descripcion}")
    if unidad is None:
        unidad = UnidadMedida.objects.create(
            descripcion=f"Unidad {descripcion}",
            simbolo=f"U{descripcion[:3]}",
        )
    return Item.objects.create(
        descripcion=descripcion,
        tipo=TipoItem.PRODUCTO,
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        unidad_negocio=_negocio(),
        precio=Decimal("1500"),
        ultimo_costo=Decimal("1000"),
        tasa_iva=TasaIva.DIEZ,
        activo=True,
    )


def _movimiento(item, unidad, tipo, cantidad, *, pk, vigente=True, secuencia=""):
    movimiento = ItemMovimiento.objects.create(
        id=pk,
        item=item,
        unidad_medida=unidad,
        tipo=tipo,
        fecha_movimiento=date(2026, 10, 1),
        cantidad=Decimal(cantidad),
        precio=Decimal("1500"),
        costo=Decimal("1000"),
        subtotal=Decimal("1500"),
        secuencia_origen=secuencia or None,
        es_vigente=vigente,
    )
    return movimiento


@pytest.mark.django_db
def test_stock_suma_y_resta_segun_el_tipo():
    item = _producto()
    _movimiento(item, item.unidad_medida, TipoMovimiento.COMPRA, "10", pk=1)
    _movimiento(item, item.unidad_medida, TipoMovimiento.AJUSTE_POSITIVO, "2", pk=2)
    _movimiento(item, item.unidad_medida, TipoMovimiento.VENTA, "3", pk=3)
    _movimiento(item, item.unidad_medida, TipoMovimiento.AJUSTE_NEGATIVO, "1", pk=4)

    stock, omitidos = stock_actual(item)

    assert stock == Decimal("8.000")
    assert omitidos is False


@pytest.mark.django_db
def test_stock_convierte_unidades_a_la_base():
    caja = UnidadMedida.objects.create(descripcion="Caja", simbolo="CJA")
    item = _producto(unidad=caja)
    unidad = UnidadMedida.objects.create(descripcion="Unidad", simbolo="UN")
    ItemUnidad.objects.create(
        item=item,
        unidad_medida=unidad,
        relacion=RelacionUnidad.MENOR,
        valor=Decimal("12"),
    )
    _movimiento(item, caja, TipoMovimiento.COMPRA, "2", pk=1)
    _movimiento(item, unidad, TipoMovimiento.COMPRA, "6", pk=2)

    stock, omitidos = stock_actual(item)

    assert stock == Decimal("2.500")
    assert omitidos is False


@pytest.mark.django_db
def test_stock_ignora_movimientos_no_vigentes():
    item = _producto()
    _movimiento(item, item.unidad_medida, TipoMovimiento.COMPRA, "10", pk=1)
    _movimiento(item, item.unidad_medida, TipoMovimiento.COMPRA, "99", pk=2, vigente=False)

    stock, _ = stock_actual(item)

    assert stock == Decimal("10.000")


@pytest.mark.django_db
def test_stock_omite_movimientos_con_unidad_no_relacionada():
    item = _producto()
    otra = UnidadMedida.objects.create(descripcion="Litro", simbolo="L")
    _movimiento(item, item.unidad_medida, TipoMovimiento.COMPRA, "10", pk=1)
    _movimiento(item, otra, TipoMovimiento.COMPRA, "5", pk=2)

    movimientos = item.movimientos.filter(es_vigente=True).select_related("unidad_medida")
    stock, omitidos = stock_desde_movimientos(item, movimientos)

    assert stock == Decimal("10.000")
    assert omitidos is True


@pytest.mark.django_db
def test_stock_actual_excluye_el_ajuste_propio():
    item = _producto()
    _movimiento(item, item.unidad_medida, TipoMovimiento.COMPRA, "10", pk=1)
    _movimiento(
        item,
        item.unidad_medida,
        TipoMovimiento.AJUSTE_POSITIVO,
        "2",
        pk=2,
        secuencia="A7",
    )
    _movimiento(item, item.unidad_medida, TipoMovimiento.VENTA, "1", pk=3)

    total, _ = stock_actual(item)
    sin_ajuste, _ = stock_actual(item, excluir_ajuste_id=7)

    assert total == Decimal("11.000")
    assert sin_ajuste == Decimal("9.000")


@pytest.mark.django_db
def test_cantidad_en_unidad_base_y_vinculadas():
    unidad = UnidadMedida.objects.create(descripcion="Unidad", simbolo="UN")
    caja = UnidadMedida.objects.create(descripcion="Caja", simbolo="CJA")
    gramo = UnidadMedida.objects.create(descripcion="Gramo", simbolo="G")
    item = _producto(unidad=unidad)
    ItemUnidad.objects.create(
        item=item,
        unidad_medida=caja,
        relacion=RelacionUnidad.MAYOR,
        valor=Decimal("12"),
    )
    ItemUnidad.objects.create(
        item=item,
        unidad_medida=gramo,
        relacion=RelacionUnidad.MENOR,
        valor=Decimal("1000"),
    )

    assert cantidad_en_unidad(item, unidad, Decimal("24")) == Decimal("24.000")
    assert cantidad_en_unidad(item, caja, Decimal("24")) == Decimal("2.000")
    assert cantidad_en_unidad(item, gramo, Decimal("0.300")) == Decimal("300.000")


@pytest.mark.django_db
def test_cantidad_en_unidad_rechaza_unidad_no_relacionada():
    item = _producto()
    otra = UnidadMedida.objects.create(descripcion="Litro", simbolo="L")

    with pytest.raises(ValidationError) as error:
        cantidad_en_unidad(item, otra, Decimal("1"))

    assert error.value.code == "sin_relacion"


@pytest.mark.django_db
def test_unidades_con_stock_incluye_base_y_vinculadas():
    caja = UnidadMedida.objects.create(descripcion="Caja", simbolo="CJA")
    item = _producto()
    ItemUnidad.objects.create(
        item=item,
        unidad_medida=caja,
        relacion=RelacionUnidad.MAYOR,
        valor=Decimal("12"),
    )

    filas = unidades_con_stock(item, Decimal("24"))

    assert filas[0]["base"] is True
    assert filas[0]["stock"] == Decimal("24.000")
    assert filas[1]["id"] == caja.pk
    assert filas[1]["stock"] == Decimal("2.000")
    assert filas[1]["aviso"] == ""

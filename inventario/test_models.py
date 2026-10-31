from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db.models.deletion import RestrictedError

from inventario.models import (
    AjusteStock,
    AjusteStockDetalle,
    Item,
    ItemCategoria,
    ItemMovimiento,
    Marca,
    TasaIva,
    TipoItem,
    TipoMovimiento,
    UnidadMedida,
)


@pytest.fixture
def item():
    unidad = UnidadMedida.objects.create(descripcion="Unidad", simbolo="UND")
    marca = Marca.objects.create(descripcion="Genérica")
    categoria = ItemCategoria.objects.create(descripcion="Alimentos")
    return Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion="Arroz 1kg",
        tipo=TipoItem.PRODUCTO,
        precio=Decimal("8500.000"),
        ultimo_costo=Decimal("7000.000"),
    )


@pytest.mark.django_db
def test_item_guarda_relaciones(item):
    item.refresh_from_db()
    assert item.marca.descripcion == "Genérica"
    assert item.categoria.descripcion == "Alimentos"
    assert item.unidad_medida.simbolo == "UND"
    assert item.activo is True
    assert item.precio == Decimal("8500.000")
    assert item.tasa_iva == TasaIva.DIEZ
    assert item.get_tasa_iva_display() == "10%"
    assert str(item) == "Arroz 1kg"


@pytest.mark.django_db
def test_item_rechaza_tipo_desconocido(item):
    item.tipo = "OTRO"
    with pytest.raises(ValidationError):
        item.full_clean()


@pytest.mark.django_db
def test_item_rechaza_tasa_iva_desconocida(item):
    item.tasa_iva = 15
    with pytest.raises(ValidationError):
        item.full_clean()


@pytest.mark.django_db
def test_no_elimina_marca_en_uso(item):
    with pytest.raises(RestrictedError):
        item.marca.delete()


@pytest.mark.django_db
def test_movimiento_y_ajuste_de_stock(item):
    movimiento = ItemMovimiento.objects.create(
        id=1,
        item=item,
        unidad_medida=item.unidad_medida,
        tipo=TipoMovimiento.COMPRA,
        fecha_movimiento=date(2026, 10, 28),
        cantidad=Decimal("10.000"),
        precio=Decimal("7000.000"),
        costo=Decimal("7000.000"),
        subtotal=Decimal("70000.000"),
    )
    ajuste = AjusteStock.objects.create(id=1, fecha="2026-10-28", observacion="Conteo")
    detalle = AjusteStockDetalle.objects.create(
        id=1,
        ajuste=ajuste,
        item=item,
        unidad_medida=item.unidad_medida,
        cantidad_anterior=Decimal("10.000"),
        cantidad_nueva=Decimal("8.000"),
        cantidad=Decimal("-2.000"),
    )

    assert item.movimientos.get() == movimiento
    assert movimiento.get_tipo_display() == "Compra"
    assert list(ajuste.detalles.all()) == [detalle]
    assert str(ajuste) == "Ajuste 1 (2026-10-28)"

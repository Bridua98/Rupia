from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from inventario.models import (
    Item,
    ItemCategoria,
    ItemUnidad,
    Marca,
    RelacionUnidad,
    TipoItem,
    UnidadMedida,
)
from inventario.unidades import convertir_a_base
from negocio.models import UnidadNegocio


def _foraneos(*, simbolo="kg"):
    marca = Marca.objects.create(descripcion="Genérica")
    categoria = ItemCategoria.objects.create(descripcion="Alimentos")
    unidad = UnidadMedida.objects.create(descripcion="Kilogramo", simbolo=simbolo)
    return marca, categoria, unidad


def _item(*, unidad=None, descripcion="Helado"):
    if unidad is None:
        _, _, unidad = _foraneos()
        marca = Marca.objects.get(descripcion="Genérica")
        categoria = ItemCategoria.objects.get(descripcion="Alimentos")
    else:
        marca = Marca.objects.create(descripcion="Genérica")
        categoria = ItemCategoria.objects.create(descripcion="Alimentos")
    return Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion=descripcion,
        tipo=TipoItem.PRODUCTO,
        precio=Decimal("15000"),
    )


def _relacion(item, unidad, relacion, valor):
    return ItemUnidad.objects.create(
        item=item,
        unidad_medida=unidad,
        relacion=relacion,
        valor=Decimal(valor),
    )


def _datos(marca, categoria, unidad, **extra):
    datos = {
        "descripcion": "Helado",
        "tipo": TipoItem.PRODUCTO,
        "marca": marca.pk,
        "categoria": categoria.pk,
        "unidad_medida": unidad.pk,
        "precio": "15000",
        "tasa_iva": "10",
        "activo": "on",
        "accion": "guardar",
        "unidades-TOTAL_FORMS": "1",
        "unidades-INITIAL_FORMS": "0",
        "unidades-MIN_NUM_FORMS": "0",
        "unidades-MAX_NUM_FORMS": "1000",
    }
    if extra.get("tipo", TipoItem.PRODUCTO) == TipoItem.PRODUCTO and "unidad_negocio" not in extra:
        unidad_negocio, _ = UnidadNegocio.objects.get_or_create(
            abreviado="DEP",
            defaults={"descripcion": "Depósito central"},
        )
        extra["unidad_negocio"] = unidad_negocio.pk
    datos.update(extra)
    return datos


def _fila(indice, unidad, relacion, valor, **extra):
    datos = {
        f"unidades-{indice}-unidad_medida": unidad.pk,
        f"unidades-{indice}-relacion": relacion,
        f"unidades-{indice}-valor": valor,
    }
    datos.update(extra)
    return datos


@pytest.mark.django_db
def test_convierte_gramos_a_kilo():
    item = _item()
    gramo = UnidadMedida.objects.create(descripcion="Gramo", simbolo="g")
    _relacion(item, gramo, RelacionUnidad.MENOR, "1000")

    assert convertir_a_base(item, gramo, "300") == Decimal("0.300")


@pytest.mark.django_db
def test_convierte_bolas_a_kilo():
    item = _item()
    bola = UnidadMedida.objects.create(descripcion="Bola", simbolo="bola")
    _relacion(item, bola, RelacionUnidad.MENOR, "20")

    assert convertir_a_base(item, bola, "6") == Decimal("0.300")


@pytest.mark.django_db
def test_convierte_cajas_mayores_a_unidades():
    unidad = UnidadMedida.objects.create(descripcion="Unidad", simbolo="un")
    item = _item(unidad=unidad, descripcion="Vaso")
    caja = UnidadMedida.objects.create(descripcion="Caja", simbolo="cja")
    _relacion(item, caja, RelacionUnidad.MAYOR, "12")

    assert convertir_a_base(item, caja, "2") == Decimal("24.000")


@pytest.mark.django_db
def test_unidad_del_item_no_convierte():
    item = _item()

    assert convertir_a_base(item, item.unidad_medida, "10.5") == Decimal("10.500")


@pytest.mark.django_db
def test_rechaza_unidad_no_relacionada():
    item = _item()
    litro = UnidadMedida.objects.create(descripcion="Litro", simbolo="l")

    with pytest.raises(ValidationError) as error:
        convertir_a_base(item, litro, "1")

    assert error.value.code == "sin_relacion"
    assert "no está relacionada" in error.value.messages[0]


@pytest.mark.django_db
def test_ficha_muestra_unidades_relacionadas(ingresada):
    content = ingresada.get("/inventario/items/?nueva=1").content.decode()

    assert 'data-rupia="tabs"' in content
    assert 'data-tab="datos"' in content
    assert 'id="tab-item-datos"' in content
    assert 'aria-selected="true"' in content
    assert "Unidades relacionadas" in content
    assert "data-unidades-rel" in content
    assert "<table" in content
    assert 'name="unidades-TOTAL_FORMS"' in content
    assert "data-unidades-agregar" in content
    assert 'src="/static/js/rupia-unidades.js"' in content
    assert 'src="/static/js/rupia-tabs.js"' in content
    assert 'src="/static/js/rupia-cantidad.js"' in content
    assert 'data-cantidad="py"' in content
    assert 'data-rupia="selector"' in content


@pytest.mark.django_db
def test_alta_guarda_unidad_relacionada(ingresada):
    marca, categoria, kilo = _foraneos()
    gramo = UnidadMedida.objects.create(descripcion="Gramo", simbolo="g")

    response = ingresada.post(
        "/inventario/items/nueva/",
        _datos(
            marca,
            categoria,
            kilo,
            **_fila(0, gramo, RelacionUnidad.MENOR, "1.000,000"),
        ),
    )

    item = Item.objects.get(descripcion="Helado")
    assert response.status_code == 302
    assert item.unidades.count() == 1
    relacionada = item.unidades.get()
    assert relacionada.unidad_medida_id == gramo.pk
    assert relacionada.relacion == RelacionUnidad.MENOR
    assert relacionada.valor == Decimal("1000.000")


@pytest.mark.django_db
def test_ficha_rechaza_secundaria_igual_a_la_base(ingresada):
    marca, categoria, kilo = _foraneos()

    response = ingresada.post(
        "/inventario/items/nueva/",
        _datos(
            marca,
            categoria,
            kilo,
            **_fila(0, kilo, RelacionUnidad.MENOR, "1000"),
        ),
    )

    assert response.status_code == 200
    assert Item.objects.count() == 0
    assert ItemUnidad.objects.count() == 0
    assert "Esa es la unidad del ítem." in response.content.decode()


@pytest.mark.django_db
def test_ficha_guarda_y_quita_filas(ingresada):
    marca, categoria, kilo = _foraneos()
    gramo = UnidadMedida.objects.create(descripcion="Gramo", simbolo="g")
    bola = UnidadMedida.objects.create(descripcion="Bola", simbolo="bola")
    item = Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=kilo,
        descripcion="Helado",
        tipo=TipoItem.PRODUCTO,
        precio=Decimal("15000"),
    )
    relacionada = _relacion(item, gramo, RelacionUnidad.MENOR, "1000")

    response = ingresada.post(
        f"/inventario/items/{item.pk}/",
        _datos(
            marca,
            categoria,
            kilo,
            **{
                "unidades-TOTAL_FORMS": "2",
                "unidades-INITIAL_FORMS": "1",
                "unidades-0-id": relacionada.pk,
                "unidades-0-unidad_medida": gramo.pk,
                "unidades-0-relacion": RelacionUnidad.MENOR,
                "unidades-0-valor": "1.000,000",
                "unidades-0-DELETE": "on",
                **_fila(1, bola, RelacionUnidad.MENOR, "20,000"),
            },
        ),
    )

    item.refresh_from_db()
    assert response.status_code == 302
    assert item.unidades.count() == 1
    queda = item.unidades.get()
    assert queda.unidad_medida_id == bola.pk
    assert queda.relacion == RelacionUnidad.MENOR
    assert queda.valor == Decimal("20.000")
    assert not ItemUnidad.objects.filter(pk=relacionada.pk).exists()


@pytest.mark.django_db
def test_ficha_muestra_el_valor_con_coma_decimal(ingresada):
    marca, categoria, kilo = _foraneos()
    gramo = UnidadMedida.objects.create(descripcion="Gramo", simbolo="g")
    item = Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=kilo,
        descripcion="Helado",
        tipo=TipoItem.PRODUCTO,
        precio=Decimal("15000"),
    )
    _relacion(item, gramo, RelacionUnidad.MENOR, "1000")

    content = ingresada.get(f"/inventario/items/?item={item.pk}").content.decode()

    assert "1.000" in content
    assert "1.000,000" not in content
    assert 'data-cantidad="py"' in content
    assert "Unidad" in content
    assert 'data-rupia="selector"' in content


@pytest.mark.django_db
def test_ver_muestra_unidades_relacionadas(ingresada):
    marca, categoria, kilo = _foraneos()
    gramo = UnidadMedida.objects.create(descripcion="Gramo", simbolo="g")
    item = Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=kilo,
        descripcion="Helado ver",
        tipo=TipoItem.PRODUCTO,
        precio=Decimal("15000"),
    )
    _relacion(item, gramo, RelacionUnidad.MENOR, "1000")

    content = ingresada.get(f"/inventario/items/?item={item.pk}&ver=1").content.decode()

    assert "view-panel" in content
    assert "Unidades relacionadas" in content
    assert "Historial de precios" in content
    assert "Movimientos" in content or "movimientos" in content.lower()
    assert "Gramo" in content or "g" in content
    assert "Detalles de ajuste" not in content
    assert 'id="panel-form"' not in content

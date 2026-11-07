from decimal import Decimal

import pytest

from inventario.models import (
    Item,
    ItemCategoria,
    ItemPrecioHistorial,
    Marca,
    OrigenPrecio,
    TipoItem,
    UnidadMedida,
)
from inventario.precios import aplicar_ajuste, calcular_precio_nuevo
from negocio.models import UnidadNegocio


def _foraneos():
    marca = Marca.objects.create(descripcion="Genérica")
    categoria = ItemCategoria.objects.create(descripcion="Alimentos")
    unidad = UnidadMedida.objects.create(descripcion="Unidad", simbolo="UND")
    return marca, categoria, unidad


def _item(**extra):
    marca, categoria, unidad = extra.pop("foraneos", None) or _foraneos()
    datos = {
        "marca": marca,
        "categoria": categoria,
        "unidad_medida": unidad,
        "descripcion": extra.pop("descripcion", "Arroz 1kg"),
        "tipo": TipoItem.PRODUCTO,
        "precio": Decimal("8500.000"),
        "ultimo_costo": Decimal("7000.000"),
    }
    datos.update(extra)
    return Item.objects.create(**datos)


def _datos_item(marca, categoria, unidad, **extra):
    datos = {
        "descripcion": "Arroz 1kg",
        "tipo": TipoItem.PRODUCTO,
        "marca": marca.pk,
        "categoria": categoria.pk,
        "unidad_medida": unidad.pk,
        "precio": "8500",
        "tasa_iva": "10",
        "activo": "on",
        "accion": "guardar",
    }
    if extra.get("tipo", TipoItem.PRODUCTO) == TipoItem.PRODUCTO and "unidad_negocio" not in extra:
        unidad_negocio, _ = UnidadNegocio.objects.get_or_create(
            abreviado="DEP",
            defaults={"descripcion": "Depósito central"},
        )
        extra["unidad_negocio"] = unidad_negocio.pk
    datos.update(extra)
    return datos


@pytest.mark.django_db
def test_porcentaje_sobre_precio_actual():
    item = _item()

    calculado = calcular_precio_nuevo(item, Decimal("10"))

    assert calculado.precio_nuevo == Decimal("9350")
    assert calculado.aplica is True


@pytest.mark.django_db
def test_porcentaje_sobre_ultimo_costo():
    item = _item(precio_segun_costo=True)

    calculado = calcular_precio_nuevo(item, Decimal("10"))

    assert calculado.precio_nuevo == Decimal("7700")
    assert calculado.aplica is True


@pytest.mark.django_db
def test_omite_marcado_sin_ultimo_costo():
    item = _item(precio_segun_costo=True, ultimo_costo=None)

    calculado = calcular_precio_nuevo(item, Decimal("10"))

    assert calculado.precio_nuevo is None
    assert calculado.omitido == "Sin último costo"
    assert calculado.aplica is False


@pytest.mark.django_db
def test_omite_sin_precio():
    item = _item(precio=None)

    calculado = calcular_precio_nuevo(item, Decimal("10"))

    assert calculado.precio_nuevo is None
    assert calculado.omitido == "Sin precio"
    assert calculado.aplica is False


@pytest.mark.django_db
def test_redondea_al_guarani():
    item = _item(precio=Decimal("8500.000"))

    calculado = calcular_precio_nuevo(item, Decimal("1.5"))

    assert calculado.precio_nuevo == Decimal("8628")


@pytest.mark.django_db
def test_baja_el_precio():
    item = _item()

    calculado = calcular_precio_nuevo(item, Decimal("-10"))

    assert calculado.precio_nuevo == Decimal("7650")


@pytest.mark.django_db
def test_cero_por_ciento_segun_costo_iguala_el_costo():
    item = _item(precio_segun_costo=True)

    calculado = calcular_precio_nuevo(item, Decimal("0"))

    assert calculado.precio_nuevo == Decimal("7000")
    assert calculado.aplica is True


@pytest.mark.django_db
def test_aplicar_masivo_audita_con_lote(usuario):
    item = _item()

    resultado = aplicar_ajuste(Item.objects.all(), Decimal("10"), usuario)

    item.refresh_from_db()
    cambio = ItemPrecioHistorial.objects.get()
    assert resultado.cambiados == 1
    assert resultado.omitidos == 0
    assert resultado.lote
    assert item.precio == Decimal("9350")
    assert cambio.precio_anterior == Decimal("8500.000")
    assert cambio.precio_nuevo == Decimal("9350")
    assert cambio.porcentaje == Decimal("10.00")
    assert cambio.origen == OrigenPrecio.MASIVO
    assert cambio.usuario == usuario
    assert cambio.lote == resultado.lote
    assert cambio.segun_costo is False


@pytest.mark.django_db
def test_aplicar_omite_sin_escribir(usuario):
    item = _item(precio_segun_costo=True, ultimo_costo=None)

    resultado = aplicar_ajuste(Item.objects.all(), Decimal("10"), usuario)

    item.refresh_from_db()
    assert resultado.cambiados == 0
    assert resultado.omitidos == 1
    assert item.precio == Decimal("8500.000")
    assert ItemPrecioHistorial.objects.count() == 0


@pytest.mark.django_db
def test_pantalla_pide_ingreso(client):
    response = client.get("/inventario/precios/")

    assert response.status_code == 302
    assert response.url.startswith("/login/")


@pytest.mark.django_db
def test_pantalla_lista_activos_y_muestra_el_menu(ingresada):
    foraneos = _foraneos()
    _item(foraneos=foraneos, descripcion="Arroz 1kg")
    _item(foraneos=foraneos, descripcion="Fideos", activo=False)
    _item(foraneos=foraneos, descripcion="Gastos Ande", tipo=TipoItem.GASTO)

    response = ingresada.get("/inventario/precios/")
    content = response.content.decode()

    assert response.status_code == 200
    assert "Arroz 1kg" in content
    assert "Fideos" not in content
    assert "Gastos Ande" not in content
    assert "Precios" in content
    assert "Historial" in content
    assert 'name="porcentaje"' in content
    assert 'name="todos_filtrados"' in content
    assert "precios-stepper-valor" in content
    assert "precios-panel" in content


@pytest.mark.django_db
def test_calcular_muestra_la_vista_previa(ingresada):
    item = _item()

    response = ingresada.post(
        "/inventario/precios/",
        {"porcentaje": "10", "accion": "calcular", "item": str(item.pk)},
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert "9.350" in content
    item.refresh_from_db()
    assert item.precio == Decimal("8500.000")
    assert ItemPrecioHistorial.objects.count() == 0


@pytest.mark.django_db
def test_calcular_marca_omitido_sin_costo(ingresada):
    item = _item(precio_segun_costo=True, ultimo_costo=None)

    response = ingresada.post(
        "/inventario/precios/",
        {"porcentaje": "10", "accion": "calcular", "item": str(item.pk)},
    )

    assert "Sin último costo" in response.content.decode()


@pytest.mark.django_db
def test_aplicar_desde_la_pantalla(ingresada, usuario):
    item = _item()

    response = ingresada.post(
        "/inventario/precios/",
        {"porcentaje": "10", "accion": "aplicar", "item": str(item.pk)},
    )

    item.refresh_from_db()
    cambio = ItemPrecioHistorial.objects.get()
    assert response.status_code == 302
    assert item.precio == Decimal("9350")
    assert cambio.usuario == usuario
    assert cambio.origen == OrigenPrecio.MASIVO

    pagina = ingresada.get(response.url)
    assert "Se actualizó 1 precio." in pagina.content.decode()


@pytest.mark.django_db
def test_aplicar_todos_los_filtrados(ingresada):
    foraneos = _foraneos()
    arroz = _item(foraneos=foraneos, descripcion="Arroz 1kg")
    fideos = _item(foraneos=foraneos, descripcion="Fideos", precio=Decimal("10000.000"))
    _item(foraneos=foraneos, descripcion="Aceite", activo=False, precio=Decimal("4000.000"))
    gasto = _item(foraneos=foraneos, descripcion="Gastos Ande", tipo=TipoItem.GASTO, precio=Decimal("5000.000"))

    response = ingresada.post(
        "/inventario/precios/",
        {"porcentaje": "10", "accion": "aplicar", "todos_filtrados": "on"},
    )

    arroz.refresh_from_db()
    fideos.refresh_from_db()
    aceite = Item.objects.get(descripcion="Aceite")
    gasto.refresh_from_db()
    assert response.status_code == 302
    assert arroz.precio == Decimal("9350")
    assert fideos.precio == Decimal("11000")
    assert aceite.precio == Decimal("4000.000")
    assert gasto.precio == Decimal("5000.000")
    assert ItemPrecioHistorial.objects.count() == 2
    assert ItemPrecioHistorial.objects.values("lote").distinct().count() == 1


@pytest.mark.django_db
def test_aplicar_sin_seleccion_pide_items(ingresada):
    _item()

    response = ingresada.post(
        "/inventario/precios/",
        {"porcentaje": "10", "accion": "aplicar"},
    )

    assert response.status_code == 200
    assert "Elegí al menos un ítem." in response.content.decode()
    assert ItemPrecioHistorial.objects.count() == 0


@pytest.mark.django_db
def test_porcentaje_menos_cien_se_rechaza(ingresada):
    item = _item()

    response = ingresada.post(
        "/inventario/precios/",
        {"porcentaje": "-100", "accion": "aplicar", "item": str(item.pk)},
    )

    item.refresh_from_db()
    assert response.status_code == 200
    assert "El porcentaje tiene que ser mayor a -100." in response.content.decode()
    assert item.precio == Decimal("8500.000")


@pytest.mark.django_db
def test_ficha_audita_el_precio_nuevo(ingresada, usuario):
    marca, categoria, unidad = _foraneos()

    ingresada.post(
        "/inventario/items/nueva/",
        _datos_item(marca, categoria, unidad, precio_segun_costo="on"),
    )

    item = Item.objects.get(descripcion="Arroz 1kg")
    cambio = ItemPrecioHistorial.objects.get()
    assert item.precio_segun_costo is True
    assert cambio.origen == OrigenPrecio.FICHA
    assert cambio.precio_anterior is None
    assert cambio.precio_nuevo == Decimal("8500.000")
    assert cambio.usuario == usuario
    assert cambio.porcentaje is None
    assert cambio.lote is None
    assert cambio.segun_costo is True


@pytest.mark.django_db
def test_ficha_no_audita_si_el_precio_no_cambia(ingresada):
    marca, categoria, unidad = _foraneos()
    item = _item(foraneos=(marca, categoria, unidad))

    ingresada.post(
        f"/inventario/items/{item.pk}/",
        _datos_item(marca, categoria, unidad, descripcion="Arroz 2kg"),
    )

    item.refresh_from_db()
    assert item.descripcion == "Arroz 2kg"
    assert ItemPrecioHistorial.objects.count() == 0


@pytest.mark.django_db
def test_ficha_audita_el_cambio_de_precio(ingresada):
    marca, categoria, unidad = _foraneos()
    item = _item(foraneos=(marca, categoria, unidad))

    ingresada.post(
        f"/inventario/items/{item.pk}/",
        _datos_item(marca, categoria, unidad, precio="9000"),
    )

    item.refresh_from_db()
    cambio = ItemPrecioHistorial.objects.get()
    assert item.precio == Decimal("9000.000")
    assert cambio.origen == OrigenPrecio.FICHA
    assert cambio.precio_anterior == Decimal("8500.000")
    assert cambio.precio_nuevo == Decimal("9000.000")


@pytest.mark.django_db
def test_ficha_muestra_la_casilla_segun_costo(ingresada):
    response = ingresada.get("/inventario/items/?nueva=1")

    content = response.content.decode()
    assert 'name="precio_segun_costo"' in content
    assert "Modificar precio según último costo" in content


@pytest.mark.django_db
def test_historial_lista_los_cambios(ingresada, usuario):
    item = _item()
    aplicar_ajuste(Item.objects.filter(pk=item.pk), Decimal("10"), usuario)

    response = ingresada.get("/inventario/precios/historial/")
    content = response.content.decode()

    assert response.status_code == 200
    assert "Arroz 1kg" in content
    assert "ada" in content
    assert "Masivo" in content
    assert "9.350" in content

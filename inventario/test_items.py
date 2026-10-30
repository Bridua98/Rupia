from datetime import date
from decimal import Decimal

import pytest

from inventario.models import (
    Item,
    ItemCategoria,
    ItemMovimiento,
    Marca,
    TipoItem,
    TipoMovimiento,
    UnidadMedida,
)


@pytest.fixture
def usuario(django_user_model):
    return django_user_model.objects.create_user(
        "ada",
        "ada@rupia.local",
        "Clave-inicial-Rupia-2026",
    )


@pytest.fixture
def ingresada(client, usuario):
    client.force_login(usuario)
    return client


def _foraneos():
    marca = Marca.objects.create(descripcion="Genérica")
    categoria = ItemCategoria.objects.create(descripcion="Alimentos")
    unidad = UnidadMedida.objects.create(descripcion="Unidad", simbolo="UND")
    return marca, categoria, unidad


def _datos(marca, categoria, unidad, **extra):
    datos = {
        "descripcion": "Arroz 1kg",
        "tipo": TipoItem.PRODUCTO,
        "marca": marca.pk,
        "categoria": categoria.pk,
        "unidad_medida": unidad.pk,
        "precio": "8500",
        "activo": "on",
        "accion": "guardar",
    }
    datos.update(extra)
    return datos


@pytest.mark.django_db
def test_selector_pide_ingreso(client):
    response = client.get("/selector/marca/")

    assert response.status_code == 302
    assert response.url.startswith("/login/")


@pytest.mark.django_db
def test_selector_desconocido_no_existe(ingresada):
    response = ingresada.get("/selector/no-existe/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_selector_filtra_por_descripcion(ingresada):
    Marca.objects.create(descripcion="Alfa")
    Marca.objects.create(descripcion="Beta")

    response = ingresada.get("/selector/marca/?q=Alf")

    labels = [row["label"] for row in response.json()["results"]]
    assert labels == ["Alfa"]


@pytest.mark.django_db
def test_selector_filtra_unidad_por_simbolo(ingresada):
    UnidadMedida.objects.create(descripcion="Kilogramo", simbolo="kg")
    UnidadMedida.objects.create(descripcion="Metro", simbolo="m")

    response = ingresada.get("/selector/unidad/?q=kg")

    assert response.json()["results"] == [
        {"id": UnidadMedida.objects.get(simbolo="kg").pk, "label": "Kilogramo (kg)"},
    ]


@pytest.mark.django_db
def test_selector_rechaza_alta_invalida(ingresada):
    response = ingresada.post("/selector/marca/nueva/", {"marca-descripcion": "   "})

    assert response.status_code == 400
    assert response.json()["errors"]["marca-descripcion"] == ["Escribí la descripción."]
    assert Marca.objects.count() == 0


@pytest.mark.django_db
def test_selector_no_repite_la_marca(ingresada):
    Marca.objects.create(descripcion="Colón")

    response = ingresada.post("/selector/marca/nueva/", {"marca-descripcion": "Colón"})

    assert response.status_code == 400
    assert response.json()["errors"]["marca-descripcion"] == [
        "Ya hay una marca con esa descripción.",
    ]
    assert Marca.objects.count() == 1


@pytest.mark.django_db
def test_selector_crea_y_devuelve_el_registro(ingresada):
    response = ingresada.post("/selector/marca/nueva/", {"marca-descripcion": "Colón"})

    assert response.status_code == 200
    data = response.json()
    marca = Marca.objects.get(descripcion="Colón")
    assert data == {"id": marca.pk, "label": "Colón"}


@pytest.mark.django_db
def test_ficha_ofrece_el_selector_con_alta(ingresada):
    response = ingresada.get("/inventario/items/nueva/")

    content = response.content.decode()
    assert response.status_code == 200
    assert 'data-rupia="selector"' in content
    assert 'data-search-url="/selector/marca/"' in content
    assert 'data-create-url="/selector/marca/nueva/"' in content
    assert 'class="selector-nueva"' in content
    assert 'aria-label="Nueva marca"' in content
    assert 'name="marca-descripcion"' in content
    assert "Nueva categoría" in content
    assert "Nueva unidad" in content
    assert 'value="PRODUCTO" selected' in content


@pytest.mark.django_db
def test_alta_de_item_con_foraneos_existentes(ingresada):
    marca, categoria, unidad = _foraneos()

    response = ingresada.post(
        "/inventario/items/nueva/",
        _datos(marca, categoria, unidad),
    )

    item = Item.objects.get(descripcion="Arroz 1kg")
    assert item.marca_id == marca.pk
    assert item.categoria_id == categoria.pk
    assert item.unidad_medida_id == unidad.pk
    assert item.tipo == TipoItem.PRODUCTO
    assert item.precio == Decimal("8500.000")
    assert item.activo is True
    assert response.status_code == 302
    assert response.url == f"/inventario/items/?item={item.pk}"
    pagina = ingresada.get(response.url)
    contenido = pagina.content.decode()
    assert pagina.status_code == 200
    assert "Arroz 1kg" in contenido
    assert "Producto" in contenido
    assert "Genérica" in contenido


@pytest.mark.django_db
def test_no_repite_la_descripcion_del_item(ingresada):
    marca, categoria, unidad = _foraneos()
    Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion="Arroz 1kg",
        tipo=TipoItem.PRODUCTO,
    )

    response = ingresada.post(
        "/inventario/items/nueva/",
        _datos(marca, categoria, unidad),
    )

    assert response.status_code == 200
    assert "Ya hay un ítem con esa descripción." in response.content.decode()
    assert Item.objects.count() == 1


@pytest.mark.django_db
def test_alta_sin_marca_no_graba(ingresada):
    marca, categoria, unidad = _foraneos()
    datos = _datos(marca, categoria, unidad)
    datos["marca"] = ""

    response = ingresada.post("/inventario/items/nueva/", datos)

    assert response.status_code == 200
    assert "Elegí una marca." in response.content.decode()
    assert Item.objects.count() == 0


@pytest.mark.django_db
def test_alta_usa_la_marca_creada_en_el_selector(ingresada):
    marca, categoria, unidad = _foraneos()
    creada = ingresada.post("/selector/marca/nueva/", {"marca-descripcion": "Molinos"})
    marca_id = creada.json()["id"]
    datos = _datos(marca, categoria, unidad)
    datos["marca"] = marca_id

    response = ingresada.post("/inventario/items/nueva/", datos)

    item = Item.objects.get(descripcion="Arroz 1kg")
    assert item.marca.descripcion == "Molinos"
    assert response.status_code == 302
    assert response.url == f"/inventario/items/?item={item.pk}"


@pytest.mark.django_db
def test_edicion_conserva_los_foraneos(ingresada):
    marca, categoria, unidad = _foraneos()
    item = Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion="Arroz 1kg",
        tipo=TipoItem.PRODUCTO,
        precio=Decimal("8500.000"),
    )

    response = ingresada.post(
        f"/inventario/items/{item.pk}/",
        _datos(marca, categoria, unidad, descripcion="Arroz 2kg"),
    )

    item.refresh_from_db()
    assert item.descripcion == "Arroz 2kg"
    assert item.marca_id == marca.pk
    assert item.categoria_id == categoria.pk
    assert item.unidad_medida_id == unidad.pk
    assert response.status_code == 302


@pytest.mark.django_db
def test_no_elimina_item_con_movimiento(ingresada):
    marca, categoria, unidad = _foraneos()
    item = Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion="Arroz 1kg",
        tipo=TipoItem.PRODUCTO,
    )
    ItemMovimiento.objects.create(
        id=1,
        item=item,
        unidad_medida=unidad,
        tipo=TipoMovimiento.COMPRA,
        fecha_movimiento=date(2026, 10, 30),
        cantidad=Decimal("1.000"),
        precio=Decimal("8500.000"),
        costo=Decimal("6000.000"),
        subtotal=Decimal("8500.000"),
    )

    response = ingresada.post(f"/inventario/items/{item.pk}/eliminar/")

    assert response.status_code == 302
    assert response.url == f"/inventario/items/{item.pk}/"
    assert Item.objects.filter(pk=item.pk).exists()
    ficha = ingresada.get(response.url)
    assert "está en uso y no se puede eliminar." in ficha.content.decode()


@pytest.mark.django_db
def test_el_menu_muestra_items(ingresada):
    response = ingresada.get("/")

    content = response.content.decode()
    assert 'href="/inventario/items/"' in content
    assert "Ítems" in content

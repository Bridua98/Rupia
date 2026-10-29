from decimal import Decimal

import pytest
from django.urls import reverse

from inventario.models import Item, ItemCategoria, Marca, TipoItem, UnidadMedida


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


@pytest.mark.django_db
def test_listado_pide_ingreso(client):
    response = client.get("/inventario/marcas/")

    assert response.status_code == 302
    assert response.url.startswith("/login/")


@pytest.mark.django_db
def test_el_menu_muestra_marcas(ingresada):
    response = ingresada.get("/")

    assert response.status_code == 200
    content = response.content.decode()
    assert 'href="/inventario/marcas/"' in content
    assert "Hola, ada." in content


@pytest.mark.django_db
def test_listado_marca_la_primera_fila(ingresada):
    Marca.objects.create(descripcion="Beta")
    alfa = Marca.objects.create(descripcion="Alfa")

    response = ingresada.get("/inventario/marcas/")

    content = response.content.decode()
    assert response.status_code == 200
    assert content.index("Alfa") < content.index("Beta")
    selected = next(part for part in content.split("<tr") if 'aria-selected="true"' in part)
    assert f'data-id="{alfa.pk}"' in selected
    assert "Nueva marca" in content
    assert 'href="/"' in content
    assert "Volver" in content
    assert 'aria-label="Acciones"' in content
    assert "Modificar" in content
    assert "2 registros" in content
    assert "Flechas para moverse" in content


@pytest.mark.django_db
def test_listado_marca_la_fila_pedida(ingresada):
    beta = Marca.objects.create(descripcion="Beta")
    Marca.objects.create(descripcion="Alfa")

    response = ingresada.get(f"/inventario/marcas/?marca={beta.pk}")

    selected = next(
        part
        for part in response.content.decode().split("<tr")
        if 'aria-selected="true"' in part
    )
    assert f'data-id="{beta.pk}"' in selected
    assert 'class="detail-panel"' in response.content.decode()
    assert "Abrir ficha" in response.content.decode()
    assert f'href="/inventario/marcas/{beta.pk}/"' in response.content.decode()
    assert 'aria-label="Cerrar"' in response.content.decode()


@pytest.mark.django_db
def test_alta_vuelve_al_listado(ingresada):
    response = ingresada.post(
        "/inventario/marcas/nueva/",
        {"descripcion": "Colón", "accion": "guardar"},
    )

    marca = Marca.objects.get(descripcion="Colón")
    assert response.status_code == 302
    assert response.url == f"/inventario/marcas/?marca={marca.pk}"


@pytest.mark.django_db
def test_descripcion_vacia_no_graba(ingresada):
    response = ingresada.post(
        "/inventario/marcas/nueva/",
        {"descripcion": "   ", "accion": "guardar"},
    )

    assert response.status_code == 200
    assert "Escribí la descripción." in response.content.decode()
    assert Marca.objects.count() == 0


@pytest.mark.django_db
def test_edicion_guarda_cambios(ingresada):
    marca = Marca.objects.create(descripcion="Colón")

    response = ingresada.post(
        f"/inventario/marcas/{marca.pk}/",
        {"descripcion": "Colón Norte", "accion": "guardar"},
    )

    marca.refresh_from_db()
    assert marca.descripcion == "Colón Norte"
    assert response.status_code == 302
    assert response.url == f"/inventario/marcas/?marca={marca.pk}"


@pytest.mark.django_db
def test_guardar_y_seguir_abre_otra_ficha(ingresada):
    response = ingresada.post(
        "/inventario/marcas/nueva/",
        {"descripcion": "Molinos", "accion": "seguir"},
    )

    assert response.status_code == 302
    assert response.url == reverse("marca_create")
    assert Marca.objects.filter(descripcion="Molinos").exists()

    marca = Marca.objects.get(descripcion="Molinos")
    seguido = ingresada.post(
        f"/inventario/marcas/{marca.pk}/",
        {"descripcion": "Molinos SA", "accion": "seguir"},
    )

    marca.refresh_from_db()
    assert marca.descripcion == "Molinos SA"
    assert seguido.status_code == 302
    assert seguido.url == "/inventario/marcas/nueva/"


@pytest.mark.django_db
def test_ficha_nueva_no_ofrece_eliminar(ingresada):
    response = ingresada.get("/inventario/marcas/nueva/")

    content = response.content.decode()
    assert response.status_code == 200
    assert "Nueva marca" in content
    assert "Guardar y seguir" in content
    assert "Eliminar" not in content
    assert "Marca anterior" not in content


@pytest.mark.django_db
def test_ficha_muestra_vecinas(ingresada):
    alfa = Marca.objects.create(descripcion="Alfa")
    beta = Marca.objects.create(descripcion="Beta")

    response = ingresada.get(f"/inventario/marcas/{alfa.pk}/")

    content = response.content.decode()
    assert "1 de 2" in content
    assert f'href="/inventario/marcas/{beta.pk}/"' in content
    assert "Eliminar" in content
    assert 'aria-current="page"' in content


@pytest.mark.django_db
def test_elimina_marca(ingresada):
    marca = Marca.objects.create(descripcion="Pulp")

    response = ingresada.post(f"/inventario/marcas/{marca.pk}/eliminar/")

    assert response.status_code == 302
    assert response.url == "/inventario/marcas/"
    assert not Marca.objects.filter(pk=marca.pk).exists()


@pytest.mark.django_db
def test_no_elimina_marca_en_uso(ingresada):
    unidad = UnidadMedida.objects.create(id=1, descripcion="Unidad", simbolo="UND")
    marca = Marca.objects.create(descripcion="Genérica")
    categoria = ItemCategoria.objects.create(descripcion="Alimentos")
    Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion="Arroz 1kg",
        tipo=TipoItem.PRODUCTO,
        precio=Decimal("8500.000"),
    )

    response = ingresada.post(f"/inventario/marcas/{marca.pk}/eliminar/")

    assert response.status_code == 302
    assert response.url == f"/inventario/marcas/{marca.pk}/"
    assert Marca.objects.filter(pk=marca.pk).exists()
    ficha = ingresada.get(response.url)
    assert "está en uso y no se puede eliminar." in ficha.content.decode()


@pytest.mark.django_db
def test_buscar_filtra_el_listado(ingresada):
    Marca.objects.create(descripcion="Alfa")
    Marca.objects.create(descripcion="Beta")

    response = ingresada.get("/inventario/marcas/?q=Alf")

    content = response.content.decode()
    assert response.status_code == 200
    assert "Alfa" in content
    assert "Beta" not in content
    assert "1 registro" in content


@pytest.mark.django_db
def test_alta_desde_el_listado_conserva_el_error(ingresada):
    response = ingresada.post(
        "/inventario/marcas/nueva/",
        {"descripcion": "   ", "accion": "guardar", "desde": "listado"},
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert "Escribí la descripción." in content
    assert 'class="detail-panel"' in content
    assert Marca.objects.count() == 0

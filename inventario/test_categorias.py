from decimal import Decimal
from io import BytesIO

import pytest
from django.urls import reverse
from openpyxl import load_workbook
from pypdf import PdfReader

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
    response = client.get("/inventario/categorias/")

    assert response.status_code == 302
    assert response.url.startswith("/login/")


@pytest.mark.django_db
def test_el_menu_muestra_categorias(ingresada):
    response = ingresada.get("/")

    assert response.status_code == 200
    content = response.content.decode()
    assert 'href="/inventario/categorias/"' in content
    assert "Hola, ada." in content


@pytest.mark.django_db
def test_listado_marca_la_primera_fila(ingresada):
    ItemCategoria.objects.create(descripcion="Beta")
    alfa = ItemCategoria.objects.create(descripcion="Alfa")

    response = ingresada.get("/inventario/categorias/")

    content = response.content.decode()
    assert response.status_code == 200
    assert content.index("Alfa") < content.index("Beta")
    selected = next(part for part in content.split("<tr") if 'aria-selected="true"' in part)
    assert f'data-id="{alfa.pk}"' in selected
    assert "Nueva categoría" in content
    assert 'aria-label="Imprimir y exportar"' in content
    assert "Imprimir" in content
    assert "Excel" in content
    assert "PDF" in content
    assert 'href="/"' in content
    assert "Volver" in content
    assert 'class="sheet-col-acciones"' in content
    assert 'aria-label="Acciones"' in content
    assert "Modificar" in content
    assert "2 registros" in content
    assert "Flechas para moverse" in content


@pytest.mark.django_db
def test_listado_marca_la_fila_pedida(ingresada):
    beta = ItemCategoria.objects.create(descripcion="Beta")
    ItemCategoria.objects.create(descripcion="Alfa")

    response = ingresada.get(f"/inventario/categorias/?categoria={beta.pk}")

    selected = next(
        part for part in response.content.decode().split("<tr") if 'aria-selected="true"' in part
    )
    assert f'data-id="{beta.pk}"' in selected
    assert 'class="detail-panel"' in response.content.decode()
    assert "Abrir ficha" in response.content.decode()
    assert f'href="/inventario/categorias/{beta.pk}/"' in response.content.decode()
    assert 'aria-label="Cerrar"' in response.content.decode()


@pytest.mark.django_db
def test_alta_vuelve_al_listado(ingresada):
    response = ingresada.post(
        "/inventario/categorias/nueva/",
        {"descripcion": "Alimentos", "accion": "guardar"},
    )

    categoria = ItemCategoria.objects.get(descripcion="Alimentos")
    assert response.status_code == 302
    assert response.url == "/inventario/categorias/"
    pagina = ingresada.get(response.url)
    assert 'class="detail-panel"' not in pagina.content.decode()


@pytest.mark.django_db
def test_descripcion_vacia_no_graba(ingresada):
    response = ingresada.post(
        "/inventario/categorias/nueva/",
        {"descripcion": "   ", "accion": "guardar"},
    )

    assert response.status_code == 200
    assert "Escribí la descripción." in response.content.decode()
    assert ItemCategoria.objects.count() == 0


@pytest.mark.django_db
def test_no_repite_la_descripcion(ingresada):
    ItemCategoria.objects.create(descripcion="Alimentos")

    response = ingresada.post(
        "/inventario/categorias/nueva/",
        {"descripcion": "Alimentos", "accion": "guardar"},
    )

    assert response.status_code == 200
    assert "Ya hay una categoría con esa descripción." in response.content.decode()
    assert ItemCategoria.objects.count() == 1


@pytest.mark.django_db
def test_edicion_guarda_cambios(ingresada):
    categoria = ItemCategoria.objects.create(descripcion="Bebidas")

    response = ingresada.post(
        f"/inventario/categorias/{categoria.pk}/",
        {"descripcion": "Bebidas sin alcohol", "accion": "guardar"},
    )

    categoria.refresh_from_db()
    assert categoria.descripcion == "Bebidas sin alcohol"
    assert response.status_code == 302
    assert response.url == "/inventario/categorias/"
    pagina = ingresada.get(response.url)
    assert 'class="detail-panel"' not in pagina.content.decode()


@pytest.mark.django_db
def test_guardar_y_seguir_abre_otra_ficha(ingresada):
    response = ingresada.post(
        "/inventario/categorias/nueva/",
        {"descripcion": "Limpieza", "accion": "seguir"},
    )

    assert response.status_code == 302
    assert response.url == reverse("categoria_create")
    assert ItemCategoria.objects.filter(descripcion="Limpieza").exists()

    categoria = ItemCategoria.objects.get(descripcion="Limpieza")
    seguido = ingresada.post(
        f"/inventario/categorias/{categoria.pk}/",
        {"descripcion": "Limpieza del hogar", "accion": "seguir"},
    )

    categoria.refresh_from_db()
    assert categoria.descripcion == "Limpieza del hogar"
    assert seguido.status_code == 302
    assert seguido.url == "/inventario/categorias/nueva/"


@pytest.mark.django_db
def test_ficha_nueva_no_ofrece_eliminar(ingresada):
    response = ingresada.get("/inventario/categorias/nueva/")

    content = response.content.decode()
    assert response.status_code == 200
    assert "Nueva categoría" in content
    assert "Guardar y seguir" in content
    assert "Eliminar" not in content
    assert "Categoría anterior" not in content


@pytest.mark.django_db
def test_ficha_muestra_vecinas(ingresada):
    alfa = ItemCategoria.objects.create(descripcion="Alfa")
    beta = ItemCategoria.objects.create(descripcion="Beta")

    response = ingresada.get(f"/inventario/categorias/{alfa.pk}/")

    content = response.content.decode()
    assert "1 de 2" in content
    assert f'href="/inventario/categorias/{beta.pk}/"' in content
    assert "Eliminar" in content
    assert 'aria-current="page"' in content


@pytest.mark.django_db
def test_el_menu_de_eliminar_incluye_el_token(ingresada):
    ItemCategoria.objects.create(descripcion="Varios")

    response = ingresada.get("/inventario/categorias/")

    content = response.content.decode()
    form = content.split('data-delete-form', 1)[1].split("</form>", 1)[0]
    assert 'name="csrfmiddlewaretoken"' in form


@pytest.mark.django_db
def test_elimina_categoria(ingresada):
    categoria = ItemCategoria.objects.create(descripcion="Varios")

    response = ingresada.post(f"/inventario/categorias/{categoria.pk}/eliminar/")

    assert response.status_code == 302
    assert response.url == "/inventario/categorias/"
    assert not ItemCategoria.objects.filter(pk=categoria.pk).exists()


@pytest.mark.django_db
def test_no_elimina_categoria_en_uso(ingresada):
    unidad = UnidadMedida.objects.create(descripcion="Unidad", simbolo="UND")
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

    response = ingresada.post(f"/inventario/categorias/{categoria.pk}/eliminar/")

    assert response.status_code == 302
    assert response.url == f"/inventario/categorias/{categoria.pk}/"
    assert ItemCategoria.objects.filter(pk=categoria.pk).exists()
    ficha = ingresada.get(response.url)
    assert "está en uso y no se puede eliminar." in ficha.content.decode()


@pytest.mark.django_db
def test_buscar_filtra_el_listado(ingresada):
    ItemCategoria.objects.create(descripcion="Alfa")
    ItemCategoria.objects.create(descripcion="Beta")

    response = ingresada.get("/inventario/categorias/?q=Alf")

    content = response.content.decode()
    assert response.status_code == 200
    assert "Alfa" in content
    assert "Beta" not in content
    assert "1 registro" in content


@pytest.mark.django_db
def test_alta_desde_el_listado_conserva_el_error(ingresada):
    response = ingresada.post(
        "/inventario/categorias/nueva/",
        {"descripcion": "   ", "accion": "guardar", "desde": "listado"},
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert "Escribí la descripción." in content
    assert 'class="detail-panel"' in content
    assert ItemCategoria.objects.count() == 0


def _serie(cantidad=26):
    for numero in range(1, cantidad + 1):
        ItemCategoria.objects.create(descripcion=f"Serie {numero:02d}")
    ItemCategoria.objects.create(descripcion="Fuera")


@pytest.mark.django_db
def test_listado_pagina_de_a_10(ingresada):
    _serie()

    primera = ingresada.get("/inventario/categorias/?q=Serie")
    contenido = primera.content.decode()

    assert primera.status_code == 200
    assert "Serie 01" in contenido
    assert "Serie 10" in contenido
    assert "Serie 11" not in contenido
    assert "Fuera" not in contenido
    assert "Mostrando 1 - 10 de 26" in contenido
    assert "26 registros" in contenido
    assert "q=Serie" in contenido
    assert "page=2" in contenido

    ultima = ingresada.get("/inventario/categorias/?q=Serie&page=3")
    pagina = ultima.content.decode()

    assert "Serie 26" in pagina
    assert "Serie 01" not in pagina
    assert "Mostrando 21 - 26 de 26" in pagina


@pytest.mark.django_db
def test_abrir_categoria_cae_en_su_pagina(ingresada):
    _serie()
    categoria = ItemCategoria.objects.get(descripcion="Serie 26")

    response = ingresada.get(f"/inventario/categorias/?categoria={categoria.pk}")

    assert response.status_code == 302
    assert f"categoria={categoria.pk}" in response.url
    assert "page=3" in response.url

    pagina = ingresada.get(response.url)
    seleccionado = next(
        part for part in pagina.content.decode().split("<tr") if 'aria-selected="true"' in part
    )
    assert f'data-id="{categoria.pk}"' in seleccionado
    assert "Serie 26" in pagina.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    [
        "/inventario/categorias/imprimir/",
        "/inventario/categorias/exportar.xlsx",
        "/inventario/categorias/exportar.pdf",
    ],
)
def test_salida_pide_ingreso(client, path):
    response = client.get(path)

    assert response.status_code == 302
    assert response.url.startswith("/login/")


@pytest.mark.django_db
def test_exporta_el_filtro_completo_en_excel(ingresada):
    _serie()

    response = ingresada.get("/inventario/categorias/exportar.xlsx?q=Serie&page=1")

    assert response.status_code == 200
    assert "spreadsheet" in response["Content-Type"]
    assert 'filename="categorias.xlsx"' in response["Content-Disposition"]
    libro = load_workbook(BytesIO(response.content))
    filas = list(libro.active.values)
    descripciones = [fila[0] for fila in filas]
    assert descripciones[0] == "Descripción"
    assert "Serie 01" in descripciones
    assert "Serie 26" in descripciones
    assert "Fuera" not in descripciones
    assert len(filas) == 27


@pytest.mark.django_db
def test_exporta_el_filtro_completo_en_pdf(ingresada):
    _serie()

    response = ingresada.get("/inventario/categorias/exportar.pdf?q=Serie&page=1")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert 'filename="categorias.pdf"' in response["Content-Disposition"]
    texto = "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(response.content)).pages
    )
    assert "Serie 01" in texto
    assert "Serie 26" in texto
    assert "Fuera" not in texto


@pytest.mark.django_db
def test_imprimir_incluye_el_filtro_completo(ingresada):
    _serie()

    response = ingresada.get("/inventario/categorias/imprimir/?q=Serie&page=1")

    assert response.status_code == 200
    contenido = response.content.decode()
    assert "Serie 01" in contenido
    assert "Serie 26" in contenido
    assert "Fuera" not in contenido
    assert "window.print" in contenido
    assert "26 registros" in contenido

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


def _payload(**extra):
    base = {"descripcion": "Unidad", "simbolo": "UND", "accion": "guardar"}
    base.update(extra)
    return base


@pytest.mark.django_db
def test_listado_pide_ingreso(client):
    response = client.get("/inventario/unidades/")

    assert response.status_code == 302
    assert response.url.startswith("/login/")


@pytest.mark.django_db
def test_el_menu_muestra_unidades(ingresada):
    response = ingresada.get("/")

    assert response.status_code == 200
    content = response.content.decode()
    assert 'href="/inventario/unidades/"' in content
    assert "Hola, ada." in content


@pytest.mark.django_db
def test_listado_marca_la_primera_fila(ingresada):
    UnidadMedida.objects.create(descripcion="Beta", simbolo="B")
    alfa = UnidadMedida.objects.create(descripcion="Alfa", simbolo="A")

    response = ingresada.get("/inventario/unidades/")

    content = response.content.decode()
    assert response.status_code == 200
    assert content.index("Alfa") < content.index("Beta")
    selected = next(part for part in content.split("<tr") if 'aria-selected="true"' in part)
    assert f'data-id="{alfa.pk}"' in selected
    assert "Nueva unidad" in content
    assert "Código" in content
    assert "Símbolo" in content
    assert "2 registros" in content
    assert "Flechas para moverse" in content


@pytest.mark.django_db
def test_listado_marca_la_fila_pedida(ingresada):
    beta = UnidadMedida.objects.create(descripcion="Beta", simbolo="B")
    UnidadMedida.objects.create(descripcion="Alfa", simbolo="A")

    response = ingresada.get(f"/inventario/unidades/?unidad={beta.pk}")

    selected = next(
        part for part in response.content.decode().split("<tr") if 'aria-selected="true"' in part
    )
    assert f'data-id="{beta.pk}"' in selected
    assert 'class="detail-panel"' in response.content.decode()
    assert f'href="/inventario/unidades/{beta.pk}/"' in response.content.decode()


@pytest.mark.django_db
def test_alta_vuelve_al_listado(ingresada):
    response = ingresada.post(
        "/inventario/unidades/nueva/",
        _payload(descripcion="Kilogramo", simbolo="kg"),
    )

    unidad = UnidadMedida.objects.get(descripcion="Kilogramo")
    assert unidad.simbolo == "kg"
    assert unidad.pk is not None
    assert response.status_code == 302
    assert response.url == f"/inventario/unidades/?unidad={unidad.pk}"


@pytest.mark.django_db
def test_descripcion_vacia_no_graba(ingresada):
    response = ingresada.post(
        "/inventario/unidades/nueva/",
        _payload(descripcion="   "),
    )

    assert response.status_code == 200
    assert "Escribí la descripción." in response.content.decode()
    assert UnidadMedida.objects.count() == 0


@pytest.mark.django_db
def test_simbolo_vacio_no_graba(ingresada):
    response = ingresada.post(
        "/inventario/unidades/nueva/",
        _payload(simbolo="   "),
    )

    assert response.status_code == 200
    assert "Escribí el símbolo." in response.content.decode()
    assert UnidadMedida.objects.count() == 0


@pytest.mark.django_db
def test_edicion_guarda_cambios(ingresada):
    unidad = UnidadMedida.objects.create(descripcion="Litro", simbolo="L")

    response = ingresada.post(
        f"/inventario/unidades/{unidad.pk}/",
        {"descripcion": "Litro neto", "simbolo": "l", "accion": "guardar"},
    )

    unidad.refresh_from_db()
    assert unidad.descripcion == "Litro neto"
    assert unidad.simbolo == "l"
    assert response.status_code == 302
    assert response.url == f"/inventario/unidades/?unidad={unidad.pk}"


@pytest.mark.django_db
def test_guardar_y_seguir_abre_otra_ficha(ingresada):
    response = ingresada.post(
        "/inventario/unidades/nueva/",
        _payload(descripcion="Par", simbolo="PR", accion="seguir"),
    )

    assert response.status_code == 302
    assert response.url == reverse("unidad_create")
    assert UnidadMedida.objects.filter(descripcion="Par").exists()

    unidad = UnidadMedida.objects.get(descripcion="Par")
    seguido = ingresada.post(
        f"/inventario/unidades/{unidad.pk}/",
        {"descripcion": "Par (2 u.)", "simbolo": "PR", "accion": "seguir"},
    )

    unidad.refresh_from_db()
    assert unidad.descripcion == "Par (2 u.)"
    assert seguido.status_code == 302
    assert seguido.url == "/inventario/unidades/nueva/"


@pytest.mark.django_db
def test_ficha_nueva_no_ofrece_eliminar(ingresada):
    response = ingresada.get("/inventario/unidades/nueva/")

    content = response.content.decode()
    assert response.status_code == 200
    assert "Nueva unidad" in content
    assert "Eliminar" not in content


@pytest.mark.django_db
def test_ficha_muestra_vecinas(ingresada):
    alfa = UnidadMedida.objects.create(descripcion="Alfa", simbolo="A")
    beta = UnidadMedida.objects.create(descripcion="Beta", simbolo="B")

    response = ingresada.get(f"/inventario/unidades/{alfa.pk}/")

    content = response.content.decode()
    assert "1 de 2" in content
    assert f'href="/inventario/unidades/{beta.pk}/"' in content
    assert "Eliminar" in content


@pytest.mark.django_db
def test_elimina_unidad(ingresada):
    unidad = UnidadMedida.objects.create(descripcion="Docena", simbolo="DOC")

    response = ingresada.post(f"/inventario/unidades/{unidad.pk}/eliminar/")

    assert response.status_code == 302
    assert response.url == "/inventario/unidades/"
    assert not UnidadMedida.objects.filter(pk=unidad.pk).exists()


@pytest.mark.django_db
def test_no_elimina_unidad_en_uso(ingresada):
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

    response = ingresada.post(f"/inventario/unidades/{unidad.pk}/eliminar/")

    assert response.status_code == 302
    assert response.url == f"/inventario/unidades/{unidad.pk}/"
    assert UnidadMedida.objects.filter(pk=unidad.pk).exists()
    ficha = ingresada.get(response.url)
    assert "está en uso y no se puede eliminar." in ficha.content.decode()


@pytest.mark.django_db
def test_buscar_filtra_el_listado(ingresada):
    UnidadMedida.objects.create(descripcion="Alfa", simbolo="A")
    UnidadMedida.objects.create(descripcion="Beta", simbolo="B")

    response = ingresada.get("/inventario/unidades/?q=Alf")

    content = response.content.decode()
    assert response.status_code == 200
    assert "Alfa" in content
    assert "Beta" not in content
    assert "1 registro" in content


@pytest.mark.django_db
def test_alta_desde_el_listado_conserva_el_error(ingresada):
    response = ingresada.post(
        "/inventario/unidades/nueva/",
        _payload(descripcion="   ", desde="listado"),
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert "Escribí la descripción." in content
    assert 'class="detail-panel"' in content
    assert UnidadMedida.objects.count() == 0


def _serie(cantidad=26):
    for numero in range(1, cantidad + 1):
        UnidadMedida.objects.create(
            descripcion=f"Serie {numero:02d}",
            simbolo=f"S{numero:02d}",
        )
    UnidadMedida.objects.create(descripcion="Fuera", simbolo="OUT")


@pytest.mark.django_db
def test_listado_pagina_de_a_10(ingresada):
    _serie()

    primera = ingresada.get("/inventario/unidades/?q=Serie")
    contenido = primera.content.decode()

    assert primera.status_code == 200
    assert "Serie 01" in contenido
    assert "Serie 10" in contenido
    assert "Serie 11" not in contenido
    assert "Fuera" not in contenido
    assert "Mostrando 1 - 10 de 26" in contenido
    assert "26 registros" in contenido

    ultima = ingresada.get("/inventario/unidades/?q=Serie&page=3")
    pagina = ultima.content.decode()

    assert "Serie 26" in pagina
    assert "Mostrando 21 - 26 de 26" in pagina


@pytest.mark.django_db
def test_abrir_unidad_cae_en_su_pagina(ingresada):
    _serie()
    unidad = UnidadMedida.objects.get(descripcion="Serie 26")

    response = ingresada.get(f"/inventario/unidades/?unidad={unidad.pk}")

    assert response.status_code == 302
    assert f"unidad={unidad.pk}" in response.url
    assert "page=3" in response.url


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    [
        "/inventario/unidades/imprimir/",
        "/inventario/unidades/exportar.xlsx",
        "/inventario/unidades/exportar.pdf",
    ],
)
def test_salida_pide_ingreso(client, path):
    response = client.get(path)

    assert response.status_code == 302
    assert response.url.startswith("/login/")


@pytest.mark.django_db
def test_exporta_el_filtro_completo_en_excel(ingresada):
    _serie()

    response = ingresada.get("/inventario/unidades/exportar.xlsx?q=Serie&page=1")

    assert response.status_code == 200
    assert 'filename="unidades.xlsx"' in response["Content-Disposition"]
    libro = load_workbook(BytesIO(response.content))
    filas = list(libro.active.values)
    assert filas[0] == ("Código", "Descripción", "Símbolo")
    descripciones = [fila[1] for fila in filas[1:]]
    assert "Serie 01" in descripciones
    assert "Serie 26" in descripciones
    assert "Fuera" not in descripciones
    assert len(filas) == 27


@pytest.mark.django_db
def test_exporta_el_filtro_completo_en_pdf(ingresada):
    _serie()

    response = ingresada.get("/inventario/unidades/exportar.pdf?q=Serie&page=1")

    assert response.status_code == 200
    assert 'filename="unidades.pdf"' in response["Content-Disposition"]
    texto = "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(response.content)).pages
    )
    assert "Serie 01" in texto
    assert "Serie 26" in texto
    assert "Fuera" not in texto


@pytest.mark.django_db
def test_imprimir_incluye_el_filtro_completo(ingresada):
    _serie()

    response = ingresada.get("/inventario/unidades/imprimir/?q=Serie&page=1")

    assert response.status_code == 200
    contenido = response.content.decode()
    assert "Serie 01" in contenido
    assert "Serie 26" in contenido
    assert "Fuera" not in contenido
    assert "26 registros" in contenido

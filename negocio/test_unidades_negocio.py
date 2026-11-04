from io import BytesIO

import pytest
from openpyxl import load_workbook
from pypdf import PdfReader

from inventario.models import Item, ItemCategoria, Marca, TipoItem, UnidadMedida
from negocio.models import UnidadNegocio




def _payload(**extra):
    base = {"descripcion": "Depósito central", "abreviado": "DEP", "accion": "guardar"}
    base.update(extra)
    return base


@pytest.mark.django_db
def test_listado_pide_ingreso(client):
    response = client.get("/unidades-negocio/")

    assert response.status_code == 302
    assert response.url.startswith("/login/")


@pytest.mark.django_db
def test_el_menu_muestra_unidades_de_negocio(ingresada):
    response = ingresada.get("/")

    assert response.status_code == 200
    content = response.content.decode()
    assert 'href="/unidades-negocio/"' in content
    assert "Hola, ada." in content


@pytest.mark.django_db
def test_listado_marca_la_primera_fila(ingresada):
    UnidadNegocio.objects.create(descripcion="Beta", abreviado="BET")
    alfa = UnidadNegocio.objects.create(descripcion="Alfa", abreviado="ALF")

    response = ingresada.get("/unidades-negocio/")

    content = response.content.decode()
    assert response.status_code == 200
    assert content.index("Alfa") < content.index("Beta")
    selected = next(part for part in content.split("<tr") if 'aria-selected="true"' in part)
    assert f'data-id="{alfa.pk}"' in selected
    assert "Nueva unidad de negocio" in content
    assert "Abreviado" in content
    assert "2 registros" in content


@pytest.mark.django_db
def test_alta_vuelve_al_listado(ingresada):
    response = ingresada.post("/unidades-negocio/nueva/", _payload())

    unidad = UnidadNegocio.objects.get(descripcion="Depósito central")
    assert unidad.abreviado == "DEP"
    assert response.status_code == 302
    assert response.url == "/unidades-negocio/"


@pytest.mark.django_db
def test_descripcion_vacia_no_graba(ingresada):
    response = ingresada.post("/unidades-negocio/nueva/", _payload(descripcion="   "))

    assert response.status_code == 200
    assert "Escribí la descripción." in response.content.decode()
    assert UnidadNegocio.objects.count() == 0


@pytest.mark.django_db
def test_abreviado_vacio_no_graba(ingresada):
    response = ingresada.post("/unidades-negocio/nueva/", _payload(abreviado="   "))

    assert response.status_code == 200
    assert "Escribí el abreviado." in response.content.decode()
    assert UnidadNegocio.objects.count() == 0


@pytest.mark.django_db
def test_no_repite_descripcion_ni_abreviado(ingresada):
    UnidadNegocio.objects.create(descripcion="Depósito central", abreviado="DEP")

    repetida = ingresada.post("/unidades-negocio/nueva/", _payload(abreviado="OTR"))
    assert repetida.status_code == 200
    assert "Ya hay una unidad de negocio con esa descripción." in repetida.content.decode()

    corto = ingresada.post(
        "/unidades-negocio/nueva/",
        _payload(descripcion="Depósito norte", abreviado="DEP"),
    )
    assert corto.status_code == 200
    assert "Ya hay una unidad de negocio con ese abreviado." in corto.content.decode()
    assert UnidadNegocio.objects.count() == 1


@pytest.mark.django_db
def test_edicion_guarda_cambios(ingresada):
    unidad = UnidadNegocio.objects.create(descripcion="Depósito", abreviado="DEP")

    response = ingresada.post(
        f"/unidades-negocio/{unidad.pk}/",
        {"descripcion": "Depósito norte", "abreviado": "NOR", "accion": "guardar"},
    )

    unidad.refresh_from_db()
    assert unidad.descripcion == "Depósito norte"
    assert unidad.abreviado == "NOR"
    assert response.status_code == 302
    assert response.url == "/unidades-negocio/"


@pytest.mark.django_db
def test_guardar_y_seguir_abre_otra_ficha(ingresada):
    response = ingresada.post("/unidades-negocio/nueva/", _payload(accion="seguir"))

    assert response.status_code == 302
    assert response.url == "/unidades-negocio/?nueva=1"
    assert UnidadNegocio.objects.filter(abreviado="DEP").exists()


@pytest.mark.django_db
def test_elimina_unidad_de_negocio(ingresada):
    unidad = UnidadNegocio.objects.create(descripcion="Depósito", abreviado="DEP")

    response = ingresada.post(f"/unidades-negocio/{unidad.pk}/eliminar/")

    assert response.status_code == 302
    assert response.url == "/unidades-negocio/"
    assert not UnidadNegocio.objects.filter(pk=unidad.pk).exists()


@pytest.mark.django_db
def test_no_elimina_unidad_de_negocio_en_uso(ingresada):
    unidad_negocio = UnidadNegocio.objects.create(descripcion="Depósito", abreviado="DEP")
    unidad = UnidadMedida.objects.create(descripcion="Unidad", simbolo="UND")
    marca = Marca.objects.create(descripcion="Genérica")
    categoria = ItemCategoria.objects.create(descripcion="Alimentos")
    Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        unidad_negocio=unidad_negocio,
        descripcion="Arroz 1kg",
        tipo=TipoItem.PRODUCTO,
    )

    response = ingresada.post(f"/unidades-negocio/{unidad_negocio.pk}/eliminar/")

    assert response.status_code == 302
    assert response.url == f"/unidades-negocio/?unidad_negocio={unidad_negocio.pk}"
    assert UnidadNegocio.objects.filter(pk=unidad_negocio.pk).exists()
    pagina = ingresada.get(response.url)
    assert "está en uso y no se puede eliminar." in pagina.content.decode()


@pytest.mark.django_db
def test_buscar_filtra_el_listado(ingresada):
    UnidadNegocio.objects.create(descripcion="Alfa", abreviado="ALF")
    UnidadNegocio.objects.create(descripcion="Beta", abreviado="BET")

    response = ingresada.get("/unidades-negocio/?q=Alf")

    content = response.content.decode()
    assert "Alfa" in content
    assert "Beta" not in content
    assert "1 registro" in content


def _serie(cantidad=26):
    for numero in range(1, cantidad + 1):
        UnidadNegocio.objects.create(
            descripcion=f"Serie {numero:02d}",
            abreviado=f"S{numero:02d}",
        )
    UnidadNegocio.objects.create(descripcion="Fuera", abreviado="OUT")


@pytest.mark.django_db
def test_exporta_el_filtro_completo_en_excel(ingresada):
    _serie()

    response = ingresada.get("/unidades-negocio/exportar.xlsx?q=Serie&page=1")

    assert response.status_code == 200
    assert 'filename="unidades-negocio.xlsx"' in response["Content-Disposition"]
    libro = load_workbook(BytesIO(response.content))
    filas = list(libro.active.values)
    assert filas[0] == ("Descripción", "Abreviado")
    descripciones = [fila[0] for fila in filas[1:]]
    assert "Serie 01" in descripciones
    assert "Serie 26" in descripciones
    assert "Fuera" not in descripciones
    assert len(filas) == 27


@pytest.mark.django_db
def test_exporta_el_filtro_completo_en_pdf(ingresada):
    _serie()

    response = ingresada.get("/unidades-negocio/exportar.pdf?q=Serie&page=1")

    assert response.status_code == 200
    texto = "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(response.content)).pages
    )
    assert "Serie 01" in texto
    assert "Serie 26" in texto
    assert "Fuera" not in texto

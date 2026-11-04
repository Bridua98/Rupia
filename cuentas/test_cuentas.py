from io import BytesIO

import pytest
from openpyxl import load_workbook
from pypdf import PdfReader

from cuentas.models import Cuenta


def _payload(**extra):
    base = {
        "descripcion": "Caja principal",
        "nombre_corto": "CAJA",
        "accion": "guardar",
    }
    base.update(extra)
    return base


@pytest.mark.django_db
def test_listado_pide_ingreso(client):
    response = client.get("/cuentas/")

    assert response.status_code == 302
    assert response.url.startswith("/login/")


@pytest.mark.django_db
def test_el_menu_muestra_cuentas(ingresada):
    response = ingresada.get("/")

    assert response.status_code == 200
    content = response.content.decode()
    assert 'href="/cuentas/"' in content
    assert "Hola, ada." in content


@pytest.mark.django_db
def test_listado_marca_la_primera_fila(ingresada):
    Cuenta.objects.create(descripcion="Beta", nombre_corto="BETA")
    alfa = Cuenta.objects.create(descripcion="Alfa", nombre_corto="ALFA")

    response = ingresada.get("/cuentas/")

    content = response.content.decode()
    assert response.status_code == 200
    assert content.index("Alfa") < content.index("Beta")
    selected = next(part for part in content.split("<tr") if 'aria-selected="true"' in part)
    assert f'data-id="{alfa.pk}"' in selected
    assert "Nueva cuenta" in content
    assert "Nombre corto" in content
    assert "2 registros" in content
    assert "Flechas para moverse" in content


@pytest.mark.django_db
def test_alta_vuelve_al_listado(ingresada):
    response = ingresada.post("/cuentas/nueva/", _payload())

    cuenta = Cuenta.objects.get(descripcion="Caja principal")
    assert cuenta.nombre_corto == "CAJA"
    assert cuenta.es_banco is False
    assert cuenta.es_tarjeta is False
    assert cuenta.numero is None
    assert response.status_code == 302
    assert response.url == "/cuentas/"
    pagina = ingresada.get(response.url)
    assert 'class="detail-panel"' not in pagina.content.decode()
    assert "Caja" in pagina.content.decode()


@pytest.mark.django_db
def test_descripcion_vacia_no_graba(ingresada):
    response = ingresada.post("/cuentas/nueva/", _payload(descripcion="   "))

    assert response.status_code == 200
    assert "Escribí la descripción." in response.content.decode()
    assert Cuenta.objects.count() == 0


@pytest.mark.django_db
def test_nombre_corto_vacio_no_graba(ingresada):
    response = ingresada.post("/cuentas/nueva/", _payload(nombre_corto="   "))

    assert response.status_code == 200
    assert "Escribí el nombre corto." in response.content.decode()
    assert Cuenta.objects.count() == 0


@pytest.mark.django_db
def test_no_repite_descripcion_ni_nombre_corto(ingresada):
    Cuenta.objects.create(descripcion="Caja principal", nombre_corto="CAJA")

    repetida = ingresada.post("/cuentas/nueva/", _payload(nombre_corto="OTRA"))
    assert repetida.status_code == 200
    assert "Ya hay una cuenta con esa descripción." in repetida.content.decode()

    corto = ingresada.post(
        "/cuentas/nueva/",
        _payload(descripcion="Caja chica", nombre_corto="CAJA"),
    )
    assert corto.status_code == 200
    assert "Ya hay una cuenta con ese nombre corto." in corto.content.decode()
    assert Cuenta.objects.count() == 1


@pytest.mark.django_db
def test_banco_sin_numero_no_graba(ingresada):
    response = ingresada.post(
        "/cuentas/nueva/",
        _payload(descripcion="Banco Itaú", nombre_corto="ITAU", es_banco="on"),
    )

    assert response.status_code == 200
    assert "Escribí el número de cuenta." in response.content.decode()
    assert Cuenta.objects.count() == 0


@pytest.mark.django_db
def test_banco_guarda_numero(ingresada):
    response = ingresada.post(
        "/cuentas/nueva/",
        _payload(
            descripcion="Banco Itaú",
            nombre_corto="ITAU",
            es_banco="on",
            numero="123456",
        ),
    )

    cuenta = Cuenta.objects.get(nombre_corto="ITAU")
    assert response.status_code == 302
    assert cuenta.es_banco is True
    assert cuenta.es_tarjeta is False
    assert cuenta.numero == "123456"
    pagina = ingresada.get(response.url)
    assert "Banco" in pagina.content.decode()
    assert "123456" in pagina.content.decode()


@pytest.mark.django_db
def test_tarjeta_solo_si_es_banco(ingresada):
    caja = ingresada.post(
        "/cuentas/nueva/",
        _payload(es_tarjeta="on", numero="999"),
    )
    cuenta = Cuenta.objects.get(nombre_corto="CAJA")
    assert caja.status_code == 302
    assert cuenta.es_tarjeta is False
    assert cuenta.numero is None

    tarjeta = ingresada.post(
        "/cuentas/nueva/",
        _payload(
            descripcion="Visa Itaú",
            nombre_corto="VISA",
            es_banco="on",
            es_tarjeta="on",
            numero="4111",
        ),
    )
    visa = Cuenta.objects.get(nombre_corto="VISA")
    assert tarjeta.status_code == 302
    assert visa.es_banco is True
    assert visa.es_tarjeta is True
    assert visa.numero == "4111"
    pagina = ingresada.get(tarjeta.url)
    assert "Tarjeta" in pagina.content.decode()


@pytest.mark.django_db
def test_edicion_guarda_cambios(ingresada):
    cuenta = Cuenta.objects.create(descripcion="Caja", nombre_corto="CJ")

    response = ingresada.post(
        f"/cuentas/{cuenta.pk}/",
        _payload(descripcion="Caja chica", nombre_corto="CHICA"),
    )

    cuenta.refresh_from_db()
    assert cuenta.descripcion == "Caja chica"
    assert cuenta.nombre_corto == "CHICA"
    assert response.status_code == 302
    assert response.url == "/cuentas/"


@pytest.mark.django_db
def test_guardar_y_seguir_abre_otra_ficha(ingresada):
    response = ingresada.post("/cuentas/nueva/", _payload(accion="seguir"))

    assert response.status_code == 302
    assert response.url == "/cuentas/?nueva=1"
    assert Cuenta.objects.filter(nombre_corto="CAJA").exists()


@pytest.mark.django_db
def test_alta_abre_el_panel_del_listado(ingresada):
    response = ingresada.get("/cuentas/nueva/")

    assert response.status_code == 302
    assert response.url == "/cuentas/?nueva=1"
    pagina = ingresada.get(response.url)
    content = pagina.content.decode()
    assert pagina.status_code == 200
    assert "Nueva cuenta" in content
    assert "Guardar" in content
    assert "Abrir ficha" not in content
    assert "data-cuenta-banco" in content
    assert "data-cuenta-si-banco" in content


@pytest.mark.django_db
def test_elimina_cuenta(ingresada):
    cuenta = Cuenta.objects.create(descripcion="Caja", nombre_corto="CJ")

    response = ingresada.post(f"/cuentas/{cuenta.pk}/eliminar/")

    assert response.status_code == 302
    assert response.url == "/cuentas/"
    assert not Cuenta.objects.filter(pk=cuenta.pk).exists()


@pytest.mark.django_db
def test_buscar_filtra_el_listado(ingresada):
    Cuenta.objects.create(descripcion="Alfa", nombre_corto="ALFA")
    Cuenta.objects.create(descripcion="Beta", nombre_corto="BETA")

    response = ingresada.get("/cuentas/?q=Alf")

    content = response.content.decode()
    assert response.status_code == 200
    assert "Alfa" in content
    assert "Beta" not in content
    assert "1 registro" in content


@pytest.mark.django_db
def test_filtro_banco(ingresada):
    Cuenta.objects.create(descripcion="Efectivo mostrador", nombre_corto="CAJA")
    Cuenta.objects.create(
        descripcion="Itaú",
        nombre_corto="ITAU",
        es_banco=True,
        numero="123",
    )

    response = ingresada.get("/cuentas/?es_banco=1")

    content = response.content.decode()
    assert "Itaú" in content
    assert "Efectivo mostrador" not in content


def _serie(cantidad=26):
    for numero in range(1, cantidad + 1):
        Cuenta.objects.create(
            descripcion=f"Serie {numero:02d}",
            nombre_corto=f"S{numero:02d}",
        )
    Cuenta.objects.create(descripcion="Fuera", nombre_corto="OUT")


@pytest.mark.django_db
def test_listado_pagina_de_a_10(ingresada):
    _serie()

    primera = ingresada.get("/cuentas/?q=Serie")
    contenido = primera.content.decode()

    assert primera.status_code == 200
    assert "Serie 01" in contenido
    assert "Serie 10" in contenido
    assert "Serie 11" not in contenido
    assert "Fuera" not in contenido
    assert "Mostrando 1 - 10 de 26" in contenido


@pytest.mark.django_db
def test_exporta_el_filtro_completo_en_excel(ingresada):
    _serie()

    response = ingresada.get("/cuentas/exportar.xlsx?q=Serie&page=1")

    assert response.status_code == 200
    assert 'filename="cuentas.xlsx"' in response["Content-Disposition"]
    libro = load_workbook(BytesIO(response.content))
    filas = list(libro.active.values)
    assert filas[0] == ("Descripción", "Nombre corto", "Tipo", "Número")
    descripciones = [fila[0] for fila in filas[1:]]
    assert "Serie 01" in descripciones
    assert "Serie 26" in descripciones
    assert "Fuera" not in descripciones
    assert len(filas) == 27


@pytest.mark.django_db
def test_exporta_el_filtro_completo_en_pdf(ingresada):
    _serie()

    response = ingresada.get("/cuentas/exportar.pdf?q=Serie&page=1")

    assert response.status_code == 200
    texto = "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(response.content)).pages
    )
    assert "Serie 01" in texto
    assert "Serie 26" in texto
    assert "Fuera" not in texto

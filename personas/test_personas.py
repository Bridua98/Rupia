import json
from datetime import date, timedelta
from io import BytesIO
from unittest.mock import patch
from urllib.error import URLError

import pytest
from django.utils import timezone
from openpyxl import load_workbook

from personas.consulta import buscar, consultar_ruc, ficha_persona
from personas.models import Genero, Persona, TipoDocumento




def crear_persona(**overrides):
    datos = {
        "tipo_documento": TipoDocumento.CEDULA,
        "documento": "1234567",
        "razon_social": "Ana Gómez",
        "genero": Genero.FEMENINO,
        "direccion": "Centro",
        "es_cliente": True,
    }
    datos.update(overrides)
    return Persona.objects.create(**datos)


def datos_persona(**overrides):
    datos = {
        "tipo_documento": TipoDocumento.CEDULA,
        "documento": "1234567",
        "razon_social": "Ana Gómez",
        "fecha_nacimiento": "1990-01-15",
        "genero": Genero.FEMENINO,
        "direccion": "Centro",
        "celular": "0981123456",
        "observacion": "Primera nota",
        "es_cliente": "on",
        "es_proveedor": "on",
        "activo": "on",
        "accion": "guardar",
    }
    datos.update(overrides)
    return datos


def sin_roles(datos):
    for campo in ("es_cliente", "es_proveedor", "es_empleado"):
        datos.pop(campo, None)
    return datos


@pytest.mark.django_db
def test_listado_pide_ingreso(client):
    response = client.get("/personas/")

    assert response.status_code == 302
    assert response.url.startswith("/login/")


@pytest.mark.django_db
def test_el_menu_muestra_personas(ingresada):
    response = ingresada.get("/personas/")

    assert response.status_code == 200
    content = response.content.decode()
    assert 'href="/personas/"' in content
    assert 'aria-current="page"' in content


@pytest.mark.django_db
def test_listado_marca_la_primera_fila(ingresada):
    crear_persona(documento="2222222", razon_social="Beta")
    alfa = crear_persona(documento="1111111", razon_social="Alfa")

    response = ingresada.get("/personas/")

    content = response.content.decode()
    assert response.status_code == 200
    assert content.index("Alfa") < content.index("Beta")
    selected = next(part for part in content.split("<tr") if 'aria-selected="true"' in part)
    assert f'data-id="{alfa.pk}"' in selected
    assert "Nueva persona" in content
    assert 'aria-label="Imprimir y exportar"' in content
    assert "2 registros" in content
    assert "Flechas para moverse" in content


@pytest.mark.django_db
def test_listado_muestra_los_roles_apilados(ingresada):
    crear_persona(
        documento="80012345-6",
        tipo_documento=TipoDocumento.RUC,
        es_cliente=True,
        es_proveedor=True,
        es_empleado=True,
    )

    response = ingresada.get("/personas/")

    content = response.content.decode()
    assert (
        '<span class="persona-rol">Cliente</span>'
        '<span class="persona-rol">Proveedor</span>'
        '<span class="persona-rol">Personal</span>'
    ) in content
    assert "RUC 80012345-6" not in content
    assert "80012345-6" in content


@pytest.mark.django_db
def test_listado_muestra_un_solo_rol(ingresada):
    crear_persona(documento="1234567", es_cliente=True)

    response = ingresada.get("/personas/")

    content = response.content.decode()
    assert '<span class="persona-rol">Cliente</span>' in content
    assert "Proveedor</span>" not in content
    assert "Personal</span>" not in content


@pytest.mark.django_db
def test_listado_marca_la_fila_pedida(ingresada):
    beta = crear_persona(documento="2222222", razon_social="Beta")
    crear_persona(documento="1111111", razon_social="Alfa")

    response = ingresada.get(f"/personas/?persona={beta.pk}")

    content = response.content.decode()
    selected = next(part for part in content.split("<tr") if 'aria-selected="true"' in part)
    assert response.status_code == 200
    assert f'data-id="{beta.pk}"' in selected
    assert 'class="detail-panel"' in content
    assert "Abrir ficha" not in content
    assert 'aria-label="Cerrar"' in content


@pytest.mark.django_db
def test_alta_vuelve_al_listado(ingresada):
    datos = datos_persona(es_empleado="on")
    response = ingresada.post("/personas/nueva/", datos)

    persona = Persona.objects.get(documento="1234567")
    assert response.status_code == 302
    assert response.url == "/personas/"
    assert persona.razon_social == "Ana Gómez"
    assert persona.fecha_nacimiento == date(1990, 1, 15)
    assert persona.genero == Genero.FEMENINO
    assert persona.direccion == "Centro"
    assert persona.celular == "0981123456"
    assert persona.observacion == "Primera nota"
    assert persona.es_cliente is True
    assert persona.es_proveedor is True
    assert persona.es_empleado is True
    assert persona.activo is True


@pytest.mark.django_db
def test_alta_sin_roles_no_graba(ingresada):
    response = ingresada.post("/personas/nueva/", sin_roles(datos_persona()))

    assert response.status_code == 200
    assert "Marcá al menos un rol: cliente, proveedor o personal." in response.content.decode()
    assert Persona.objects.count() == 0


@pytest.mark.django_db
def test_edicion_sin_roles_no_graba(ingresada):
    persona = crear_persona()

    response = ingresada.post(
        f"/personas/{persona.pk}/",
        sin_roles(datos_persona(razon_social="Ana Gómez Modificada")),
    )

    persona.refresh_from_db()
    assert response.status_code == 200
    assert "Marcá al menos un rol: cliente, proveedor o personal." in response.content.decode()
    assert persona.razon_social == "Ana Gómez"
    assert persona.es_cliente is True


@pytest.mark.django_db
def test_no_repite_el_documento(ingresada):
    crear_persona(documento="1234567")

    response = ingresada.post("/personas/nueva/", datos_persona(razon_social="Otra persona"))

    assert response.status_code == 200
    assert "Ya hay una persona con ese documento." in response.content.decode()
    assert Persona.objects.count() == 1


@pytest.mark.django_db
def test_no_permite_fecha_de_nacimiento_futura(ingresada):
    manana = (timezone.localdate() + timedelta(days=1)).isoformat()

    response = ingresada.post(
        "/personas/nueva/",
        datos_persona(fecha_nacimiento=manana),
    )

    assert response.status_code == 200
    assert "La fecha de nacimiento no puede ser futura." in response.content.decode()
    assert Persona.objects.count() == 0


@pytest.mark.django_db
def test_edicion_guarda_cambios(ingresada):
    persona = crear_persona()

    response = ingresada.post(
        f"/personas/{persona.pk}/",
        datos_persona(razon_social="Ana Gómez Modificada", celular="0972123456"),
    )

    persona.refresh_from_db()
    assert persona.razon_social == "Ana Gómez Modificada"
    assert persona.celular == "0972123456"
    assert response.status_code == 302
    assert response.url == "/personas/"


@pytest.mark.django_db
def test_guardar_y_seguir_abre_otra_ficha(ingresada):
    response = ingresada.post(
        "/personas/nueva/",
        datos_persona(accion="seguir"),
    )

    assert response.status_code == 302
    assert response.url == "/personas/?nueva=1"
    assert Persona.objects.filter(documento="1234567").exists()


@pytest.mark.django_db
def test_nueva_persona_desde_compras_marca_proveedor(ingresada):
    response = ingresada.get(
        "/personas/?nueva=1&proveedor=1&razon_social=Proveedor%20nuevo"
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert "Nueva persona" in content
    assert "Proveedor nuevo" in content
    assert 'id="id_es_proveedor"' in content
    assert 'id="id_es_proveedor" checked' in content


@pytest.mark.django_db
def test_formulario_usa_personal_y_fecha_nativa(ingresada):
    response = ingresada.get("/personas/?nueva=1")

    content = response.content.decode()
    assert response.status_code == 200
    assert '<label for="id_es_empleado">Personal</label>' in content
    assert 'type="date"' in content


@pytest.mark.django_db
def test_edicion_muestra_la_fecha_de_nacimiento(ingresada):
    persona = crear_persona(fecha_nacimiento=date(1990, 1, 15))

    response = ingresada.get(f"/personas/?persona={persona.pk}")

    content = response.content.decode()
    assert response.status_code == 200
    assert 'value="1990-01-15"' in content


@pytest.mark.django_db
def test_alta_abre_el_panel_del_listado(ingresada):
    response = ingresada.get("/personas/nueva/")

    assert response.status_code == 302
    assert response.url == "/personas/?nueva=1"
    pagina = ingresada.get(response.url)
    content = pagina.content.decode()
    assert pagina.status_code == 200
    assert "Nueva persona" in content
    assert "Guardar" in content
    assert "Abrir ficha" not in content
    assert "Persona anterior" not in content


@pytest.mark.django_db
def test_elimina_persona(ingresada):
    persona = crear_persona()

    response = ingresada.post(f"/personas/{persona.pk}/eliminar/")

    assert response.status_code == 302
    assert response.url == "/personas/"
    assert not Persona.objects.filter(pk=persona.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("query", "visible", "oculta"),
    [
        ("0981123456", "Ana Gómez", "Beto"),
        ("2222222", "Beto", "Ana Gómez"),
    ],
)
def test_buscar_por_documento_y_celular(ingresada, query, visible, oculta):
    crear_persona(documento="1111111", razon_social="Ana Gómez", celular="0981123456")
    crear_persona(documento="2222222", razon_social="Beto", celular="0972123456")

    response = ingresada.get(f"/personas/?q={query}")

    content = response.content.decode()
    assert response.status_code == 200
    assert visible in content
    assert oculta not in content
    assert "1 registro" in content


@pytest.mark.django_db
def test_filtrar_por_rol(ingresada):
    crear_persona(documento="1111111", razon_social="Ana Gómez", es_cliente=True)
    crear_persona(
        documento="2222222",
        razon_social="Beto",
        es_cliente=False,
        es_proveedor=True,
    )

    response = ingresada.get("/personas/?es_proveedor=1")

    content = response.content.decode()
    assert response.status_code == 200
    assert "Beto" in content
    assert "Ana Gómez" not in content


@pytest.mark.django_db
def test_guardar_desde_el_listado_cierra_el_panel(ingresada):
    response = ingresada.post(
        "/personas/nueva/",
        datos_persona(desde="listado", q="Ana"),
    )

    assert response.status_code == 302
    assert response.url == "/personas/?q=Ana"
    pagina = ingresada.get(response.url)
    contenido = pagina.content.decode()
    assert 'class="detail-panel"' not in contenido
    assert "Ana Gómez" in contenido


@pytest.mark.django_db
def test_alta_desde_el_listado_conserva_el_error(ingresada):
    response = ingresada.post(
        "/personas/nueva/",
        sin_roles(datos_persona(desde="listado")),
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert "Marcá al menos un rol: cliente, proveedor o personal." in content
    assert 'class="detail-panel"' in content
    assert Persona.objects.count() == 0


@pytest.mark.django_db
def test_listado_pagina_de_a_10(ingresada):
    for numero in range(1, 12):
        crear_persona(
            documento=f"{numero:07d}",
            razon_social=f"Persona {numero:02d}",
        )

    primera = ingresada.get("/personas/")
    contenido = primera.content.decode()

    assert primera.status_code == 200
    assert "Persona 01" in contenido
    assert "Persona 10" in contenido
    assert "Persona 11" not in contenido
    assert "Mostrando 1 - 10 de 11" in contenido
    assert "11 registros" in contenido

    segunda = ingresada.get("/personas/?page=2")
    pagina = segunda.content.decode()

    assert "Persona 11" in pagina
    assert "Persona 01" not in pagina
    assert "Mostrando 11 - 11 de 11" in pagina


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    [
        "/personas/imprimir/",
        "/personas/exportar.xlsx",
        "/personas/exportar.pdf",
    ],
)
def test_salida_pide_ingreso(client, path):
    response = client.get(path)

    assert response.status_code == 302
    assert response.url.startswith("/login/")


@pytest.mark.django_db
def test_exporta_tipo_y_documento_en_excel(ingresada):
    crear_persona(
        documento="80012345-6",
        tipo_documento=TipoDocumento.RUC,
        razon_social="Comercial Este",
        es_cliente=True,
        es_proveedor=True,
        es_empleado=True,
    )

    response = ingresada.get("/personas/exportar.xlsx")
    libro = load_workbook(BytesIO(response.content))
    filas = list(libro.active.values)

    assert response.status_code == 200
    assert list(filas[0]) == [
        "Razón social",
        "Tipo",
        "Documento",
        "Celular",
        "Activo",
    ]
    assert filas[1][1] == "Cliente, Proveedor, Personal"
    assert filas[1][2] == "80012345-6"
    assert filas[1][4] is True


@pytest.mark.django_db
def test_imprimir_incluye_el_tipo(ingresada):
    crear_persona(
        documento="80012345-6",
        tipo_documento=TipoDocumento.RUC,
        razon_social="Comercial Este",
        es_cliente=True,
        es_proveedor=True,
        es_empleado=True,
    )

    response = ingresada.get("/personas/imprimir/")

    contenido = response.content.decode()
    assert response.status_code == 200
    assert "Cliente, Proveedor, Personal" in contenido
    assert "80012345-6" in contenido
    assert "RUC 80012345-6" not in contenido
    assert "window.print" in contenido


class FakePeople:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_ficha_mapea_ruc_con_dv():
    ficha = ficha_persona(
        {
            "ruc": "80009735",
            "razonsocial": "ADMINISTRACION NACIONAL DE ELECTRICIDAD - ANDE",
            "dv": "1",
            "tipo": "J",
            "estado": "ACTIVO",
        }
    )

    assert ficha["tipo_documento"] == TipoDocumento.RUC
    assert ficha["documento"] == "80009735-1"
    assert ficha["razon_social"] == "ADMINISTRACION NACIONAL DE ELECTRICIDAD - ANDE"
    assert ficha["fecha_nacimiento"] is None
    assert ficha["label"] == "ADMINISTRACION NACIONAL DE ELECTRICIDAD - ANDE (80009735-1)"


def test_ficha_mapea_cedula_sin_dv_y_fecha():
    ficha = ficha_persona(
        {
            "ruc": "1234567",
            "razonsocial": "GOMEZ ANA",
            "dv": None,
            "tipo": "F",
            "fecNac": "15/01/1990",
        }
    )

    assert ficha["tipo_documento"] == TipoDocumento.CEDULA
    assert ficha["documento"] == "1234567"
    assert ficha["razon_social"] == "GOMEZ ANA"
    assert ficha["fecha_nacimiento"] == "1990-01-15"


@patch("personas.consulta.urlopen")
def test_buscar_devuelve_vacio_si_el_servicio_cae(urlopen):
    urlopen.side_effect = URLError("down")

    assert buscar("ande") == []


@patch("personas.consulta.urlopen")
def test_consultar_ruc_devuelve_vacio_si_el_servicio_cae(urlopen):
    urlopen.side_effect = URLError("down")

    assert consultar_ruc("80009735") is None


@patch("personas.consulta.urlopen")
def test_buscar_usa_el_padron(urlopen):
    urlopen.return_value = FakePeople(
        [
            {
                "ruc": "80009735",
                "razonsocial": "ANDE",
                "dv": "1",
                "tipo": "J",
                "estado": "ACTIVO",
            }
        ]
    )

    results = buscar("ande")

    assert results[0]["documento"] == "80009735-1"
    assert urlopen.call_args[0][0].full_url.endswith("/search?query=ande")


@pytest.mark.django_db
def test_consulta_pide_ingreso(client):
    response = client.get("/personas/consulta/?q=ande")

    assert response.status_code == 302
    assert response.url.startswith("/login/")


@pytest.mark.django_db
@patch("personas.views.buscar")
def test_consulta_devuelve_sugerencias(buscar_mock, ingresada):
    buscar_mock.return_value = [
        {
            "ruc": "80009735",
            "tipo_documento": TipoDocumento.RUC,
            "documento": "80009735-1",
            "razon_social": "ANDE",
            "fecha_nacimiento": None,
            "label": "ANDE (80009735-1)",
        }
    ]

    response = ingresada.get("/personas/consulta/?q=ande")

    assert response.status_code == 200
    assert response.json()["results"][0]["documento"] == "80009735-1"
    buscar_mock.assert_called_once_with("ande")


@pytest.mark.django_db
@patch("personas.views.consultar_ruc")
def test_consulta_devuelve_la_ficha(consultar_mock, ingresada):
    consultar_mock.return_value = {
        "ruc": "1234567",
        "tipo_documento": TipoDocumento.CEDULA,
        "documento": "1234567",
        "razon_social": "GOMEZ ANA",
        "fecha_nacimiento": "1990-01-15",
        "label": "GOMEZ ANA (1234567)",
    }

    response = ingresada.get("/personas/consulta/?ruc=1234567")

    assert response.status_code == 200
    assert response.json()["fecha_nacimiento"] == "1990-01-15"
    consultar_mock.assert_called_once_with("1234567")


@pytest.mark.django_db
def test_formulario_publica_la_consulta(ingresada):
    response = ingresada.get("/personas/?nueva=1")

    content = response.content.decode()
    assert response.status_code == 200
    assert 'data-persona-consulta="/personas/consulta/"' in content
    assert 'data-persona-campo="documento"' in content
    assert 'data-persona-campo="razon_social"' in content
    assert "js/rupia-personas.js" in content

from datetime import timedelta

import pytest
from django.utils import timezone

from ventas.models import PuntoExpedicion, TipoComprobante


def _hoy():
    return timezone.localdate()


def _payload(tipo=TipoComprobante.TICKET, **extra):
    hoy = _hoy()
    datos = {
        "tipo": tipo,
        "establecimiento": "001",
        "codigo": "001" if tipo == TipoComprobante.TICKET else "002",
        "timbrado": "12345678",
        "vigencia_desde": (hoy - timedelta(days=1)).isoformat(),
        "vigencia_hasta": (hoy + timedelta(days=300)).isoformat(),
        "numero_desde": "1",
        "numero_hasta": "1000",
        "emisor_razon_social": "Rupia SA",
        "emisor_ruc": "80000001-0",
        "emisor_direccion": "Asunción",
        "emisor_telefono": "021000000",
        "emisor_actividad": "Comercio",
        "habilitado": "on",
        "accion": "guardar",
    }
    datos.update(extra)
    return datos


@pytest.mark.django_db
def test_el_menu_muestra_timbrados(ingresada):
    content = ingresada.get("/").content.decode()
    assert 'href="/ventas/timbrados/"' in content
    assert "Timbrados" in content
    assert "Gestión" in content


@pytest.mark.django_db
def test_listado_pide_ingreso(client):
    response = client.get("/ventas/timbrados/")
    assert response.status_code == 302
    assert response.url.startswith("/login/")


@pytest.mark.django_db
def test_alta_ticket_y_factura(ingresada):
    ticket = ingresada.post("/ventas/timbrados/nueva/", _payload())
    registro = PuntoExpedicion.objects.get(tipo=TipoComprobante.TICKET)
    assert ticket.status_code == 302
    assert registro.numero_proximo == 1
    assert registro.habilitado is True
    assert registro.establecimiento == "001"

    factura = ingresada.post(
        "/ventas/timbrados/nueva/",
        _payload(TipoComprobante.FACTURA, timbrado="87654321", numero_proximo="124"),
    )
    assert factura.status_code == 302
    otro = PuntoExpedicion.objects.get(tipo=TipoComprobante.FACTURA)
    assert otro.timbrado == "87654321"
    assert otro.numero_proximo == 124
    assert otro.codigo == "002"


@pytest.mark.django_db
def test_timbrado_exige_ocho_digitos(ingresada):
    corto = ingresada.post("/ventas/timbrados/nueva/", _payload(timbrado="1234567"))
    assert corto.status_code == 200
    assert "8 dígitos" in corto.content.decode()
    assert PuntoExpedicion.objects.count() == 0

    largo = ingresada.post("/ventas/timbrados/nueva/", _payload(timbrado="123456789"))
    assert largo.status_code == 200
    assert PuntoExpedicion.objects.count() == 0


@pytest.mark.django_db
def test_no_repite_tipo(ingresada):
    ingresada.post("/ventas/timbrados/nueva/", _payload())
    repetido = ingresada.post("/ventas/timbrados/nueva/", _payload(timbrado="99999999"))
    assert repetido.status_code == 200
    assert "Ya hay un timbrado para ese tipo de comprobante." in repetido.content.decode()
    assert PuntoExpedicion.objects.count() == 1


@pytest.mark.django_db
def test_editar_deshabilita_timbrado(ingresada):
    ingresada.post("/ventas/timbrados/nueva/", _payload())
    punto = PuntoExpedicion.objects.get()
    datos = _payload(habilitado="")
    datos.pop("habilitado")
    response = ingresada.post(f"/ventas/timbrados/{punto.pk}/", datos)
    assert response.status_code == 302
    punto.refresh_from_db()
    assert punto.habilitado is False


@pytest.mark.django_db
def test_listado_muestra_timbrado(ingresada):
    ingresada.post("/ventas/timbrados/nueva/", _payload())
    content = ingresada.get("/ventas/timbrados/").content.decode()
    assert "12345678" in content
    assert "001-001" in content
    assert "Ticket" in content
    assert "Nuevo timbrado" in content

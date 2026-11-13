import pytest
from django.core.exceptions import ValidationError

from configuracion.testing import crear_usuario_con_permisos
from mesas import comandas, puesto
from mesas.models import EnvioSector, EstadoEnvio, Sector, TipoEnvio
from mesas.test_comandas import _habilitar, carta  # noqa: F401


def _pedido(usuario, carta, **items):  # noqa: F811
    comanda = comandas.abrir(usuario=usuario, mesa=carta["mesa"], personas=2)
    for nombre, cantidad in items.items():
        comandas.agregar(comanda, carta[nombre], usuario=usuario, cantidad=cantidad)
    comandas.enviar(comanda, usuario=usuario)
    return comanda


# --- Cola ----------------------------------------------------------------------


@pytest.mark.django_db
def test_cada_pedido_se_toma_una_sola_vez(usuario, carta):  # noqa: F811
    _pedido(usuario, carta, cerveza="2", milanesa="1")

    primera = puesto.tomar_pendientes(carta["barra"])
    segunda = puesto.tomar_pendientes(carta["barra"])

    assert [envio.sector for envio in primera] == [carta["barra"]]
    assert segunda == []
    envio = EnvioSector.objects.get(sector=carta["barra"])
    assert envio.estado == EstadoEnvio.IMPRESO
    assert envio.impreso_en is not None
    # La cocina sigue teniendo lo suyo pendiente.
    assert EnvioSector.objects.get(sector=carta["cocina"]).estado == EstadoEnvio.PENDIENTE


@pytest.mark.django_db
def test_la_cola_muestra_lo_pendiente_e_impreso_pero_no_lo_listo(usuario, carta):  # noqa: F811
    _pedido(usuario, carta, cerveza="1")
    envio = EnvioSector.objects.get(sector=carta["barra"])

    assert puesto.cola(carta["barra"]) == [envio]
    puesto.tomar_pendientes(carta["barra"])
    assert puesto.cola(carta["barra"]) == [envio]

    puesto.marcar_listo(envio)
    assert puesto.cola(carta["barra"]) == []
    assert puesto.recientes_listos(carta["barra"]) == [envio]
    with pytest.raises(ValidationError, match="ya estaba listo"):
        puesto.marcar_listo(envio)

    puesto.volver_a_cola(envio)
    assert puesto.cola(carta["barra"]) == [envio]


@pytest.mark.django_db
def test_imprimir_a_mano_reserva_lo_pendiente(usuario, carta):  # noqa: F811
    _pedido(usuario, carta, milanesa="1")
    envio = EnvioSector.objects.get()

    puesto.imprimir(envio)

    assert puesto.tomar_pendientes(carta["cocina"]) == []
    envio.refresh_from_db()
    assert envio.estado == EstadoEnvio.IMPRESO


# --- Pantallas -----------------------------------------------------------------


@pytest.mark.django_db
def test_con_un_solo_sector_entra_directo(ingresada, carta):  # noqa: F811
    _habilitar()
    Sector.objects.filter(pk=carta["cocina"].pk).update(activo=False)

    response = ingresada.get("/mesas/puesto/")

    assert response.url == f"/mesas/puesto/{carta['barra'].pk}/"


@pytest.mark.django_db
def test_elegir_sector_y_ver_la_cola(ingresada, usuario, carta):  # noqa: F811
    _habilitar()
    comanda = comandas.abrir(usuario=usuario, mesa=carta["mesa"], personas=2)
    comandas.agregar(comanda, carta["milanesa"], usuario=usuario, nota="bien cocida")
    comandas.enviar(comanda, usuario=usuario)

    elegir = ingresada.get("/mesas/puesto/").content.decode()
    pantalla = ingresada.get(f"/mesas/puesto/{carta['cocina'].pk}/").content.decode()
    barra = ingresada.get(f"/mesas/puesto/{carta['barra'].pk}/?parcial=1").content.decode()

    assert "Barra" in elegir and "Cocina" in elegir
    assert "Mesa 1" in pantalla
    assert "Milanesa" in pantalla
    assert "bien cocida" in pantalla
    assert "Pedido · ronda 1" in pantalla
    assert "--kiosk-printing" in pantalla
    assert "No hay pedidos en preparación." in barra


@pytest.mark.django_db
def test_tomar_devuelve_los_tickets_para_imprimir(ingresada, usuario, carta):  # noqa: F811
    _habilitar()
    _pedido(usuario, carta, cerveza="2")
    url = f"/mesas/puesto/{carta['barra'].pk}/tomar/"

    primera = ingresada.post(url).json()
    segunda = ingresada.post(url).json()

    assert len(primera["tickets"]) == 1
    html = primera["tickets"][0]["html"]
    assert "Mesa 1" in html
    assert "Cerveza" in html
    assert "Ronda 1" in html
    assert "2 pers." in html
    assert segunda["tickets"] == []


@pytest.mark.django_db
def test_la_anulacion_sale_marcada(ingresada, usuario, carta):  # noqa: F811
    _habilitar()
    comanda = _pedido(usuario, carta, cerveza="3")
    ingresada.post(f"/mesas/puesto/{carta['barra'].pk}/tomar/")
    detalle = comanda.detalles.get()
    comandas.anular_linea(detalle, usuario=usuario, motivo="Se equivocó", cantidad="1")

    tickets = ingresada.post(f"/mesas/puesto/{carta['barra'].pk}/tomar/").json()["tickets"]
    pantalla = ingresada.get(f"/mesas/puesto/{carta['barra'].pk}/").content.decode()

    assert len(tickets) == 1
    assert "ANULACIÓN" in tickets[0]["html"]
    assert "Motivo: Se equivocó" in tickets[0]["html"]
    assert "Visto" in pantalla
    anulacion = EnvioSector.objects.get(tipo=TipoEnvio.ANULACION)
    assert anulacion.estado == EstadoEnvio.IMPRESO


@pytest.mark.django_db
def test_listo_reimprimir_y_deshacer(ingresada, usuario, carta):  # noqa: F811
    _habilitar()
    _pedido(usuario, carta, milanesa="1")
    envio = EnvioSector.objects.get()

    reimpresion = ingresada.post(f"/mesas/puesto/envios/{envio.pk}/imprimir/").json()
    listo = ingresada.post(
        f"/mesas/puesto/envios/{envio.pk}/listo/", HTTP_X_REQUESTED_WITH="XMLHttpRequest"
    )
    envio.refresh_from_db()
    assert "Milanesa" in reimpresion["html"]
    assert listo.json() == {"ok": True}
    assert envio.estado == EstadoEnvio.LISTO

    ingresada.post(f"/mesas/puesto/envios/{envio.pk}/deshacer/")
    envio.refresh_from_db()
    assert envio.estado == EstadoEnvio.IMPRESO
    assert envio.listo_en is None


@pytest.mark.django_db
def test_el_puesto_pide_permiso_y_modulo(client, django_user_model, ingresada, carta):  # noqa: F811
    assert ingresada.get("/mesas/puesto/").status_code == 404

    _habilitar()
    mozo = crear_usuario_con_permisos(django_user_model, ("comandas", "ver"), username="mozo")
    client.force_login(mozo)
    assert client.get(f"/mesas/puesto/{carta['barra'].pk}/").status_code == 403
    assert client.post(f"/mesas/puesto/{carta['barra'].pk}/tomar/").status_code == 403


@pytest.mark.django_db
def test_la_cocina_solo_ve_su_pantalla(client, django_user_model, carta):  # noqa: F811
    _habilitar()
    cocina = crear_usuario_con_permisos(
        django_user_model, ("puesto_sector", "ver"), username="cocina"
    )
    client.force_login(cocina)

    menu = client.get(f"/mesas/puesto/{carta['cocina'].pk}/").context["menu"]
    mesas = next(entrada for entrada in menu if entrada["label"] == "Mesas")

    assert [hijo["label"] for hijo in mesas["children"]] == ["Cocina y barra"]
    assert client.get("/mesas/tablero/").status_code == 403


@pytest.mark.django_db
def test_un_sector_inactivo_no_tiene_pantalla(ingresada, carta):  # noqa: F811
    _habilitar()
    Sector.objects.filter(pk=carta["barra"].pk).update(activo=False)

    assert ingresada.get(f"/mesas/puesto/{carta['barra'].pk}/").status_code == 404

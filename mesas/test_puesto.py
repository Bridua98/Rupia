from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

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
    assert "1 abierto" in pantalla
    assert "0 en preparación" in pantalla
    assert "0 listos" in pantalla
    assert "No hay pedidos abiertos." in barra
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
def test_al_marcar_listo_la_cola_muestra_el_pedido_para_devolverlo(ingresada, usuario, carta):  # noqa: F811
    _habilitar()
    _pedido(usuario, carta, milanesa="1", cerveza="2")
    cocina = EnvioSector.objects.get(sector=carta["cocina"])
    puesto.marcar_listo(cocina)

    parcial = ingresada.get(f"/mesas/puesto/{carta['cocina'].pk}/?parcial=1").content.decode()

    assert "0 abiertos" in parcial
    assert "0 en preparación" in parcial
    assert "1 listo" in parcial
    assert "No hay pedidos en preparación." in parcial
    assert "Milanesa" in parcial
    assert "Volver a la cola" in parcial
    assert "listo " in parcial


@pytest.mark.django_db
def test_la_cola_separa_abiertos_preparacion_y_listos(ingresada, usuario, carta):  # noqa: F811
    _habilitar()
    _pedido(usuario, carta, milanesa="1")
    envio = EnvioSector.objects.get(sector=carta["cocina"])
    url = f"/mesas/puesto/{carta['cocina'].pk}/?parcial=1"

    abiertos = ingresada.get(url).content.decode()
    puesto.tomar_pendientes(carta["cocina"])
    en_marcha = ingresada.get(url).content.decode()
    puesto.marcar_listo(envio)
    listos = ingresada.get(url).content.decode()

    assert "1 abierto" in abiertos
    assert "0 en preparación" in abiertos
    assert "Mesa 1" in abiertos
    assert "0 abiertos" in en_marcha
    assert "1 en preparación" in en_marcha
    assert "0 abiertos" in listos
    assert "0 en preparación" in listos
    assert "1 listo" in listos
    assert "Volver a la cola" in listos


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


# --- Horno --------------------------------------------------------------------


def _horno(carta):  # noqa: F811
    Sector.objects.filter(pk=carta["cocina"].pk).update(exige_empezar=True, minutos_demora=12)
    carta["cocina"].refresh_from_db()
    return carta["cocina"]


@pytest.mark.django_db
def test_imprimir_no_mete_al_horno(usuario, carta):  # noqa: F811
    horno = _horno(carta)
    _pedido(usuario, carta, milanesa="1")
    envio = EnvioSector.objects.get(sector=horno)

    puesto.tomar_pendientes(horno)

    envio.refresh_from_db()
    assert envio.estado == EstadoEnvio.IMPRESO
    assert puesto.abiertos(horno) == [envio]
    assert puesto.en_preparacion(horno) == []


@pytest.mark.django_db
def test_empezar_mete_al_horno_una_sola_vez(usuario, carta):  # noqa: F811
    horno = _horno(carta)
    _pedido(usuario, carta, milanesa="1")
    envio = EnvioSector.objects.get(sector=horno)

    puesto.empezar(envio)
    otra = puesto.empezar(envio)

    envio.refresh_from_db()
    assert envio.estado == EstadoEnvio.PREPARACION
    assert envio.empezado_en is not None
    assert otra.empezado_en == envio.empezado_en
    assert puesto.abiertos(horno) == []
    assert puesto.en_preparacion(horno) == [envio]


@pytest.mark.django_db
def test_la_barra_sigue_pasando_a_preparacion_al_imprimir(usuario, carta):  # noqa: F811
    _pedido(usuario, carta, cerveza="1")
    envio = EnvioSector.objects.get(sector=carta["barra"])

    puesto.tomar_pendientes(carta["barra"])

    envio.refresh_from_db()
    assert envio.estado == EstadoEnvio.IMPRESO
    assert puesto.abiertos(carta["barra"]) == []
    assert puesto.en_preparacion(carta["barra"]) == [envio]


@pytest.mark.django_db
def test_el_horno_muestra_cola_empezar_y_preparacion(ingresada, usuario, carta):  # noqa: F811
    _habilitar()
    horno = _horno(carta)
    _pedido(usuario, carta, milanesa="1")
    envio = EnvioSector.objects.get(sector=horno)
    url = f"/mesas/puesto/{horno.pk}/?parcial=1"

    cola = ingresada.get(url).content.decode()
    puesto.tomar_pendientes(horno)
    impresa = ingresada.get(url).content.decode()
    ingresada.post(f"/mesas/puesto/envios/{envio.pk}/empezar/")
    en_marcha = ingresada.get(url).content.decode()

    assert "En cola" in cola
    assert "1 en cola" in cola
    assert "0 en preparación" in cola
    assert "Empezar" in cola
    assert "1 en cola" in impresa
    assert "0 en preparación" in impresa
    assert "0 en cola" in en_marcha
    assert "1 en preparación" in en_marcha
    assert "Empezar" not in en_marcha


@pytest.mark.django_db
def test_deshacer_listo_en_el_horno_vuelve_a_preparacion(usuario, carta):  # noqa: F811
    horno = _horno(carta)
    _pedido(usuario, carta, milanesa="1")
    envio = EnvioSector.objects.get(sector=horno)
    puesto.empezar(envio)
    puesto.marcar_listo(envio)
    puesto.volver_a_cola(envio)

    envio.refresh_from_db()
    assert envio.estado == EstadoEnvio.PREPARACION
    assert envio.listo_en is None
    assert puesto.en_preparacion(horno) == [envio]


@pytest.mark.django_db
def test_el_horno_demora_desde_que_entra(ingresada, usuario, carta):  # noqa: F811
    _habilitar()
    horno = _horno(carta)
    Sector.objects.filter(pk=horno.pk).update(minutos_demora=5)
    _pedido(usuario, carta, milanesa="1")
    envio = EnvioSector.objects.get(sector=horno)
    EnvioSector.objects.filter(pk=envio.pk).update(
        creado_en=timezone.now() - timedelta(minutes=20)
    )
    url = f"/mesas/puesto/{horno.pk}/?parcial=1"

    cola = ingresada.get(url).content.decode()
    puesto.empezar(envio)
    EnvioSector.objects.filter(pk=envio.pk).update(
        empezado_en=timezone.now() - timedelta(minutes=6)
    )
    en_marcha = ingresada.get(url).content.decode()

    assert "is-demorado" not in cola
    assert "is-demorado" in en_marcha


@pytest.mark.django_db
def test_no_se_puede_empezar_un_pedido_listo(usuario, carta):  # noqa: F811
    _horno(carta)
    _pedido(usuario, carta, milanesa="1")
    envio = EnvioSector.objects.get(sector=carta["cocina"])
    puesto.marcar_listo(envio)

    with pytest.raises(ValidationError, match="ya estaba listo"):
        puesto.empezar(envio)

import pytest
from django.contrib.auth import get_user_model

from configuracion.models import Perfil, PerfilPermiso
from inventario.models import ItemMovimiento, TipoMovimiento
from ventas.models import EstadoVenta, PuntoExpedicion, TipoAnulacion, TipoComprobante, Venta
from ventas.test_venta import _preparar


def _cobrar_ticket(client):
    client.post("/ventas/punto-de-venta/agregar/", {"q": "PROD-001"})
    response = client.post("/ventas/punto-de-venta/confirmar/")
    venta = Venta.objects.get(estado=EstadoVenta.COBRADA)
    assert response.url == f"/ventas/{venta.pk}/ticket/"
    return venta


@pytest.mark.django_db
def test_menu_muestra_ventas(ingresada):
    content = ingresada.get("/").content.decode()
    assert 'href="/ventas/"' in content
    assert ">Ventas<" in content or "Ventas" in content


@pytest.mark.django_db
def test_listado_pide_ingreso(client):
    response = client.get("/ventas/")
    assert response.status_code == 302
    assert response.url.startswith("/login/")


@pytest.mark.django_db
def test_listado_muestra_boton_punto_de_venta(ingresada):
    content = ingresada.get("/ventas/").content.decode()
    assert 'button-create" href="/ventas/punto-de-venta/"' in content
    assert ">Punto de venta</span>" in content


@pytest.mark.django_db
def test_listado_sin_permiso_pos_oculta_boton(client, django_user_model):
    user = django_user_model.objects.create_user(
        "backoffice", "backoffice@rupia.local", "Clave-inicial-Rupia-2026"
    )
    perfil = Perfil.objects.create(descripcion="Backoffice")
    for accion in ("ver", "anular", "exportar"):
        PerfilPermiso.objects.create(perfil=perfil, formulario="ventas", accion=accion)
    perfil.usuarios.add(user)
    client.force_login(user)
    content = client.get("/ventas/").content.decode()
    assert 'button-create" href="/ventas/punto-de-venta/"' not in content


@pytest.mark.django_db
def test_listado_exige_permiso(client, django_user_model):
    user = django_user_model.objects.create_user(
        "cajero", "cajero@rupia.local", "Clave-inicial-Rupia-2026"
    )
    perfil = Perfil.objects.create(descripcion="Cajero")
    PerfilPermiso.objects.create(perfil=perfil, formulario="punto_de_venta", accion="ver")
    perfil.usuarios.add(user)
    client.force_login(user)
    response = client.get("/ventas/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_listado_muestra_cobradas_y_omite_en_curso(ingresada):
    _preparar()
    cobrada = _cobrar_ticket(ingresada)
    ingresada.post("/ventas/punto-de-venta/agregar/", {"q": "PROD-001"})
    assert Venta.objects.filter(estado=EstadoVenta.EN_CURSO).exists()

    content = ingresada.get("/ventas/").content.decode()
    assert cobrada.numero_completo in content
    assert "Cobrada" in content
    assert "En curso" not in content
    assert "Anular" in content


@pytest.mark.django_db
def test_anular_fisica_ocupa_el_numero_y_devuelve_stock(ingresada):
    _preparar()
    venta = _cobrar_ticket(ingresada)
    numero = venta.numero_completo
    movimiento = ItemMovimiento.objects.get(tipo=TipoMovimiento.VENTA)
    assert movimiento.es_vigente is True

    response = ingresada.post(
        f"/ventas/{venta.pk}/anular/",
        {"tipo_anulacion": TipoAnulacion.FISICA},
    )
    assert response.status_code == 302
    venta.refresh_from_db()
    movimiento.refresh_from_db()
    assert venta.estado == EstadoVenta.ANULADA
    assert venta.tipo_anulacion == TipoAnulacion.FISICA
    assert movimiento.es_vigente is False
    assert PuntoExpedicion.objects.get(tipo=TipoComprobante.TICKET).numero_proximo == 125

    ingresada.post("/ventas/punto-de-venta/agregar/", {"q": "PROD-001"})
    ingresada.post("/ventas/punto-de-venta/confirmar/")
    nueva = Venta.objects.get(estado=EstadoVenta.COBRADA)
    assert nueva.numero_completo == "001-001-0000125"
    assert nueva.numero_completo != numero
    assert Venta.objects.filter(
        numero_completo=numero, estado=EstadoVenta.ANULADA
    ).exists()


@pytest.mark.django_db
def test_anular_reutilizable_libera_el_numero(ingresada):
    _preparar()
    venta = _cobrar_ticket(ingresada)
    numero = venta.numero_completo

    response = ingresada.post(
        f"/ventas/{venta.pk}/anular/",
        {"tipo_anulacion": TipoAnulacion.REUTILIZABLE},
    )
    assert response.status_code == 302
    venta.refresh_from_db()
    assert venta.estado == EstadoVenta.ANULADA
    assert venta.tipo_anulacion == TipoAnulacion.REUTILIZABLE
    assert ItemMovimiento.objects.get(tipo=TipoMovimiento.VENTA).es_vigente is False
    assert PuntoExpedicion.objects.get(tipo=TipoComprobante.TICKET).numero_proximo == 124

    ingresada.post("/ventas/punto-de-venta/agregar/", {"q": "PROD-001"})
    ingresada.post("/ventas/punto-de-venta/confirmar/")
    nueva = Venta.objects.get(estado=EstadoVenta.COBRADA)
    assert nueva.pk != venta.pk
    assert nueva.numero_completo == numero
    assert nueva.numero_completo == "001-001-0000124"


@pytest.mark.django_db
def test_no_anula_dos_veces(ingresada):
    _preparar()
    venta = _cobrar_ticket(ingresada)
    ingresada.post(
        f"/ventas/{venta.pk}/anular/",
        {"tipo_anulacion": TipoAnulacion.FISICA},
    )
    ingresada.post(
        f"/ventas/{venta.pk}/anular/",
        {"tipo_anulacion": TipoAnulacion.REUTILIZABLE},
    )
    venta.refresh_from_db()
    assert venta.tipo_anulacion == TipoAnulacion.FISICA
    assert "ya está anulada" in ingresada.get("/ventas/").content.decode()


@pytest.mark.django_db
def test_ver_venta_pinta_situacion(ingresada):
    _preparar()
    venta = _cobrar_ticket(ingresada)
    content = ingresada.get(f"/ventas/?venta={venta.pk}&ver=1").content.decode()
    assert "rupia-badge is-vigente" in content
    assert "view-panel is-anulado" not in content

    ingresada.post(
        f"/ventas/{venta.pk}/anular/",
        {"tipo_anulacion": TipoAnulacion.FISICA},
    )
    anulada = ingresada.get(f"/ventas/?venta={venta.pk}&ver=1").content.decode()
    assert "view-panel is-anulado" in anulada
    assert "rupia-badge is-anulado" in anulada
    assert "Este registro está anulado." in anulada


@pytest.mark.django_db
def test_reimprime_venta_de_otro_usuario(ingresada, django_user_model):
    _preparar()
    venta = _cobrar_ticket(ingresada)
    otro = get_user_model().objects.create_user(
        "otra", "otra@rupia.local", "Clave-inicial-Rupia-2026", is_superuser=True
    )
    ingresada.force_login(otro)
    response = ingresada.get(f"/ventas/{venta.pk}/ticket/")
    assert response.status_code == 200
    assert venta.numero_completo in response.content.decode()

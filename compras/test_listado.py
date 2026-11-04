import pytest
from django.contrib.auth import get_user_model

from compras.models import Compra, EstadoCompra
from compras.test_compra import _cabecera, _preparar
from configuracion.models import Perfil, PerfilPermiso
from inventario.models import ItemMovimiento, TipoMovimiento


def _confirmar_factura(client):
    cuenta, proveedor, _item_prod = _preparar()
    client.post("/compras/nueva/agregar/", {"q": "PROD-001"})
    detalle = Compra.objects.get(estado=EstadoCompra.EN_CURSO).detalles.get()
    client.post(
        f"/compras/nueva/lineas/{detalle.pk}/",
        {"accion": "costo", "costo": "8.000"},
    )
    response = client.post("/compras/nueva/confirmar/", _cabecera(cuenta, proveedor))
    compra = Compra.objects.get(estado=EstadoCompra.CONFIRMADA)
    assert response.url == "/compras/"
    return compra


@pytest.mark.django_db
def test_listado_pide_ingreso(client):
    response = client.get("/compras/")
    assert response.status_code == 302
    assert response.url.startswith("/login/")


@pytest.mark.django_db
def test_listado_exige_permiso(client, django_user_model):
    user = django_user_model.objects.create_user(
        "cajero", "cajero@rupia.local", "Clave-inicial-Rupia-2026"
    )
    perfil = Perfil.objects.create(descripcion="Cajero")
    PerfilPermiso.objects.create(perfil=perfil, formulario="punto_de_venta", accion="ver")
    perfil.usuarios.add(user)
    client.force_login(user)
    response = client.get("/compras/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_listado_muestra_confirmadas_y_omite_en_curso(ingresada):
    confirmada = _confirmar_factura(ingresada)
    ingresada.post("/compras/nueva/agregar/", {"q": "PROD-001"})
    assert Compra.objects.filter(estado=EstadoCompra.EN_CURSO).exists()

    content = ingresada.get("/compras/").content.decode()
    assert confirmada.numero_completo in content
    assert "Confirmada" in content
    assert "En curso" not in content
    assert "Anular" in content
    assert "Nueva compra" in content


@pytest.mark.django_db
def test_anular_desactiva_movimiento(ingresada):
    compra = _confirmar_factura(ingresada)
    movimiento = ItemMovimiento.objects.get(tipo=TipoMovimiento.COMPRA)
    assert movimiento.es_vigente is True

    response = ingresada.post(f"/compras/{compra.pk}/anular/")
    assert response.status_code == 302
    compra.refresh_from_db()
    movimiento.refresh_from_db()
    assert compra.estado == EstadoCompra.ANULADA
    assert movimiento.es_vigente is False


@pytest.mark.django_db
def test_alta_exige_permiso(client, django_user_model):
    user = get_user_model().objects.create_user(
        "consulta", "consulta@rupia.local", "Clave-inicial-Rupia-2026"
    )
    perfil = Perfil.objects.create(descripcion="Consulta compras")
    PerfilPermiso.objects.create(perfil=perfil, formulario="compras", accion="ver")
    perfil.usuarios.add(user)
    client.force_login(user)
    lista = client.get("/compras/")
    assert lista.status_code == 200
    assert "Nueva compra" not in lista.content.decode()
    assert client.get("/compras/nueva/").status_code == 403

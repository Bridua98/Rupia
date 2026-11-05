from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from django.core.exceptions import ValidationError
from openpyxl import load_workbook

from configuracion.models import Perfil, PerfilPermiso
from cuentas.models import Cuenta, EstadoTransferencia, Transferencia
from cuentas.transferencia import anular


def _cuenta(descripcion, nombre_corto, **extra):
    return Cuenta.objects.create(descripcion=descripcion, nombre_corto=nombre_corto, **extra)


def _payload(origen, destino, **extra):
    base = {
        "fecha": "2026-11-04",
        "cuenta_origen": str(origen.pk),
        "importe_salida": "10.000",
        "cuenta_destino": str(destino.pk),
        "importe_entrada": "10.000",
        "comprobante": "DEP-001",
        "accion": "guardar",
    }
    base.update(extra)
    return base


@pytest.mark.django_db
def test_listado_pide_ingreso(client):
    response = client.get("/cuentas/transferencias/")

    assert response.status_code == 302
    assert response.url.startswith("/login/")


@pytest.mark.django_db
def test_menu_muestra_transferencias(ingresada):
    response = ingresada.get("/")

    content = response.content.decode()
    assert response.status_code == 200
    assert 'href="/cuentas/transferencias/"' in content
    assert "Transferencias" in content


@pytest.mark.django_db
def test_formulario_pide_salida_y_entrada(ingresada):
    content = ingresada.get("/cuentas/transferencias/?nueva=1").content.decode()
    assert "Cuenta de salida" in content
    assert "Cuenta de entrada" in content
    assert "Importe de salida" in content
    assert "Importe de entrada" in content
    assert "Comprobante" in content
    assert content.index("Importe de salida") < content.index("Importe de entrada")


@pytest.mark.django_db
def test_alta_debita_y_acredita(ingresada, usuario):
    caja = _cuenta("Caja 01", "CAJA")
    banco = _cuenta("Banco Itaú", "ITAU", es_banco=True, numero="123")

    response = ingresada.post("/cuentas/transferencias/nueva/", _payload(caja, banco))

    transferencia = Transferencia.objects.get()
    assert transferencia.cuenta_origen == caja
    assert transferencia.cuenta_destino == banco
    assert transferencia.importe == Decimal("10000")
    assert transferencia.comprobante == "DEP-001"
    assert transferencia.estado == EstadoTransferencia.CONFIRMADA
    assert transferencia.usuario == usuario
    assert transferencia.fecha == date(2026, 11, 4)
    assert response.status_code == 302
    assert response.url == "/cuentas/transferencias/"


@pytest.mark.django_db
def test_importes_distintos_no_graban(ingresada):
    caja = _cuenta("Caja 01", "CAJA")
    banco = _cuenta("Banco Itaú", "ITAU", es_banco=True, numero="123")

    response = ingresada.post(
        "/cuentas/transferencias/nueva/",
        _payload(caja, banco, importe_entrada="9.000"),
    )

    assert response.status_code == 200
    assert "El importe de salida y el de entrada tienen que coincidir." in response.content.decode()
    assert Transferencia.objects.count() == 0


@pytest.mark.django_db
def test_misma_cuenta_no_graba(ingresada):
    caja = _cuenta("Caja 01", "CAJA")

    response = ingresada.post("/cuentas/transferencias/nueva/", _payload(caja, caja))

    assert response.status_code == 200
    assert (
        "La cuenta de salida y la de entrada tienen que ser distintas."
        in response.content.decode()
    )
    assert Transferencia.objects.count() == 0


@pytest.mark.django_db
def test_importe_cero_no_graba(ingresada):
    caja = _cuenta("Caja 01", "CAJA")
    banco = _cuenta("Banco Itaú", "ITAU", es_banco=True, numero="123")

    response = ingresada.post(
        "/cuentas/transferencias/nueva/",
        _payload(caja, banco, importe_salida="0", importe_entrada="0"),
    )

    assert response.status_code == 200
    assert "El importe tiene que ser mayor a cero." in response.content.decode()
    assert Transferencia.objects.count() == 0


@pytest.mark.django_db
def test_listado_y_anular(ingresada, usuario):
    caja = _cuenta("Caja 01", "CAJA")
    banco = _cuenta("Banco Itaú", "ITAU", es_banco=True, numero="123")
    ingresada.post("/cuentas/transferencias/nueva/", _payload(caja, banco))
    transferencia = Transferencia.objects.get()

    lista = ingresada.get("/cuentas/transferencias/")
    content = lista.content.decode()
    assert "Caja 01" in content
    assert "Banco Itaú" in content
    assert "DEP-001" in content
    assert "Anular" in content
    assert "Nueva transferencia" in content

    response = ingresada.post(f"/cuentas/transferencias/{transferencia.pk}/anular/")
    assert response.status_code == 302
    transferencia.refresh_from_db()
    assert transferencia.estado == EstadoTransferencia.ANULADA
    assert transferencia.anulado_por == usuario
    assert transferencia.anulado_en is not None


@pytest.mark.django_db
def test_anular_dos_veces_falla(usuario):
    caja = _cuenta("Caja 01", "CAJA")
    banco = _cuenta("Banco Itaú", "ITAU", es_banco=True, numero="123")
    transferencia = Transferencia.objects.create(
        fecha=date(2026, 11, 4),
        cuenta_origen=caja,
        cuenta_destino=banco,
        importe=Decimal("10000"),
        usuario=usuario,
    )
    anular(transferencia, usuario=usuario)

    with pytest.raises(ValidationError):
        anular(transferencia, usuario=usuario)


@pytest.mark.django_db
def test_alta_exige_permiso(client, django_user_model):
    user = django_user_model.objects.create_user(
        "consulta", "consulta@rupia.local", "Clave-inicial-Rupia-2026"
    )
    perfil = Perfil.objects.create(descripcion="Consulta transferencias")
    PerfilPermiso.objects.create(perfil=perfil, formulario="transferencias", accion="ver")
    perfil.usuarios.add(user)
    client.force_login(user)

    lista = client.get("/cuentas/transferencias/")
    content = lista.content.decode()
    assert lista.status_code == 200
    assert "Nueva transferencia" not in content

    caja = _cuenta("Caja 01", "CAJA")
    banco = _cuenta("Banco Itaú", "ITAU", es_banco=True, numero="123")
    alta = client.post("/cuentas/transferencias/nueva/", _payload(caja, banco))
    assert alta.status_code == 403
    assert Transferencia.objects.count() == 0


@pytest.mark.django_db
def test_exporta_excel(ingresada, usuario):
    caja = _cuenta("Caja 01", "CAJA")
    banco = _cuenta("Banco Itaú", "ITAU", es_banco=True, numero="123")
    Transferencia.objects.create(
        fecha=date(2026, 11, 4),
        cuenta_origen=caja,
        cuenta_destino=banco,
        importe=Decimal("10000"),
        comprobante="DEP-001",
        usuario=usuario,
    )

    response = ingresada.get("/cuentas/transferencias/exportar.xlsx")
    assert response.status_code == 200
    libro = load_workbook(BytesIO(response.content))
    hoja = libro.active
    assert hoja.cell(1, 1).value == "Fecha"
    assert "Caja 01" in str(hoja.cell(2, 2).value)
    assert "Banco Itaú" in str(hoja.cell(2, 3).value)

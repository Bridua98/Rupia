from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from cuentas.models import Cuenta, Transferencia


@pytest.mark.django_db
def test_caja_no_lleva_datos_de_banco():
    cuenta = Cuenta(
        descripcion="Caja principal",
        nombre_corto="CAJA",
        es_banco=False,
        es_tarjeta=True,
        numero="999",
    )
    cuenta.full_clean()
    cuenta.save()
    cuenta.refresh_from_db()

    assert cuenta.es_banco is False
    assert cuenta.es_tarjeta is False
    assert cuenta.numero is None
    assert cuenta.tipo_caja() == "Caja"
    assert str(cuenta) == "Caja principal"


@pytest.mark.django_db
def test_banco_exige_numero():
    cuenta = Cuenta(descripcion="Banco Itaú", nombre_corto="ITAU", es_banco=True)

    with pytest.raises(ValidationError) as error:
        cuenta.full_clean()

    assert "numero" in error.value.message_dict
    assert "Escribí el número de cuenta." in error.value.message_dict["numero"]


@pytest.mark.django_db
def test_tarjeta_es_un_banco():
    cuenta = Cuenta(
        descripcion="Visa Itaú",
        nombre_corto="VISA",
        es_banco=True,
        es_tarjeta=True,
        numero="4111111111111111",
    )
    cuenta.full_clean()
    cuenta.save()

    assert cuenta.tipo_caja() == "Tarjeta"
    assert cuenta.numero == "4111111111111111"


@pytest.mark.django_db
def test_transferencia_exige_cuentas_distintas(django_user_model):
    caja = Cuenta.objects.create(descripcion="Caja principal", nombre_corto="CAJA")
    usuario = django_user_model.objects.create_user("ada", "ada@rupia.local", "x")
    transferencia = Transferencia(
        fecha=date(2026, 11, 4),
        cuenta_origen=caja,
        cuenta_destino=caja,
        importe=Decimal("1000"),
        usuario=usuario,
    )

    with pytest.raises(ValidationError) as error:
        transferencia.full_clean()

    assert "La cuenta de salida y la de entrada tienen que ser distintas." in error.value.messages

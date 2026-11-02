from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from personas.models import Genero, Persona, TipoDocumento


@pytest.mark.django_db
def test_persona_guarda_roles():
    persona = Persona.objects.create(
        tipo_documento=TipoDocumento.RUC,
        documento="80012345-6",
        razon_social="Comercial Este",
        fecha_nacimiento=date(1990, 1, 15),
        genero=Genero.SIN_DEFINIR,
        direccion="Av. España 123",
        celular="0981123456",
        es_cliente=True,
        es_proveedor=True,
    )

    persona.full_clean()
    persona.refresh_from_db()
    assert persona.activo is True
    assert persona.es_empleado is False
    assert persona.fecha_nacimiento == date(1990, 1, 15)
    assert str(persona) == "Comercial Este (80012345-6)"


@pytest.mark.django_db
def test_persona_rechaza_genero_desconocido():
    persona = Persona(
        tipo_documento=TipoDocumento.CEDULA,
        documento="1234567",
        razon_social="Ana Gómez",
        genero="OTRO",
        direccion="Centro",
        es_cliente=True,
    )

    with pytest.raises(ValidationError):
        persona.full_clean()


@pytest.mark.django_db
def test_persona_rechaza_documento_repetido():
    Persona.objects.create(
        tipo_documento=TipoDocumento.CEDULA,
        documento="1234567",
        razon_social="Ana Gómez",
        genero=Genero.FEMENINO,
        direccion="Centro",
        es_cliente=True,
    )
    repetida = Persona(
        tipo_documento=TipoDocumento.CEDULA,
        documento="1234567",
        razon_social="Ana Gómez Dos",
        genero=Genero.FEMENINO,
        direccion="Centro",
        es_cliente=True,
    )

    with pytest.raises(ValidationError) as error:
        repetida.full_clean()

    assert "Ya hay una persona con ese documento." in str(error.value)


@pytest.mark.django_db
def test_persona_exige_al_menos_un_rol():
    persona = Persona(
        tipo_documento=TipoDocumento.CEDULA,
        documento="7654321",
        razon_social="Sin Rol",
        genero=Genero.SIN_DEFINIR,
        direccion="Centro",
    )

    with pytest.raises(ValidationError) as error:
        persona.full_clean()

    assert "Marcá al menos un rol" in str(error.value)


@pytest.mark.django_db
def test_persona_rechaza_fecha_de_nacimiento_futura():
    persona = Persona(
        tipo_documento=TipoDocumento.CEDULA,
        documento="7654321",
        razon_social="Futura",
        fecha_nacimiento=timezone.localdate() + timedelta(days=1),
        genero=Genero.SIN_DEFINIR,
        direccion="Centro",
        es_cliente=True,
    )

    with pytest.raises(ValidationError) as error:
        persona.full_clean()

    assert "La fecha de nacimiento no puede ser futura." in str(error.value)

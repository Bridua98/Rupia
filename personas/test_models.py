from datetime import date

import pytest
from django.core.exceptions import ValidationError

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
    )

    with pytest.raises(ValidationError):
        persona.full_clean()

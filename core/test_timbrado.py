import pytest
from django.core.exceptions import ValidationError

from core.timbrado import interpretar_timbrado


def test_acepta_ocho_digitos():
    assert interpretar_timbrado("12345678") == "12345678"


def test_rechaza_largo_distinto():
    with pytest.raises(ValidationError, match="8 dígitos"):
        interpretar_timbrado("1234567")
    with pytest.raises(ValidationError, match="8 dígitos"):
        interpretar_timbrado("123456789")
    with pytest.raises(ValidationError, match="8 dígitos"):
        interpretar_timbrado("12A45678")


def test_vacio_opcional():
    assert interpretar_timbrado("", requerido=False) == ""
    with pytest.raises(ValidationError, match="Escribí el timbrado"):
        interpretar_timbrado("")

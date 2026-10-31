from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from core.moneda import MonedaField, formatear_guaranies, interpretar_guaranies


def test_formatea_con_punto_de_miles():
    assert formatear_guaranies(Decimal("8500")) == "8.500"
    assert formatear_guaranies(Decimal("1250000.000")) == "1.250.000"
    assert formatear_guaranies(0) == "0"


def test_interpreta_guaranies_con_simbolo_y_sin_el():
    assert interpretar_guaranies("8500") == "8500"
    assert interpretar_guaranies("8.500") == "8500"
    assert interpretar_guaranies("Gs. 1.250.000") == "1250000"
    assert interpretar_guaranies("1.250.000 Gs.") == "1250000"
    assert interpretar_guaranies("₲ 8.500") == "8500"
    assert interpretar_guaranies("   ") == ""


def test_rechaza_decimales_y_agrupacion_invalida():
    with pytest.raises(ValidationError, match="no admite decimales"):
        interpretar_guaranies("8.500,50")
    with pytest.raises(ValidationError, match="importe en guaraníes"):
        interpretar_guaranies("8.50")
    with pytest.raises(ValidationError, match="importe en guaraníes"):
        interpretar_guaranies("12a")


def test_campo_devuelve_decimal_entero():
    campo = MonedaField(required=False)

    assert campo.clean("Gs. 8.500") == Decimal("8500")
    assert campo.clean("") is None
    assert campo.prepare_value(Decimal("8500.000")) == "8.500"
    assert campo.prepare_value("8.500") == "8.500"

    html = str(campo.widget.render("precio", "8.500", attrs={"id": "id_precio"}))
    assert 'data-moneda="guarani"' in html
    assert 'data-moneda-miles="."' in html
    assert campo.widget.simbolo == "Gs."


def test_campo_limita_los_digitos():
    campo = MonedaField(required=False, max_digits=12)

    with pytest.raises(ValidationError, match="12 dígitos"):
        campo.clean("1.000.000.000.000")

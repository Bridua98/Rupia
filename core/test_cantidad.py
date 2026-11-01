from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from core.cantidad import CantidadField, formatear_cantidad, interpretar_cantidad


def test_formatea_con_coma_decimal_y_punto_de_miles():
    assert formatear_cantidad(Decimal("0.3")) == "0,300"
    assert formatear_cantidad(Decimal("12")) == "12"
    assert formatear_cantidad(Decimal("1000")) == "1.000"
    assert formatear_cantidad(Decimal("1250.5")) == "1.250,500"


def test_interpreta_cantidad_paraguaya():
    assert interpretar_cantidad("0,300") == "0.300"
    assert interpretar_cantidad("12,000") == "12.000"
    assert interpretar_cantidad("1.000,000") == "1000.000"
    assert interpretar_cantidad("1.250,5") == "1250.5"
    assert interpretar_cantidad("1.000") == "1000"
    assert interpretar_cantidad("1000") == "1000"
    assert interpretar_cantidad("   ") == ""


def test_rechaza_cantidad_invalida():
    with pytest.raises(ValidationError, match="cantidad"):
        interpretar_cantidad("1,2,3")
    with pytest.raises(ValidationError, match="cantidad"):
        interpretar_cantidad("1.00")
    with pytest.raises(ValidationError, match="cantidad"):
        interpretar_cantidad("12a")


def test_campo_devuelve_decimal():
    campo = CantidadField(required=False)

    assert campo.clean("1.000,000") == Decimal("1000.000")
    assert campo.clean("0,300") == Decimal("0.300")
    assert campo.clean("12") == Decimal("12.000")
    assert campo.clean("") is None
    assert campo.prepare_value(Decimal("1000")) == "1.000"

    html = str(campo.widget.render("valor", "1.000,000", attrs={"id": "id_valor"}))
    assert 'data-cantidad="py"' in html
    assert 'data-cantidad-decimal=","' in html
    assert 'data-cantidad-miles="."' in html

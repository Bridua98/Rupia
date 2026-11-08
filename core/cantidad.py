import re
from decimal import ROUND_HALF_UP, Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from core.moneda import SEPARADOR_DECIMAL, SEPARADOR_MILES

_ENTERO = re.compile(r"^(?:0|[1-9]\d{0,2}(?:\.\d{3})*)$")
_PLANO = re.compile(r"^(?:0|[1-9]\d*)$")


def formatear_cantidad(valor, *, decimales=3) -> str:
    numero = Decimal(valor).quantize(Decimal("1").scaleb(-decimales), rounding=ROUND_HALF_UP)
    signo = "-" if numero < 0 else ""
    numero = abs(numero)
    texto = f"{numero:.{decimales}f}"
    entero, frac = texto.split(".")
    miles = f"{int(entero):,}".replace(",", SEPARADOR_MILES)
    if int(frac) == 0:
        return signo + miles
    return signo + miles + SEPARADOR_DECIMAL + frac


def html_cantidad(valor, *, decimales=3):
    if valor is None:
        return mark_safe("—")
    numero = Decimal(valor)
    if numero < 0:
        tono = "is-neg"
    elif numero == 0:
        tono = "is-cero"
    else:
        tono = "is-pos"
    return format_html(
        '<span class="valor-num {0}" dir="ltr">{1}</span>',
        tono,
        formatear_cantidad(numero, decimales=decimales),
    )


def interpretar_cantidad(valor, *, decimales=3) -> str:
    texto = str(valor).replace("\u00a0", " ").strip()
    if texto == "":
        return ""
    if texto.count(SEPARADOR_DECIMAL) > 1:
        raise ValidationError("Escribí la cantidad.", code="invalid")
    if SEPARADOR_DECIMAL in texto:
        entero, frac = texto.split(SEPARADOR_DECIMAL, 1)
        if not frac.isdigit() or len(frac) > decimales:
            raise ValidationError("Escribí la cantidad.", code="invalid")
        return f"{_entero(entero)}.{frac}"
    if texto.count(".") == 1:
        entero, frac = texto.split(".", 1)
        if frac.isdigit() and len(frac) <= decimales:
            if len(frac) == 3 and _ENTERO.fullmatch(entero or "0") is not None:
                return _entero(texto)
            return f"{_entero(entero or '0')}.{frac}"
    return _entero(texto)


def _entero(texto: str) -> str:
    if texto == "":
        return "0"
    patron = _ENTERO if SEPARADOR_MILES in texto else _PLANO
    if patron.fullmatch(texto) is None:
        raise ValidationError("Escribí la cantidad.", code="invalid")
    return texto.replace(SEPARADOR_MILES, "")


class CantidadInput(forms.TextInput):
    is_cantidad = True

    def __init__(self, attrs=None, *, decimales=3, max_enteros=12):
        base = {
            "placeholder": "0",
            "inputmode": "decimal",
            "autocomplete": "off",
            "data-cantidad": "py",
            "data-cantidad-decimales": str(decimales),
            "data-cantidad-max": str(max_enteros),
            "data-cantidad-miles": SEPARADOR_MILES,
            "data-cantidad-decimal": SEPARADOR_DECIMAL,
        }
        if attrs:
            base.update(attrs)
        super().__init__(attrs=base)


class CantidadField(forms.DecimalField):
    """Cantidad paraguaya: punto de miles y coma decimal."""

    widget = CantidadInput

    def __init__(self, *, max_digits=15, decimal_places=3, **kwargs):
        mensajes = {
            "invalid": "Escribí la cantidad.",
            "max_digits": f"La cantidad admite hasta {max_digits} dígitos.",
        }
        mensajes.update(kwargs.pop("error_messages", {}))
        kwargs["localize"] = False
        if kwargs.get("widget") is None:
            kwargs["widget"] = CantidadInput(
                decimales=decimal_places,
                max_enteros=max_digits - decimal_places,
            )
        self.decimales = decimal_places
        super().__init__(
            max_digits=max_digits,
            decimal_places=decimal_places,
            error_messages=mensajes,
            **kwargs,
        )

    def prepare_value(self, value):
        if value in self.empty_values:
            return ""
        if isinstance(value, str):
            return value
        return formatear_cantidad(value, decimales=self.decimales)

    def to_python(self, value):
        if value in self.empty_values:
            return None
        crudo = interpretar_cantidad(value, decimales=self.decimales)
        if crudo == "":
            return None
        return super().to_python(crudo)

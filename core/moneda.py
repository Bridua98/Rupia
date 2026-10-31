import re
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

SIMBOLO = "Gs."
SEPARADOR_MILES = "."
SEPARADOR_DECIMAL = ","
CODIGO = "guarani"

_SIMBOLO = re.compile(r"(?:gs\.?|₲)", re.IGNORECASE)
_AGRUPADO = re.compile(r"^(?:0|[1-9]\d{0,2}(?:\.\d{3})*)$")
_PLANO = re.compile(r"^(?:0|[1-9]\d*)$")


def formatear_guaranies(valor) -> str:
    numero = Decimal(valor)
    entero = int(numero.quantize(Decimal("1")))
    signo = "-" if entero < 0 else ""
    return signo + f"{abs(entero):,}".replace(",", SEPARADOR_MILES)


def interpretar_guaranies(valor) -> str:
    texto = str(valor).replace("\u00a0", " ").strip()
    texto = _SIMBOLO.sub("", texto).strip()
    if texto == "":
        return ""
    if SEPARADOR_DECIMAL in texto:
        raise ValidationError("El guaraní no admite decimales.", code="decimales")
    if SEPARADOR_MILES in texto:
        valido = _AGRUPADO.fullmatch(texto) is not None
    else:
        valido = _PLANO.fullmatch(texto) is not None
    if not valido:
        raise ValidationError("Escribí un importe en guaraníes.", code="invalid")
    return texto.replace(SEPARADOR_MILES, "")


class MonedaInput(forms.TextInput):
    is_moneda = True
    simbolo = SIMBOLO

    def __init__(self, attrs=None, *, max_enteros=12):
        base = {
            "inputmode": "numeric",
            "data-moneda": CODIGO,
            "data-moneda-max": str(max_enteros),
            "data-moneda-miles": SEPARADOR_MILES,
        }
        if attrs:
            base.update(attrs)
        super().__init__(attrs=base)


class MonedaField(forms.DecimalField):
    """Importe en guaraníes: sin decimales, miles con punto y símbolo Gs."""

    widget = MonedaInput

    def __init__(self, *, max_digits=12, decimal_places=0, **kwargs):
        if decimal_places != 0:
            raise ValueError("Por ahora la moneda solo admite guaraníes, sin decimales.")
        mensajes = {
            "invalid": "Escribí un importe en guaraníes.",
            "max_digits": f"El importe admite hasta {max_digits} dígitos.",
        }
        mensajes.update(kwargs.pop("error_messages", {}))
        kwargs["localize"] = False
        if kwargs.get("widget") is None:
            kwargs["widget"] = MonedaInput(max_enteros=max_digits)
        self.max_enteros = max_digits
        super().__init__(
            max_digits=max_digits,
            decimal_places=0,
            error_messages=mensajes,
            **kwargs,
        )

    def prepare_value(self, value):
        if value in self.empty_values:
            return ""
        if isinstance(value, str):
            return value
        return formatear_guaranies(value)

    def to_python(self, value):
        if value in self.empty_values:
            return None
        digitos = interpretar_guaranies(value)
        if digitos == "":
            return None
        if len(digitos) > self.max_enteros:
            raise ValidationError(
                self.error_messages["max_digits"],
                code="max_digits",
            )
        return super().to_python(digitos)

from decimal import Decimal

from django.db.models import Case, DecimalField, F, When

from inventario.models import TipoMovimiento

TIPOS_SALIDA = frozenset({TipoMovimiento.VENTA, TipoMovimiento.AJUSTE_NEGATIVO})

_CANTIDAD = DecimalField(max_digits=15, decimal_places=3)


def es_salida(tipo) -> bool:
    return tipo in TIPOS_SALIDA


def con_signo_stock(tipo, valor):
    if valor is None:
        return None
    numero = Decimal(valor)
    return -numero if es_salida(tipo) else numero


def expresion_stock(campo):
    return Case(
        When(tipo__in=tuple(TIPOS_SALIDA), then=-F(campo)),
        default=F(campo),
        output_field=_CANTIDAD,
    )

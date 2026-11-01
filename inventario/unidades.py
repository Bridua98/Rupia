from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError

from inventario.models import RelacionUnidad

TRES = Decimal("0.001")


def redondear_cantidad(valor: Decimal) -> Decimal:
    return valor.quantize(TRES, rounding=ROUND_HALF_UP)


def convertir_a_base(item, unidad, cantidad) -> Decimal:
    cantidad = Decimal(cantidad)
    if unidad.pk == item.unidad_medida_id:
        return redondear_cantidad(cantidad)
    relacion = item.unidades.filter(unidad_medida=unidad).first()
    if relacion is None:
        raise ValidationError("Esa unidad no está relacionada con el ítem.", code="sin_relacion")
    if relacion.valor <= 0:
        raise ValidationError("El valor de la relación tiene que ser mayor a 0.", code="valor")
    if relacion.relacion == RelacionUnidad.MENOR:
        resultado = cantidad / relacion.valor
    else:
        resultado = cantidad * relacion.valor
    return redondear_cantidad(resultado)

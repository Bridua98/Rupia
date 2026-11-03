from django.db import IntegrityError, transaction

from inventario.models import ItemCategoria, Marca, UnidadMedida

DEFECTO_ID = 999999999
DEFECTO_NOMBRE = "defecto"
DEFECTO_SIMBOLO = "999999999"


def _buscar(model, **extra):
    encontrado = model.objects.filter(pk=DEFECTO_ID).first()
    if encontrado:
        return encontrado
    encontrado = model.objects.filter(descripcion__iexact=DEFECTO_NOMBRE).first()
    if encontrado:
        return encontrado
    for campo, valor in extra.items():
        encontrado = model.objects.filter(**{campo: valor}).first()
        if encontrado:
            return encontrado
    return None


def _asegurar(model, **extra):
    encontrado = _buscar(model, **extra)
    if encontrado:
        return encontrado
    datos = {"id": DEFECTO_ID, "descripcion": DEFECTO_NOMBRE, **extra}
    try:
        with transaction.atomic():
            return model.objects.create(**datos)
    except IntegrityError:
        encontrado = _buscar(model, **extra)
        if encontrado:
            return encontrado
        raise


def asegurar_referenciales_defecto():
    return {
        "marca": _asegurar(Marca),
        "categoria": _asegurar(ItemCategoria),
        "unidad_medida": _asegurar(UnidadMedida, simbolo=DEFECTO_SIMBOLO),
    }

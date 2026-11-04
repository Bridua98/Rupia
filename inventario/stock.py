from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from inventario.models import (
    AjusteStockDetalle,
    Item,
    ItemMovimiento,
    RelacionUnidad,
    TipoItem,
    TipoMovimiento,
)
from inventario.precios import redondear_guarani
from inventario.unidades import convertir_a_base, redondear_cantidad

TIPOS_SALIDA = frozenset({TipoMovimiento.VENTA, TipoMovimiento.AJUSTE_NEGATIVO})
PREFIJO_AJUSTE = "A"


def secuencia_ajuste(ajuste) -> str:
    pk = getattr(ajuste, "pk", ajuste)
    return f"{PREFIJO_AJUSTE}{pk}"


def siguiente_id(model):
    ultimo = model.objects.select_for_update().order_by("-pk").values_list("pk", flat=True).first()
    return (ultimo or 0) + 1


def siguiente_movimiento_id():
    return siguiente_id(ItemMovimiento)


def stock_desde_movimientos(item, movimientos) -> tuple[Decimal, bool]:
    total = Decimal("0")
    omitidos = False
    for movimiento in movimientos:
        try:
            cantidad_base = convertir_a_base(item, movimiento.unidad_medida, movimiento.cantidad)
        except ValidationError:
            omitidos = True
            continue
        if movimiento.tipo in TIPOS_SALIDA:
            cantidad_base = -cantidad_base
        total += cantidad_base
    return redondear_cantidad(total), omitidos


def stock_actual(item, *, excluir_ajuste_id=None) -> tuple[Decimal, bool]:
    movimientos = item.movimientos.filter(es_vigente=True).select_related("unidad_medida")
    if excluir_ajuste_id is not None:
        movimientos = movimientos.exclude(secuencia_origen=secuencia_ajuste(excluir_ajuste_id))
    return stock_desde_movimientos(item, movimientos)


def cantidad_en_unidad(item, unidad, cantidad_base) -> Decimal:
    cantidad_base = Decimal(cantidad_base)
    if unidad.pk == item.unidad_medida_id:
        return redondear_cantidad(cantidad_base)
    relacion = item.unidades.filter(unidad_medida=unidad).first()
    if relacion is None:
        raise ValidationError("Esa unidad no está relacionada con el ítem.", code="sin_relacion")
    if relacion.valor <= 0:
        raise ValidationError("El valor de la relación tiene que ser mayor a 0.", code="valor")
    if relacion.relacion == RelacionUnidad.MENOR:
        resultado = cantidad_base * relacion.valor
    else:
        resultado = cantidad_base / relacion.valor
    return redondear_cantidad(resultado)


def unidades_con_stock(item, stock_base) -> list[dict]:
    filas = [
        {
            "id": item.unidad_medida_id,
            "descripcion": item.unidad_medida.descripcion,
            "simbolo": item.unidad_medida.simbolo,
            "relacion": "",
            "valor": None,
            "stock": redondear_cantidad(stock_base),
            "base": True,
            "aviso": "",
        }
    ]
    for relacion in item.unidades.select_related("unidad_medida").order_by("id"):
        aviso = ""
        if relacion.valor <= 0:
            stock = None
            aviso = "El valor de la relación tiene que ser mayor a 0."
        elif relacion.relacion == RelacionUnidad.MENOR:
            stock = redondear_cantidad(stock_base * relacion.valor)
        else:
            stock = redondear_cantidad(stock_base / relacion.valor)
        filas.append(
            {
                "id": relacion.unidad_medida_id,
                "descripcion": relacion.unidad_medida.descripcion,
                "simbolo": relacion.unidad_medida.simbolo,
                "relacion": relacion.relacion,
                "valor": relacion.valor,
                "stock": stock,
                "base": False,
                "aviso": aviso,
            }
        )
    return filas


def _asignar_ids_detalles(formset):
    pendientes = []
    for form in formset.forms:
        if form.instance.pk is not None:
            continue
        cleaned = getattr(form, "cleaned_data", None)
        if not cleaned or cleaned.get("DELETE"):
            continue
        pendientes.append(form)
    if not pendientes:
        return
    siguiente = siguiente_id(AjusteStockDetalle)
    for form in pendientes:
        form.instance.pk = siguiente
        siguiente += 1


def _registrar_movimientos(ajuste, detalles):
    siguiente = siguiente_movimiento_id()
    for detalle in detalles:
        if detalle.cantidad_nueva < 0:
            raise ValidationError("La cantidad nueva no puede ser negativa.", code="cantidad")
        if detalle.item.tipo != TipoItem.PRODUCTO:
            raise ValidationError(
                "Los ajustes de stock solo admiten productos.",
                code="item",
            )
        diferencia = detalle.cantidad
        if diferencia == 0:
            continue
        cantidad = abs(diferencia)
        costo = detalle.item.ultimo_costo or Decimal("0")
        precio = detalle.item.precio or Decimal("0")
        ItemMovimiento.objects.create(
            id=siguiente,
            item=detalle.item,
            unidad_medida=detalle.unidad_medida,
            tipo=(
                TipoMovimiento.AJUSTE_POSITIVO if diferencia > 0 else TipoMovimiento.AJUSTE_NEGATIVO
            ),
            fecha_movimiento=ajuste.fecha,
            cantidad=cantidad,
            precio=precio,
            costo=costo,
            subtotal=redondear_guarani(cantidad * costo),
            secuencia_origen=secuencia_ajuste(ajuste),
            secuencia_detalle_origen=detalle.pk,
            es_vigente=True,
        )
        siguiente += 1


def guardar_ajuste(ajuste, *, formset=None) -> bool:
    """Guarda detalles y movimientos. Devuelve True si hubo unidades omitidas."""
    with transaction.atomic():
        ItemMovimiento.objects.filter(
            secuencia_origen=secuencia_ajuste(ajuste),
            es_vigente=True,
        ).update(es_vigente=False)
        if formset is not None:
            _asignar_ids_detalles(formset)
            formset.instance = ajuste
            formset.save()
        detalles = list(
            ajuste.detalles.select_related("item", "unidad_medida", "item__unidad_medida")
        )
        ids = sorted({detalle.item_id for detalle in detalles})
        if ids:
            list(Item.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
        omitidos = False
        for detalle in detalles:
            anterior_base, sin_unidad = stock_actual(
                detalle.item,
                excluir_ajuste_id=ajuste.pk,
            )
            omitidos = omitidos or sin_unidad
            anterior = cantidad_en_unidad(detalle.item, detalle.unidad_medida, anterior_base)
            detalle.cantidad_anterior = anterior
            detalle.cantidad = detalle.cantidad_nueva - anterior
            detalle.save(update_fields=["cantidad_anterior", "cantidad"])
        _registrar_movimientos(ajuste, detalles)
        return omitidos


def eliminar_ajuste(ajuste):
    with transaction.atomic():
        ItemMovimiento.objects.filter(
            secuencia_origen=secuencia_ajuste(ajuste),
            es_vigente=True,
        ).update(es_vigente=False)
        ajuste.delete()

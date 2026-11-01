from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from inventario.models import ItemPrecioHistorial, OrigenPrecio

UNO = Decimal("1")
CIEN = Decimal("100")


@dataclass(frozen=True)
class PrecioCalculado:
    precio_nuevo: Decimal | None
    omitido: str = ""

    @property
    def aplica(self) -> bool:
        return not self.omitido and self.precio_nuevo is not None


@dataclass(frozen=True)
class ResultadoAjuste:
    cambiados: int
    omitidos: int
    lote: str | None


def redondear_guarani(valor: Decimal) -> Decimal:
    return valor.quantize(UNO, rounding=ROUND_HALF_UP)


def base_precio(item) -> Decimal | None:
    if item.precio_segun_costo:
        return item.ultimo_costo
    return item.precio


def calcular_precio_nuevo(item, porcentaje: Decimal) -> PrecioCalculado:
    base = base_precio(item)
    if base is None:
        if item.precio_segun_costo:
            return PrecioCalculado(None, "Sin último costo")
        return PrecioCalculado(None, "Sin precio")
    nuevo = redondear_guarani(base * (UNO + porcentaje / CIEN))
    if item.precio is not None and nuevo == item.precio:
        return PrecioCalculado(nuevo, "Sin cambio")
    return PrecioCalculado(nuevo)


def previsualizar(items, porcentaje: Decimal) -> dict[int, PrecioCalculado]:
    return {item.pk: calcular_precio_nuevo(item, porcentaje) for item in items}


def registrar_cambio_ficha(item, precio_anterior, usuario) -> ItemPrecioHistorial | None:
    if usuario is None or precio_anterior == item.precio:
        return None
    return ItemPrecioHistorial.objects.create(
        item=item,
        precio_anterior=precio_anterior,
        precio_nuevo=item.precio,
        ultimo_costo=item.ultimo_costo,
        porcentaje=None,
        segun_costo=item.precio_segun_costo,
        origen=OrigenPrecio.FICHA,
        usuario=usuario,
        fecha=timezone.now(),
        lote=None,
    )


def aplicar_ajuste(queryset, porcentaje: Decimal, usuario) -> ResultadoAjuste:
    cambiados = 0
    omitidos = 0
    lote = uuid4().hex
    ahora = timezone.now()
    historial = []
    with transaction.atomic():
        for item in queryset.select_for_update().order_by("descripcion", "pk"):
            calculado = calcular_precio_nuevo(item, porcentaje)
            if not calculado.aplica:
                omitidos += 1
                continue
            anterior = item.precio
            item.precio = calculado.precio_nuevo
            item.save(update_fields=["precio"])
            historial.append(
                ItemPrecioHistorial(
                    item=item,
                    precio_anterior=anterior,
                    precio_nuevo=calculado.precio_nuevo,
                    ultimo_costo=item.ultimo_costo,
                    porcentaje=porcentaje,
                    segun_costo=item.precio_segun_costo,
                    origen=OrigenPrecio.MASIVO,
                    usuario=usuario,
                    fecha=ahora,
                    lote=lote,
                )
            )
            cambiados += 1
        if historial:
            ItemPrecioHistorial.objects.bulk_create(historial)
    return ResultadoAjuste(
        cambiados=cambiados,
        omitidos=omitidos,
        lote=lote if cambiados else None,
    )

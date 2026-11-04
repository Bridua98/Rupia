from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from django.utils import timezone

from core.cantidad import formatear_cantidad
from core.moneda import SIMBOLO, formatear_guaranies
from inventario.precios import redondear_guarani
from ventas.cobro import CERO, total_venta
from ventas.models import EstadoVenta, Venta, VentaDetalle

SIN_UNIDAD = "Sin unidad"
SIN_CLIENTE = "Sin cliente"


@dataclass
class CorteTablero:
    nombre: str
    importe: Decimal
    importe_txt: str


@dataclass
class TarjetaUltima:
    numero: str
    fecha: object
    cliente: str
    importe: Decimal
    importe_txt: str


@dataclass
class TarjetaProducto:
    descripcion: str
    cantidad: Decimal
    cantidad_txt: str
    importe: Decimal
    importe_txt: str


@dataclass
class TableroVentas:
    ventas_dia_cantidad: int
    ventas_dia_importe: Decimal
    ventas_dia_importe_txt: str
    ultima: TarjetaUltima | None
    producto: TarjetaProducto | None
    categorias: list[CorteTablero]
    marcas: list[CorteTablero]
    unidades: list[CorteTablero]


def _dinero(valor) -> str:
    return f"{SIMBOLO} {formatear_guaranies(valor)}"


def _netos_lineas(venta, lineas) -> dict[int, Decimal]:
    subtotal = redondear_guarani(sum((linea.subtotal for linea in lineas), CERO))
    descuento = redondear_guarani(venta.descuento or CERO)
    if not lineas:
        return {}
    if subtotal <= 0 or descuento <= 0:
        return {linea.id: redondear_guarani(linea.subtotal) for linea in lineas}
    partes = {
        linea.id: redondear_guarani(descuento * linea.subtotal / subtotal) for linea in lineas
    }
    diferencia = descuento - sum(partes.values(), CERO)
    if diferencia:
        mayor = max(lineas, key=lambda linea: linea.subtotal)
        partes[mayor.id] += diferencia
    return {
        linea.id: redondear_guarani(linea.subtotal - partes.get(linea.id, CERO))
        for linea in lineas
    }


def _ordenar_cortes(acumulado: dict[str, Decimal]) -> list[CorteTablero]:
    ordenados = sorted(acumulado.items(), key=lambda par: (-par[1], par[0]))
    return [
        CorteTablero(nombre=nombre, importe=importe, importe_txt=_dinero(importe))
        for nombre, importe in ordenados
        if importe
    ]


def _cobradas():
    return Venta.objects.filter(estado=EstadoVenta.COBRADA)


def tablero_inicio(hoy=None) -> TableroVentas:
    hoy = hoy or timezone.localdate()
    ultima_venta = _cobradas().select_related("cliente").first()
    ultima = None
    if ultima_venta is not None:
        importe = total_venta(ultima_venta)
        ultima = TarjetaUltima(
            numero=str(ultima_venta),
            fecha=ultima_venta.fecha,
            cliente=ultima_venta.cliente.razon_social if ultima_venta.cliente_id else SIN_CLIENTE,
            importe=importe,
            importe_txt=_dinero(importe),
        )

    ventas_dia = list(_cobradas().filter(fecha=hoy))
    lineas = list(
        VentaDetalle.objects.filter(venta__in=ventas_dia).select_related(
            "item",
            "item__categoria",
            "item__marca",
            "item__unidad_negocio",
        )
    )
    por_venta = defaultdict(list)
    for linea in lineas:
        por_venta[linea.venta_id].append(linea)

    productos = {}
    categorias = defaultdict(lambda: CERO)
    marcas = defaultdict(lambda: CERO)
    unidades = defaultdict(lambda: CERO)
    importe_dia = CERO

    for venta in ventas_dia:
        netos = _netos_lineas(venta, por_venta.get(venta.id, []))
        importe_dia += sum(netos.values(), CERO)
        for linea in por_venta.get(venta.id, []):
            neto = netos[linea.id]
            item = linea.item
            producto = productos.setdefault(
                item.id,
                {
                    "descripcion": item.descripcion,
                    "cantidad": CERO,
                    "importe": CERO,
                },
            )
            producto["cantidad"] += linea.cantidad
            producto["importe"] += neto
            categorias[item.categoria.descripcion] += neto
            marcas[item.marca.descripcion] += neto
            if item.unidad_negocio_id:
                unidades[item.unidad_negocio.descripcion] += neto
            else:
                unidades[SIN_UNIDAD] += neto

    importe_dia = redondear_guarani(importe_dia)
    producto = None
    if productos:
        ganador = max(productos.values(), key=lambda dato: (dato["cantidad"], dato["importe"]))
        producto = TarjetaProducto(
            descripcion=ganador["descripcion"],
            cantidad=ganador["cantidad"],
            cantidad_txt=formatear_cantidad(ganador["cantidad"]),
            importe=ganador["importe"],
            importe_txt=_dinero(ganador["importe"]),
        )

    return TableroVentas(
        ventas_dia_cantidad=len(ventas_dia),
        ventas_dia_importe=importe_dia,
        ventas_dia_importe_txt=_dinero(importe_dia),
        ultima=ultima,
        producto=producto,
        categorias=_ordenar_cortes(categorias),
        marcas=_ordenar_cortes(marcas),
        unidades=_ordenar_cortes(unidades),
    )

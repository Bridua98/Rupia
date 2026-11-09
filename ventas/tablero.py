import math
from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone

from compras.cuotas import total_saldo_pendiente
from compras.models import (
    Compra,
    EstadoCompra,
    EstadoPagoProveedor,
    PagoProveedor,
    TipoCompra,
)
from configuracion.permisos import tiene_permiso
from core.cantidad import formatear_cantidad
from core.moneda import mostrar_guaranies
from cuentas.disponibilidad import mayor_disponibilidad
from inventario.models import AjusteStock
from inventario.precios import redondear_guarani
from ventas.cobro import CERO, total_venta
from ventas.models import CondicionVenta, EstadoVenta, MedioPago, Venta, VentaDetalle

SIN_UNIDAD = "Sin unidad"
SIN_CLIENTE = "Sin cliente"
CIEN = Decimal("100")
IMPORTE = DecimalField(max_digits=15, decimal_places=3)
TIPOS_COMPRA = (TipoCompra.FACTURA_CONTADO, TipoCompra.FACTURA_CREDITO)
MESES_CORTOS = (
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
)
COLOR_CONTADO = "#1e8a4c"
COLOR_CREDITO = "#3b6fd8"
COLOR_OTROS = "#e08a2f"
RADIO_ANILLO = 62
LARGO_ANILLO = 2 * math.pi * RADIO_ANILLO


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
class VariacionTablero:
    porcentaje: Decimal | None
    texto: str
    sentido: str


@dataclass
class SerieTablero:
    puntos: str
    area: str
    vacia: bool


@dataclass
class IndicadorTablero:
    etiqueta: str
    valor: Decimal
    valor_txt: str
    meta: str = ""
    serie: SerieTablero | None = None
    periodo: VariacionTablero | None = None
    anio: VariacionTablero | None = None
    tono: str = ""


@dataclass
class ComparacionTablero:
    ventas: Decimal
    ventas_txt: str
    compras: Decimal
    compras_txt: str
    diferencia: Decimal
    diferencia_txt: str
    ventas_ancho: int
    compras_ancho: int
    ventas_pct: str
    compras_pct: str


@dataclass
class PorcionTablero:
    nombre: str
    importe: Decimal
    importe_txt: str
    porcentaje: int
    color: str
    trazo: str = ""
    offset: str = "0"


@dataclass
class RankingTablero:
    puesto: int
    descripcion: str
    importe: Decimal
    importe_txt: str
    porcentaje: int


@dataclass
class ActividadTablero:
    tipo: str
    titulo: str
    cuando: str
    detalle: str
    href: str


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
    ventas_hoy: IndicadorTablero = field(
        default_factory=lambda: _indicador_vacio("Ventas del día")
    )
    compras_hoy: IndicadorTablero = field(
        default_factory=lambda: _indicador_vacio("Compras del día")
    )
    disponibilidad: IndicadorTablero = field(
        default_factory=lambda: _indicador_vacio("Disponibilidad")
    )
    resultado_mes: IndicadorTablero = field(
        default_factory=lambda: _indicador_vacio("Resultado del mes")
    )
    cuentas: list[CorteTablero] = field(default_factory=list)
    comparacion_dia: ComparacionTablero | None = None
    comparacion_mes: ComparacionTablero | None = None
    liquidez: IndicadorTablero = field(default_factory=lambda: _indicador_vacio("Liquidez"))
    por_pagar: IndicadorTablero = field(
        default_factory=lambda: _indicador_vacio("Cuentas a pagar")
    )
    flujo_mes: IndicadorTablero = field(
        default_factory=lambda: _indicador_vacio("Flujo del mes")
    )
    cobertura: IndicadorTablero = field(default_factory=lambda: _indicador_vacio("Cobertura"))
    ventas_mes: IndicadorTablero = field(
        default_factory=lambda: _indicador_vacio("Ventas del mes")
    )
    compras_mes: IndicadorTablero = field(
        default_factory=lambda: _indicador_vacio("Compras del mes")
    )
    ticket_promedio: IndicadorTablero = field(
        default_factory=lambda: _indicador_vacio("Ticket promedio")
    )
    margen: IndicadorTablero = field(default_factory=lambda: _indicador_vacio("Margen estimado"))
    egresos_mes: IndicadorTablero = field(
        default_factory=lambda: _indicador_vacio("Egresos del mes")
    )
    mostrar_ventas: bool = True
    mostrar_compras: bool = True
    mostrar_resultado: bool = True
    mostrar_disponibilidad: bool = True
    mostrar_cuentas_pagar: bool = True
    mostrar_liquidez: bool = True
    periodo_txt: str = ""
    graficos: dict = field(default_factory=dict)
    distribucion: list[PorcionTablero] = field(default_factory=list)
    ranking: list[RankingTablero] = field(default_factory=list)
    actividades: list[ActividadTablero] = field(default_factory=list)

    @property
    def mostrar_resumen(self) -> bool:
        return (
            self.mostrar_ventas
            or self.mostrar_compras
            or self.mostrar_disponibilidad
            or self.mostrar_resultado
        )

    @property
    def mostrar_gestion(self) -> bool:
        return (
            self.mostrar_ventas
            or self.mostrar_compras
            or self.mostrar_disponibilidad
            or self.mostrar_resultado
        )

    @property
    def mostrar_seccion_liquidez(self) -> bool:
        return self.mostrar_liquidez or self.mostrar_cuentas_pagar

    @property
    def mostrar_vacio(self) -> bool:
        return not (
            self.mostrar_ventas
            or self.mostrar_compras
            or self.mostrar_disponibilidad
            or self.mostrar_cuentas_pagar
        )


def _dinero(valor) -> str:
    return mostrar_guaranies(valor)


def _cero():
    return Value(CERO, output_field=IMPORTE)


def _indicador_vacio(etiqueta: str) -> IndicadorTablero:
    return IndicadorTablero(etiqueta=etiqueta, valor=CERO, valor_txt=_dinero(CERO))


def _fecha_anio_anterior(dia):
    try:
        return dia.replace(year=dia.year - 1)
    except ValueError:
        return dia.replace(year=dia.year - 1, day=28)


def _rango_mes(dia):
    inicio = dia.replace(day=1)
    return inicio, dia


def _rango_mes_anterior(dia):
    inicio_mes = dia.replace(day=1)
    fin_anterior = inicio_mes - timedelta(days=1)
    inicio_anterior = fin_anterior.replace(day=1)
    tope = min(dia.day, monthrange(fin_anterior.year, fin_anterior.month)[1])
    return inicio_anterior, inicio_anterior.replace(day=tope)


def _rango_mes_anio_anterior(dia):
    inicio = _fecha_anio_anterior(dia.replace(day=1))
    tope = min(dia.day, monthrange(inicio.year, inicio.month)[1])
    return inicio, inicio.replace(day=tope)


def _variacion(actual: Decimal, anterior: Decimal) -> VariacionTablero:
    if anterior == 0 and actual == 0:
        return VariacionTablero(porcentaje=None, texto="—", sentido="neutral")
    if anterior == 0:
        sentido = "up" if actual > 0 else "down"
        return VariacionTablero(porcentaje=None, texto="Nuevo", sentido=sentido)
    porcentaje = redondear_guarani(((actual - anterior) / anterior) * CIEN)
    sentido = "up" if porcentaje > 0 else "down" if porcentaje < 0 else "neutral"
    signo = "+" if porcentaje > 0 else ""
    return VariacionTablero(
        porcentaje=porcentaje,
        texto=f"{signo}{int(porcentaje)}%",
        sentido=sentido,
    )


def _serie(valores: list[Decimal]) -> SerieTablero:
    if not any(valores):
        return SerieTablero(puntos="", area="", vacia=True)
    alto = 42
    ancho = 140
    n = len(valores)
    mx = max(valores)
    mn = min(valores)
    span = mx - mn if mx != mn else (mx or Decimal("1"))
    coords = []
    for i, valor in enumerate(valores):
        x = 0 if n == 1 else round(i * (ancho / (n - 1)), 2)
        y = round(alto - 3 - float((valor - mn) / span) * (alto - 6), 2)
        coords.append((x, y))
    puntos = " ".join(f"{x},{y}" for x, y in coords)
    area = f"0,{alto} {puntos} {coords[-1][0]},{alto}"
    return SerieTablero(puntos=puntos, area=area, vacia=False)


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


def _importe_venta():
    return Coalesce(Sum("detalles__subtotal"), _cero()) - Coalesce(F("descuento"), _cero())


def _total_ventas(desde, hasta) -> tuple[Decimal, int]:
    filas = list(
        _cobradas()
        .filter(fecha__gte=desde, fecha__lte=hasta)
        .annotate(importe=_importe_venta())
        .values_list("importe", flat=True)
    )
    total = redondear_guarani(sum((importe or CERO for importe in filas), CERO))
    return total, len(filas)


def _total_compras(desde, hasta, tipos=TIPOS_COMPRA) -> Decimal:
    total = (
        Compra.objects.filter(
            estado=EstadoCompra.CONFIRMADA,
            tipo__in=tipos,
            fecha__gte=desde,
            fecha__lte=hasta,
        ).aggregate(total=Coalesce(Sum("detalles__subtotal"), _cero()))["total"]
        or CERO
    )
    return redondear_guarani(total)


def _serie_diaria(desde, hasta, por_fecha: dict[object, Decimal]) -> SerieTablero:
    valores = []
    dia = desde
    while dia <= hasta:
        valores.append(por_fecha.get(dia, CERO))
        dia += timedelta(days=1)
    return _serie(valores)


def _mapa_ventas(desde, hasta) -> dict:
    filas = (
        _cobradas()
        .filter(fecha__gte=desde, fecha__lte=hasta)
        .annotate(importe=_importe_venta())
        .values_list("fecha", "importe")
    )
    acumulado = defaultdict(lambda: CERO)
    for fecha, importe in filas:
        acumulado[fecha] += importe or CERO
    return {fecha: redondear_guarani(importe) for fecha, importe in acumulado.items()}


def _mapa_compras(desde, hasta) -> dict:
    filas = (
        Compra.objects.filter(
            estado=EstadoCompra.CONFIRMADA,
            tipo__in=TIPOS_COMPRA,
            fecha__gte=desde,
            fecha__lte=hasta,
        )
        .values("fecha")
        .annotate(importe=Coalesce(Sum("detalles__subtotal"), _cero()))
    )
    return {fila["fecha"]: redondear_guarani(fila["importe"] or CERO) for fila in filas}


def _indicador(
    etiqueta,
    actual,
    anterior,
    anio_anterior,
    *,
    meta="",
    serie=None,
    tono="",
    invertir=False,
):
    periodo = _variacion(actual, anterior)
    anio = _variacion(actual, anio_anterior)
    if invertir:
        periodo = VariacionTablero(
            porcentaje=periodo.porcentaje,
            texto=periodo.texto,
            sentido=_invertir(periodo.sentido),
        )
        anio = VariacionTablero(
            porcentaje=anio.porcentaje,
            texto=anio.texto,
            sentido=_invertir(anio.sentido),
        )
    return IndicadorTablero(
        etiqueta=etiqueta,
        valor=actual,
        valor_txt=_dinero(actual),
        meta=meta,
        serie=serie,
        periodo=periodo,
        anio=anio,
        tono=tono,
    )


def _invertir(sentido: str) -> str:
    if sentido == "up":
        return "down"
    if sentido == "down":
        return "up"
    return sentido


def _comparacion(ventas: Decimal, compras: Decimal) -> ComparacionTablero:
    tope = max(ventas, compras, Decimal("1"))
    diferencia = redondear_guarani(ventas - compras)
    ventas_ancho = max(8, int((ventas / tope) * 100))
    compras_ancho = max(8, int((compras / tope) * 100))
    if ventas == 0:
        ventas_ancho = 0
    if compras == 0:
        compras_ancho = 0
    total = ventas + compras
    if total:
        ventas_pct = f"{int(redondear_guarani((ventas / total) * CIEN))}%"
        compras_pct = f"{int(redondear_guarani((compras / total) * CIEN))}%"
    else:
        ventas_pct = "—"
        compras_pct = "—"
    return ComparacionTablero(
        ventas=ventas,
        ventas_txt=_dinero(ventas),
        compras=compras,
        compras_txt=_dinero(compras),
        diferencia=diferencia,
        diferencia_txt=_dinero(diferencia),
        ventas_ancho=ventas_ancho,
        compras_ancho=compras_ancho,
        ventas_pct=ventas_pct,
        compras_pct=compras_pct,
    )


def _costo_ventas(desde, hasta) -> Decimal:
    costo_linea = ExpressionWrapper(
        F("cantidad") * Coalesce(F("item__ultimo_costo"), _cero()),
        output_field=IMPORTE,
    )
    total = (
        VentaDetalle.objects.filter(
            venta__estado=EstadoVenta.COBRADA,
            venta__fecha__gte=desde,
            venta__fecha__lte=hasta,
        ).aggregate(total=Coalesce(Sum(costo_linea), _cero()))["total"]
        or CERO
    )
    return redondear_guarani(total)


def _permisos_tablero(user):
    if user is None:
        return True, True, True, True

    ventas = tiene_permiso(user, "ventas", "ver") or tiene_permiso(
        user, "punto_de_venta", "ver"
    )
    compras = tiene_permiso(user, "compras", "ver")
    disponibilidad = tiene_permiso(user, "reporte_disponibilidad", "ver")
    cuentas_pagar = tiene_permiso(user, "reporte_cuentas_pagar", "ver")
    return ventas, compras, disponibilidad, cuentas_pagar


def _inicio_mes_desplazado(dia, meses: int) -> date:
    total = dia.year * 12 + (dia.month - 1) - meses
    anio, mes = divmod(total, 12)
    return date(anio, mes + 1, 1)


def _fin_de_mes(inicio: date, tope: date) -> date:
    ultimo = monthrange(inicio.year, inicio.month)[1]
    return min(inicio.replace(day=ultimo), tope)


def _entero(valor: Decimal) -> int:
    return int(redondear_guarani(valor or CERO))


def _parte(valor: Decimal, total: Decimal) -> int:
    if total <= 0 or valor <= 0:
        return 0
    return int(redondear_guarani((valor / total) * CIEN))


def _etiqueta_mes(dia: date) -> str:
    return MESES_CORTOS[dia.month - 1].capitalize()


def _periodo_txt(dia: date) -> str:
    return f"Este mes ({MESES_CORTOS[dia.month - 1]}. {dia.year})"


def _puntos(fechas, ventas_map, compras_map, etiqueta) -> list[dict]:
    puntos = []
    for dia in fechas:
        ventas = ventas_map.get(dia, CERO)
        compras = compras_map.get(dia, CERO)
        puntos.append(
            {
                "e": etiqueta(dia),
                "v": _entero(ventas),
                "c": _entero(compras),
                "vt": _dinero(ventas),
                "ct": _dinero(compras),
            }
        )
    return puntos


def _fechas(desde, hasta):
    dia = desde
    while dia <= hasta:
        yield dia
        dia += timedelta(days=1)


def _por_mes(mapa) -> dict:
    acumulado = defaultdict(lambda: CERO)
    for fecha, importe in mapa.items():
        acumulado[fecha.replace(day=1)] += importe or CERO
    return acumulado


def _trazar_anillo(porciones: list[PorcionTablero]) -> None:
    visibles = [porcion for porcion in porciones if porcion.porcentaje]
    separacion = 4 if len(visibles) > 1 else 0
    acumulado = 0.0
    for porcion in porciones:
        if not porcion.porcentaje:
            porcion.trazo = f"0 {LARGO_ANILLO:.3f}"
            porcion.offset = "0"
            continue
        largo = LARGO_ANILLO * porcion.porcentaje / 100
        dibujo = max(largo - separacion, 1)
        porcion.trazo = f"{dibujo:.3f} {LARGO_ANILLO:.3f}"
        porcion.offset = f"{-(acumulado + separacion / 2):.3f}"
        acumulado += largo


def _distribucion(contado, credito, otros) -> list[PorcionTablero]:
    total = redondear_guarani(contado + credito + otros)
    porciones = [
        PorcionTablero(
            "Contado",
            redondear_guarani(contado),
            _dinero(contado),
            _parte(contado, total),
            COLOR_CONTADO,
        ),
        PorcionTablero(
            "Crédito",
            redondear_guarani(credito),
            _dinero(credito),
            _parte(credito, total),
            COLOR_CREDITO,
        ),
        PorcionTablero(
            "Otros",
            redondear_guarani(otros),
            _dinero(otros),
            _parte(otros, total),
            COLOR_OTROS,
        ),
    ]
    ajuste = 100 - sum(porcion.porcentaje for porcion in porciones)
    if total > 0 and ajuste:
        mayor = max(porciones, key=lambda porcion: porcion.importe)
        mayor.porcentaje += ajuste
    _trazar_anillo(porciones)
    return porciones


def _ranking(productos: dict, total: Decimal) -> list[RankingTablero]:
    ordenados = sorted(
        productos.values(),
        key=lambda dato: (-dato["importe"], dato["descripcion"]),
    )[:3]
    return [
        RankingTablero(
            puesto=indice,
            descripcion=dato["descripcion"],
            importe=redondear_guarani(dato["importe"]),
            importe_txt=_dinero(dato["importe"]),
            porcentaje=_parte(dato["importe"], total),
        )
        for indice, dato in enumerate(ordenados, start=1)
    ]


def _puede(user, formulario: str) -> bool:
    if user is None:
        return True
    return tiene_permiso(user, formulario, "ver")


def _actividades(*, ventas: bool, compras: bool, pagos: bool, stock: bool):
    eventos = []
    if ventas:
        for venta in (
            _cobradas().annotate(importe=_importe_venta()).order_by("-fecha", "-id")[:4]
        ):
            eventos.append(
                (
                    venta.fecha,
                    venta.id,
                    ActividadTablero(
                        tipo="venta",
                        titulo="Nueva venta registrada",
                        cuando=venta.fecha.strftime("%d/%m/%Y"),
                        detalle=_dinero(venta.importe or CERO),
                        href=reverse("venta_list"),
                    ),
                )
            )
    if compras:
        for compra in (
            Compra.objects.filter(estado=EstadoCompra.CONFIRMADA)
            .annotate(importe=Coalesce(Sum("detalles__subtotal"), _cero()))
            .order_by("-fecha", "-id")[:4]
        ):
            eventos.append(
                (
                    compra.fecha,
                    compra.id,
                    ActividadTablero(
                        tipo="compra",
                        titulo="Compra confirmada",
                        cuando=compra.fecha.strftime("%d/%m/%Y"),
                        detalle=_dinero(compra.importe or CERO),
                        href=reverse("compra_list"),
                    ),
                )
            )
    if pagos:
        for pago in (
            PagoProveedor.objects.filter(estado=EstadoPagoProveedor.CONFIRMADO)
            .order_by("-fecha", "-id")[:4]
        ):
            eventos.append(
                (
                    pago.fecha,
                    pago.id,
                    ActividadTablero(
                        tipo="pago",
                        titulo="Pago a proveedor",
                        cuando=pago.fecha.strftime("%d/%m/%Y"),
                        detalle=_dinero(pago.importe or CERO),
                        href=reverse("pago_proveedor_list"),
                    ),
                )
            )
    if stock:
        ajustes = AjusteStock.objects.prefetch_related("detalles__item").order_by(
            "-fecha", "-id"
        )[:4]
        for ajuste in ajustes:
            nombres = [linea.item.descripcion for linea in ajuste.detalles.all()]
            if not nombres:
                detalle = "Ajuste"
            elif len(nombres) == 1:
                detalle = nombres[0]
            else:
                detalle = f"{nombres[0]} +{len(nombres) - 1}"
            eventos.append(
                (
                    ajuste.fecha,
                    ajuste.id,
                    ActividadTablero(
                        tipo="stock",
                        titulo="Stock actualizado",
                        cuando=ajuste.fecha.strftime("%d/%m/%Y"),
                        detalle=detalle,
                        href=reverse("ajuste_stock_list"),
                    ),
                )
            )
    eventos.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in eventos[:5]]


def tablero_inicio(hoy=None, user=None) -> TableroVentas:
    hoy = hoy or timezone.localdate()
    ayer = hoy - timedelta(days=1)
    mismo_anio = _fecha_anio_anterior(hoy)
    mes_inicio, mes_fin = _rango_mes(hoy)
    mes_ant_inicio, mes_ant_fin = _rango_mes_anterior(hoy)
    mes_anio_inicio, mes_anio_fin = _rango_mes_anio_anterior(hoy)
    semana_inicio = hoy - timedelta(days=6)
    mostrar_ventas, mostrar_compras, mostrar_disponibilidad, mostrar_cuentas_pagar = (
        _permisos_tablero(user)
    )
    mostrar_resultado = mostrar_ventas and mostrar_compras
    mostrar_liquidez = mostrar_disponibilidad and mostrar_cuentas_pagar

    ultima = None
    producto = None
    ventas_dia = []
    categorias = {}
    marcas = {}
    unidades = {}
    importe_dia = CERO
    ventas_ayer = CERO
    ventas_anio = CERO
    ventas_mes = CERO
    ventas_mes_cantidad = 0
    ventas_mes_ant = CERO
    ventas_mes_anio = CERO
    serie_ventas = _serie([])
    ticket = CERO
    costo_mes = CERO
    margen_valor = CERO
    margen_meta = "Sin ventas cobradas en el mes"
    meta_ventas = "Sin ventas cobradas hoy"
    contado_dia = CERO
    credito_dia = CERO
    otros_dia = CERO
    productos = {}

    if mostrar_ventas:
        ultima_venta = _cobradas().select_related("cliente").first()
        if ultima_venta is not None:
            importe = total_venta(ultima_venta)
            ultima = TarjetaUltima(
                numero=str(ultima_venta),
                fecha=ultima_venta.fecha,
                cliente=(
                    ultima_venta.cliente.razon_social
                    if ultima_venta.cliente_id
                    else SIN_CLIENTE
                ),
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

        categorias = defaultdict(lambda: CERO)
        marcas = defaultdict(lambda: CERO)
        unidades = defaultdict(lambda: CERO)

        for venta in ventas_dia:
            netos = _netos_lineas(venta, por_venta.get(venta.id, []))
            neto_venta = sum(netos.values(), CERO)
            importe_dia += neto_venta
            if venta.condicion_venta != CondicionVenta.CONTADO:
                credito_dia += neto_venta
            elif venta.medio == MedioPago.EFECTIVO:
                contado_dia += neto_venta
            else:
                otros_dia += neto_venta
            for linea in por_venta.get(venta.id, []):
                neto = netos[linea.id]
                item = linea.item
                producto_dato = productos.setdefault(
                    item.id,
                    {
                        "descripcion": item.descripcion,
                        "cantidad": CERO,
                        "importe": CERO,
                    },
                )
                producto_dato["cantidad"] += linea.cantidad
                producto_dato["importe"] += neto
                categorias[item.categoria.descripcion] += neto
                marcas[item.marca.descripcion] += neto
                if item.unidad_negocio_id:
                    unidades[item.unidad_negocio.descripcion] += neto
                else:
                    unidades[SIN_UNIDAD] += neto

        importe_dia = redondear_guarani(importe_dia)
        if productos:
            ganador = max(
                productos.values(), key=lambda dato: (dato["cantidad"], dato["importe"])
            )
            producto = TarjetaProducto(
                descripcion=ganador["descripcion"],
                cantidad=ganador["cantidad"],
                cantidad_txt=formatear_cantidad(ganador["cantidad"]),
                importe=ganador["importe"],
                importe_txt=_dinero(ganador["importe"]),
            )

        ventas_ayer, _ = _total_ventas(ayer, ayer)
        ventas_anio, _ = _total_ventas(mismo_anio, mismo_anio)
        ventas_mes, ventas_mes_cantidad = _total_ventas(mes_inicio, mes_fin)
        ventas_mes_ant, _ = _total_ventas(mes_ant_inicio, mes_ant_fin)
        ventas_mes_anio, _ = _total_ventas(mes_anio_inicio, mes_anio_fin)
        serie_ventas = _serie_diaria(semana_inicio, hoy, _mapa_ventas(semana_inicio, hoy))
        ticket = (
            redondear_guarani(importe_dia / Decimal(len(ventas_dia))) if ventas_dia else CERO
        )
        meta_ventas = (
            f"{len(ventas_dia)} comprobante{'' if len(ventas_dia) == 1 else 's'}"
            if ventas_dia
            else "Sin ventas cobradas hoy"
        )
        if mostrar_resultado:
            costo_mes = _costo_ventas(mes_inicio, mes_fin)
            margen_valor = redondear_guarani(ventas_mes - costo_mes)
            if ventas_mes > 0:
                margen_pct = int(redondear_guarani((margen_valor / ventas_mes) * CIEN))
                margen_meta = f"{margen_pct}% sobre ventas del mes"

    compras_hoy = CERO
    compras_ayer = CERO
    compras_anio = CERO
    compras_mes = CERO
    compras_mes_ant = CERO
    compras_mes_anio = CERO
    egresos_mes = CERO
    egresos_mes_ant = CERO
    egresos_mes_anio = CERO
    serie_compras = _serie([])

    if mostrar_compras:
        compras_hoy = _total_compras(hoy, hoy)
        compras_ayer = _total_compras(ayer, ayer)
        compras_anio = _total_compras(mismo_anio, mismo_anio)
        compras_mes = _total_compras(mes_inicio, mes_fin)
        compras_mes_ant = _total_compras(mes_ant_inicio, mes_ant_fin)
        compras_mes_anio = _total_compras(mes_anio_inicio, mes_anio_fin)
        egresos_mes = _total_compras(mes_inicio, mes_fin, tipos=(TipoCompra.EGRESO,))
        egresos_mes_ant = _total_compras(
            mes_ant_inicio, mes_ant_fin, tipos=(TipoCompra.EGRESO,)
        )
        egresos_mes_anio = _total_compras(
            mes_anio_inicio, mes_anio_fin, tipos=(TipoCompra.EGRESO,)
        )
        serie_compras = _serie_diaria(semana_inicio, hoy, _mapa_compras(semana_inicio, hoy))

    resultado_mes = CERO
    resultado_mes_ant = CERO
    resultado_mes_anio = CERO
    if mostrar_resultado:
        resultado_mes = redondear_guarani(ventas_mes - compras_mes - egresos_mes)
        resultado_mes_ant = redondear_guarani(
            ventas_mes_ant - compras_mes_ant - egresos_mes_ant
        )
        resultado_mes_anio = redondear_guarani(
            ventas_mes_anio - compras_mes_anio - egresos_mes_anio
        )

    disponible = CERO
    cuentas = []
    entradas_mes = CERO
    salidas_mes = CERO
    flujo_mes = CERO
    flujo_mes_ant = CERO
    flujo_mes_anio = CERO
    if mostrar_disponibilidad:
        _detalle, resumen, totales = mayor_disponibilidad()
        disponible = redondear_guarani(totales["saldo"])
        cuentas = [
            CorteTablero(
                nombre=fila.cuenta, importe=fila.saldo, importe_txt=_dinero(fila.saldo)
            )
            for fila in sorted(resumen, key=lambda fila: (-fila.saldo, fila.cuenta))
        ]
        _, _resumen_mes, totales_mes = mayor_disponibilidad(
            fecha_desde=mes_inicio, fecha_hasta=mes_fin
        )
        entradas_mes = redondear_guarani(totales_mes["entra"])
        salidas_mes = redondear_guarani(totales_mes["salida"])
        flujo_mes = redondear_guarani(entradas_mes - salidas_mes)
        _, _, totales_mes_ant = mayor_disponibilidad(
            fecha_desde=mes_ant_inicio, fecha_hasta=mes_ant_fin
        )
        flujo_mes_ant = redondear_guarani(
            totales_mes_ant["entra"] - totales_mes_ant["salida"]
        )
        _, _, totales_mes_anio = mayor_disponibilidad(
            fecha_desde=mes_anio_inicio, fecha_hasta=mes_anio_fin
        )
        flujo_mes_anio = redondear_guarani(
            totales_mes_anio["entra"] - totales_mes_anio["salida"]
        )

    por_pagar = CERO
    if mostrar_cuentas_pagar:
        por_pagar = total_saldo_pendiente()

    cobertura_txt = "Sin pasivo"
    cobertura_meta = "No hay saldo pendiente en cuentas a pagar"
    liquidez_tono = ""
    cobertura_dias_txt = "Sin salidas"
    if mostrar_liquidez:
        if por_pagar > 0:
            ratio = (disponible / por_pagar) if por_pagar else CERO
            cobertura_txt = f"{ratio.quantize(Decimal('0.1'))}×"
            cobertura_meta = "Disponible sobre compras a crédito"
            liquidez_tono = "ok" if ratio >= 1 else "alerta"
        else:
            liquidez_tono = "ok" if disponible >= 0 else "alerta"
        dias_mes = max((hoy - mes_inicio).days + 1, 1)
        promedio_salida = (
            redondear_guarani(salidas_mes / Decimal(dias_mes)) if salidas_mes else CERO
        )
        if promedio_salida > 0 and disponible > 0:
            dias_cobertura = int(disponible / promedio_salida)
            cobertura_dias_txt = f"{dias_cobertura} día{'s' if dias_cobertura != 1 else ''}"
        elif disponible <= 0:
            cobertura_dias_txt = "Sin saldo"
            liquidez_tono = "alerta"
        else:
            cobertura_dias_txt = "Sin salidas"

    mapa_ventas = {}
    mapa_compras = {}
    if mostrar_ventas or mostrar_compras:
        desde_grafico = _inicio_mes_desplazado(hoy.replace(day=1), 11)
        if mostrar_ventas:
            mapa_ventas = _mapa_ventas(desde_grafico, hoy)
        if mostrar_compras:
            mapa_compras = _mapa_compras(desde_grafico, hoy)
    ventas_por_mes = _por_mes(mapa_ventas)
    compras_por_mes = _por_mes(mapa_compras)
    meses = [
        _inicio_mes_desplazado(hoy.replace(day=1), desplazamiento)
        for desplazamiento in range(11, -1, -1)
    ]
    graficos = {
        "ventas": mostrar_ventas,
        "compras": mostrar_compras,
        "lineas": {
            "7": _puntos(
                list(_fechas(hoy - timedelta(days=6), hoy)),
                mapa_ventas,
                mapa_compras,
                lambda dia: dia.strftime("%d/%m"),
            ),
            "30": _puntos(
                list(_fechas(hoy - timedelta(days=29), hoy)),
                mapa_ventas,
                mapa_compras,
                lambda dia: dia.strftime("%d/%m"),
            ),
            "12": _puntos(meses, ventas_por_mes, compras_por_mes, _etiqueta_mes),
        },
        "flujo": [],
    }
    if mostrar_disponibilidad:
        for desplazamiento in (2, 1, 0):
            inicio_barra = _inicio_mes_desplazado(hoy.replace(day=1), desplazamiento)
            if desplazamiento == 0:
                entra, sale = entradas_mes, salidas_mes
            else:
                _, _, totales_barra = mayor_disponibilidad(
                    fecha_desde=inicio_barra,
                    fecha_hasta=_fin_de_mes(inicio_barra, hoy),
                )
                entra = redondear_guarani(totales_barra["entra"])
                sale = redondear_guarani(totales_barra["salida"])
            graficos["flujo"].append(
                {
                    "e": _etiqueta_mes(inicio_barra),
                    "entra": _entero(entra),
                    "sale": _entero(sale),
                    "et": _dinero(entra),
                    "st": _dinero(sale),
                }
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
        ventas_hoy=_indicador(
            "Ventas del día",
            importe_dia,
            ventas_ayer,
            ventas_anio,
            meta=meta_ventas,
            serie=serie_ventas,
        ),
        compras_hoy=_indicador(
            "Compras del día",
            compras_hoy,
            compras_ayer,
            compras_anio,
            meta="Facturas confirmadas",
            serie=serie_compras,
            invertir=True,
        ),
        disponibilidad=IndicadorTablero(
            etiqueta="Disponibilidad",
            valor=disponible,
            valor_txt=_dinero(disponible),
            meta=f"{len(cuentas)} cuenta{'s' if len(cuentas) != 1 else ''}"
            if cuentas
            else "Sin movimientos de caja",
            tono="ok" if disponible > 0 else "alerta" if disponible < 0 else "",
        ),
        resultado_mes=_indicador(
            "Resultado del mes",
            resultado_mes,
            resultado_mes_ant,
            resultado_mes_anio,
            meta="Ventas menos compras y egresos",
            tono="ok" if resultado_mes >= 0 else "alerta",
        ),
        cuentas=cuentas,
        comparacion_dia=_comparacion(importe_dia, compras_hoy) if mostrar_resultado else None,
        comparacion_mes=_comparacion(ventas_mes, compras_mes) if mostrar_resultado else None,
        liquidez=IndicadorTablero(
            etiqueta="Saldo líquido",
            valor=disponible,
            valor_txt=_dinero(disponible),
            meta="Caja, banco y tarjeta",
            tono=liquidez_tono,
        ),
        por_pagar=IndicadorTablero(
            etiqueta="Cuentas a pagar",
            valor=por_pagar,
            valor_txt=_dinero(por_pagar),
            meta="Saldo pendiente de cuotas",
            tono="alerta" if mostrar_cuentas_pagar and por_pagar > disponible else "",
        ),
        flujo_mes=_indicador(
            "Flujo de caja del mes",
            flujo_mes,
            flujo_mes_ant,
            flujo_mes_anio,
            meta=f"Entradas {_dinero(entradas_mes)} · Salidas {_dinero(salidas_mes)}",
            tono="ok" if flujo_mes >= 0 else "alerta",
        ),
        cobertura=IndicadorTablero(
            etiqueta="Cobertura",
            valor=disponible,
            valor_txt=cobertura_dias_txt,
            meta=f"{cobertura_txt} · {cobertura_meta}",
            tono=liquidez_tono,
        ),
        ventas_mes=_indicador(
            "Ventas del mes",
            ventas_mes,
            ventas_mes_ant,
            ventas_mes_anio,
            meta=f"{ventas_mes_cantidad} comprobante"
            f"{'' if ventas_mes_cantidad == 1 else 's'}",
        ),
        compras_mes=_indicador(
            "Compras del mes",
            compras_mes,
            compras_mes_ant,
            compras_mes_anio,
            meta="Facturas confirmadas",
            invertir=True,
        ),
        ticket_promedio=IndicadorTablero(
            etiqueta="Ticket promedio",
            valor=ticket,
            valor_txt=_dinero(ticket),
            meta="Sobre ventas cobradas hoy",
        ),
        margen=IndicadorTablero(
            etiqueta="Margen estimado",
            valor=margen_valor,
            valor_txt=_dinero(margen_valor),
            meta=margen_meta,
            tono="ok" if margen_valor >= 0 else "alerta",
        ),
        egresos_mes=_indicador(
            "Egresos del mes",
            egresos_mes,
            egresos_mes_ant,
            egresos_mes_anio,
            meta="Gastos confirmados",
            invertir=True,
        ),
        mostrar_ventas=mostrar_ventas,
        mostrar_compras=mostrar_compras,
        mostrar_resultado=mostrar_resultado,
        mostrar_disponibilidad=mostrar_disponibilidad,
        mostrar_cuentas_pagar=mostrar_cuentas_pagar,
        mostrar_liquidez=mostrar_liquidez,
        periodo_txt=_periodo_txt(hoy),
        graficos=graficos,
        distribucion=_distribucion(contado_dia, credito_dia, otros_dia)
        if mostrar_ventas
        else [],
        ranking=_ranking(productos, importe_dia) if mostrar_ventas else [],
        actividades=_actividades(
            ventas=mostrar_ventas,
            compras=mostrar_compras,
            pagos=_puede(user, "pagos_proveedor"),
            stock=_puede(user, "ajustes_stock"),
        ),
    )


def fecha_minima():
    return date(2000, 1, 1)

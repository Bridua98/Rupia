import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone

from compras.models import CompraDetalle, EstadoCompra, TipoCompra
from compras.tables import ReporteGastosAgrupadoTable, ReporteGastosDetalleTable
from core.listado import (
    apply_filters,
    apply_search,
    filter_specs_for,
    filter_values,
    search_fields_for,
)
from core.mantenimiento import MantenimientoListView
from core.moneda import html_guaranies, mostrar_guaranies
from cuentas.models import Cuenta
from inventario.models import Item, TipoItem
from inventario.precios import redondear_guarani
from negocio.models import UnidadNegocio
from personas.models import Persona

AGRUPAR_DETALLE = ""
AGRUPAR_UNIDAD = "unidad"
AGRUPAR_CUENTA = "cuenta"
AGRUPAR_PRODUCTO = "producto"

AGRUPAR_CHOICES = (
    (AGRUPAR_DETALLE, "Sin agrupar (cada línea)"),
    (AGRUPAR_UNIDAD, "Por unidad de negocio"),
    (AGRUPAR_CUENTA, "Por cuenta"),
    (AGRUPAR_PRODUCTO, "Por producto"),
)

AGRUPAR_LABELS = {
    AGRUPAR_UNIDAD: "Por unidad de negocio",
    AGRUPAR_CUENTA: "Por cuenta",
    AGRUPAR_PRODUCTO: "Por producto",
}

CLASE_CHOICES = (
    (TipoItem.GASTO, "Gasto"),
    (TipoItem.PRODUCTO, "Mercadería"),
)

CLASE_LABELS = dict(CLASE_CHOICES)

ONCE = Decimal("11")
VEINTIUNO = Decimal("21")
CERO = Decimal("0")
CIEN = Decimal("100")
RADIO_ANILLO = 62
LARGO_ANILLO = 2 * math.pi * RADIO_ANILLO
COLOR_MERCADERIA = "#1e8a4c"
COLOR_GASTO = "#7b5ea7"
DIAS_SERIE_DIARIA = 45


@dataclass
class FilaGasto:
    pk: int
    compra_id: int
    fecha: object
    comprobante: str
    tipo_comprobante: str
    proveedor: str
    timbrado: str
    cuenta: str
    cuenta_id: int
    cuenta_corto: str
    unidad_negocio: str
    unidad_negocio_id: int
    unidad_abreviado: str
    producto: str
    producto_id: int
    tipo_item: str
    tasa_iva: int
    gravado: Decimal
    iva: Decimal
    subtotal: Decimal


@dataclass
class FilaGastoAgrupada:
    pk: int
    etiqueta: str
    detalle: str
    lineas: int
    gravado: Decimal
    iva: Decimal
    subtotal: Decimal


@dataclass
class VariacionPanel:
    texto: str
    sentido: str


@dataclass
class SeriePanel:
    puntos: str
    area: str
    vacia: bool


@dataclass
class IndicadorPanel:
    etiqueta: str
    valor_txt: str
    meta: str = ""
    serie: SeriePanel | None = None
    periodo: VariacionPanel | None = None
    tono: str = ""


@dataclass
class PorcionPanel:
    nombre: str
    importe: Decimal
    importe_txt: str
    porcentaje: int
    color: str
    trazo: str = ""
    offset: str = "0"


@dataclass
class PanelGastos:
    desde: str
    hasta: str
    total: IndicadorPanel
    gravado: IndicadorPanel
    iva: IndicadorPanel
    comprobantes: IndicadorPanel
    clases: list
    hay_clases: bool
    evolucion: dict


def _parse_fecha(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _texto_fecha(value) -> str:
    dia = _parse_fecha(value)
    return dia.strftime("%d/%m/%Y") if dia else ""


def _variacion(actual: Decimal, anterior: Decimal) -> VariacionPanel:
    if anterior == 0 and actual == 0:
        return VariacionPanel(texto="—", sentido="neutral")
    if anterior == 0:
        return VariacionPanel(texto="Nuevo", sentido="up" if actual > 0 else "down")
    porcentaje = redondear_guarani(((actual - anterior) / anterior) * CIEN)
    sentido = "up" if porcentaje > 0 else "down" if porcentaje < 0 else "neutral"
    signo = "+" if porcentaje > 0 else ""
    return VariacionPanel(texto=f"{signo}{int(porcentaje)}%", sentido=sentido)


def _serie_spark(valores: list[Decimal]) -> SeriePanel:
    if not any(valores):
        return SeriePanel(puntos="", area="", vacia=True)
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
    return SeriePanel(puntos=puntos, area=area, vacia=False)


def _parte(valor: Decimal, total: Decimal) -> int:
    if total <= 0 or valor <= 0:
        return 0
    return int(redondear_guarani((valor / total) * CIEN))


def _trazar_anillo(porciones: list[PorcionPanel]) -> None:
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


def _clases_dona(filas) -> list[PorcionPanel]:
    mercaderia = sum((fila.subtotal for fila in filas if fila.tipo_item == "Mercadería"), CERO)
    gasto = sum((fila.subtotal for fila in filas if fila.tipo_item == "Gasto"), CERO)
    total = redondear_guarani(mercaderia + gasto)
    porciones = [
        PorcionPanel(
            "Mercadería",
            redondear_guarani(mercaderia),
            mostrar_guaranies(mercaderia),
            _parte(mercaderia, total),
            COLOR_MERCADERIA,
        ),
        PorcionPanel(
            "Gasto",
            redondear_guarani(gasto),
            mostrar_guaranies(gasto),
            _parte(gasto, total),
            COLOR_GASTO,
        ),
    ]
    ajuste = 100 - sum(porcion.porcentaje for porcion in porciones)
    if total > 0 and ajuste:
        mayor = max(porciones, key=lambda porcion: porcion.importe)
        mayor.porcentaje += ajuste
    _trazar_anillo(porciones)
    return porciones


def _mapa_importe(filas, getter) -> dict:
    acumulado = defaultdict(lambda: CERO)
    for fila in filas:
        acumulado[fila.fecha] += getter(fila)
    return dict(acumulado)


def _mapa_comprobantes(filas) -> dict:
    ids = defaultdict(set)
    for fila in filas:
        ids[fila.fecha].add(fila.compra_id)
    return {fecha: Decimal(len(compras)) for fecha, compras in ids.items()}


def _usar_semanas(desde: date, hasta: date) -> bool:
    return (hasta - desde).days + 1 > DIAS_SERIE_DIARIA


def _buckets(desde: date, hasta: date):
    if not _usar_semanas(desde, hasta):
        dia = desde
        while dia <= hasta:
            yield dia, dia, dia.strftime("%d/%m")
            dia += timedelta(days=1)
        return
    inicio = desde
    while inicio <= hasta:
        fin = min(inicio + timedelta(days=6), hasta)
        yield inicio, fin, inicio.strftime("%d/%m")
        inicio = fin + timedelta(days=1)


def _valores_rango(desde: date, hasta: date, por_fecha: dict) -> list[Decimal]:
    valores = []
    for inicio, fin, _etiqueta in _buckets(desde, hasta):
        total = CERO
        dia = inicio
        while dia <= fin:
            total += por_fecha.get(dia, CERO)
            dia += timedelta(days=1)
        valores.append(total)
    return valores


def _puntos_evolucion(desde: date, hasta: date, por_fecha: dict) -> list[dict]:
    puntos = []
    for inicio, fin, etiqueta in _buckets(desde, hasta):
        total = CERO
        dia = inicio
        while dia <= fin:
            total += por_fecha.get(dia, CERO)
            dia += timedelta(days=1)
        puntos.append({"e": etiqueta, "v": int(total), "vt": mostrar_guaranies(total)})
    return puntos


def _totales_filas(filas) -> dict:
    return {
        "gravado": sum((fila.gravado for fila in filas), CERO),
        "iva": sum((fila.iva for fila in filas), CERO),
        "subtotal": sum((fila.subtotal for fila in filas), CERO),
        "comprobantes": Decimal(len({fila.compra_id for fila in filas})),
    }


def _indicador(etiqueta, valor, anterior, serie, formatear) -> IndicadorPanel:
    return IndicadorPanel(
        etiqueta=etiqueta,
        valor_txt=formatear(valor),
        serie=serie,
        periodo=_variacion(valor, anterior),
    )


def liquidar_linea(subtotal, tasa) -> tuple[Decimal, Decimal]:
    """IVA incluido, con la misma regla que la liquidación del comprobante."""
    importe = Decimal(subtotal or 0)
    tasa = int(tasa or 0)
    if tasa == 10 and importe:
        iva = redondear_guarani(importe / ONCE)
        return importe - iva, iva
    if tasa == 5 and importe:
        iva = redondear_guarani(importe / VEINTIUNO)
        return importe - iva, iva
    return importe, CERO


def _specs_detalle(view):
    return [spec for spec in filter_specs_for(view) if spec.get("kind") != "skip"]


class ReporteGastosListView(MantenimientoListView):
    template_name = "compras/reporte_gastos_list.html"
    model = CompraDetalle
    permiso_formulario = "reporte_gastos"
    page_title = "Informe de gastos"
    eyebrow = "Gestión"
    title = "Informe de gastos"
    create_label = ""
    show_create = False
    list_hint = (
        "Líneas de compras confirmadas: gastos y mercaderías. "
        "El IVA está incluido en el total."
    )
    search_label = "Buscar"
    search_placeholder = "Buscar por producto, proveedor, comprobante o cuenta..."
    search_fields = (
        "item__descripcion",
        "compra__numero_completo",
        "compra__proveedor__razon_social",
        "compra__cuenta__descripcion",
        "unidad_negocio__descripcion",
    )
    filters = (
        {
            "name": "fecha_desde",
            "label": "Desde",
            "kind": "date",
            "field": "compra__fecha",
            "lookup": "gte",
            "default": "month_start",
        },
        {
            "name": "fecha_hasta",
            "label": "Hasta",
            "kind": "date",
            "field": "compra__fecha",
            "lookup": "lte",
            "default": "today",
        },
        {
            "name": "compra__tipo",
            "label": "Tipo de comprobante",
            "kind": "choice",
            "choices": TipoCompra.choices,
        },
        {
            "name": "item__tipo",
            "label": "Clase",
            "kind": "choice",
            "choices": CLASE_CHOICES,
        },
        {
            "name": "compra__cuenta",
            "label": "Cuenta",
            "kind": "fk",
            "queryset": lambda: Cuenta.objects.order_by("descripcion"),
        },
        {
            "name": "unidad_negocio",
            "label": "Unidad de negocio",
            "kind": "fk",
            "queryset": lambda: UnidadNegocio.objects.order_by("descripcion"),
        },
        {
            "name": "compra__proveedor",
            "label": "Proveedor",
            "kind": "fk",
            "queryset": lambda: Persona.objects.filter(es_proveedor=True).order_by("razon_social"),
        },
        {
            "name": "item",
            "label": "Producto",
            "kind": "fk",
            "queryset": lambda: Item.objects.filter(
                tipo__in=(TipoItem.GASTO, TipoItem.PRODUCTO)
            ).order_by("descripcion"),
        },
        {
            "name": "agrupar",
            "label": "Agrupar por",
            "kind": "skip",
            "choices": AGRUPAR_CHOICES,
        },
    )
    record_noun = "línea"
    order_by = ("-compra__fecha", "-compra_id", "id")
    list_url_name = "reporte_gastos"
    per_page = 15
    back_url_name = "home"
    print_url_name = "reporte_gastos_print"
    export_xlsx_url_name = "reporte_gastos_export_xlsx"
    export_pdf_url_name = "reporte_gastos_export_pdf"
    export_basename = "informe-gastos"
    export_totals = True
    selection_param = "reporte_sel"

    def agrupar(self):
        return filter_values(self.request, filter_specs_for(self)).get("agrupar", AGRUPAR_DETALLE)

    def detalles_queryset(self, valores=None):
        queryset = (
            CompraDetalle.objects.filter(
                compra__estado=EstadoCompra.CONFIRMADA,
                item__tipo__in=(TipoItem.GASTO, TipoItem.PRODUCTO),
            )
            .select_related(
                "compra",
                "compra__proveedor",
                "compra__cuenta",
                "item",
                "unidad_negocio",
            )
            .order_by(*self.order_by)
        )
        queryset = apply_search(queryset, self.query(), search_fields_for(self))
        specs = _specs_detalle(self)
        if valores is None:
            valores = filter_values(self.request, specs)
        return apply_filters(queryset, valores, specs)

    def _detalle(self):
        if not hasattr(self, "_detalle_cache"):
            self._detalle_cache = self._armar_detalle()
        return self._detalle_cache

    def _armar_detalle(self, valores=None):
        filas = []
        for detalle in self.detalles_queryset(valores):
            compra = detalle.compra
            gravado, iva = liquidar_linea(detalle.subtotal, detalle.tasa_iva)
            negocio = detalle.unidad_negocio
            cuenta = compra.cuenta
            filas.append(
                FilaGasto(
                    pk=detalle.pk,
                    compra_id=compra.pk,
                    fecha=compra.fecha,
                    comprobante=compra.numero_completo or f"Egreso {compra.pk}",
                    tipo_comprobante=compra.get_tipo_display(),
                    proveedor=compra.proveedor.razon_social if compra.proveedor_id else "—",
                    timbrado=compra.timbrado or "—",
                    cuenta=cuenta.descripcion if cuenta else "—",
                    cuenta_id=compra.cuenta_id or 0,
                    cuenta_corto=cuenta.nombre_corto if cuenta else "",
                    unidad_negocio=negocio.descripcion if negocio else "—",
                    unidad_negocio_id=detalle.unidad_negocio_id or 0,
                    unidad_abreviado=negocio.abreviado if negocio else "",
                    producto=detalle.item.descripcion,
                    producto_id=detalle.item_id,
                    tipo_item=CLASE_LABELS.get(detalle.item.tipo, detalle.item.tipo),
                    tasa_iva=int(detalle.tasa_iva),
                    gravado=gravado,
                    iva=iva,
                    subtotal=detalle.subtotal,
                )
            )
        return filas

    def _filas_agrupadas(self, filas, modo):
        grupos = {}
        for fila in filas:
            if modo == AGRUPAR_UNIDAD:
                clave = fila.unidad_negocio_id
                etiqueta = fila.unidad_negocio if clave else "Sin unidad de negocio"
                detalle = fila.unidad_abreviado
            elif modo == AGRUPAR_CUENTA:
                clave = fila.cuenta_id
                etiqueta = fila.cuenta if clave else "Sin cuenta"
                detalle = fila.cuenta_corto
            else:
                clave = fila.producto_id
                etiqueta = fila.producto
                detalle = fila.tipo_item
            grupo = grupos.get(clave)
            if grupo is None:
                grupo = FilaGastoAgrupada(
                    pk=clave or 0,
                    etiqueta=etiqueta,
                    detalle=detalle,
                    lineas=0,
                    gravado=CERO,
                    iva=CERO,
                    subtotal=CERO,
                )
                grupos[clave] = grupo
            grupo.lineas += 1
            grupo.gravado += fila.gravado
            grupo.iva += fila.iva
            grupo.subtotal += fila.subtotal
        return sorted(grupos.values(), key=lambda fila: fila.etiqueta.lower())

    def get_queryset(self):
        filas = self._detalle()
        modo = self.agrupar()
        if modo and modo != AGRUPAR_DETALLE:
            return self._filas_agrupadas(filas, modo)
        return filas

    @property
    def table_class(self):
        modo = self.agrupar()
        if modo and modo != AGRUPAR_DETALLE:
            return ReporteGastosAgrupadoTable
        return ReporteGastosDetalleTable

    def creating(self):
        return False

    def panel_pk(self):
        return None

    def get_table_kwargs(self):
        return {}

    def totales_raw(self):
        datos = _totales_filas(self._detalle())
        return {
            "gravado": datos["gravado"],
            "iva": datos["iva"],
            "subtotal": datos["subtotal"],
        }

    def _rango_actual(self):
        valores = filter_values(self.request, _specs_detalle(self))
        desde = _parse_fecha(valores.get("fecha_desde"))
        hasta = _parse_fecha(valores.get("fecha_hasta"))
        hoy = timezone.localdate()
        if desde is None:
            desde = hoy.replace(day=1)
        if hasta is None:
            hasta = hoy
        if hasta < desde:
            desde, hasta = hasta, desde
        return desde, hasta, valores

    def _detalle_anterior(self, desde, hasta, valores):
        dias = (hasta - desde).days + 1
        prev_hasta = desde - timedelta(days=1)
        prev_desde = prev_hasta - timedelta(days=dias - 1)
        anteriores = dict(valores)
        anteriores["fecha_desde"] = prev_desde.isoformat()
        anteriores["fecha_hasta"] = prev_hasta.isoformat()
        return self._armar_detalle(anteriores)

    def _panel(self):
        filas = self._detalle()
        desde, hasta, valores = self._rango_actual()
        actual = _totales_filas(filas)
        anterior = _totales_filas(self._detalle_anterior(desde, hasta, valores))
        por_total = _mapa_importe(filas, lambda fila: fila.subtotal)
        por_gravado = _mapa_importe(filas, lambda fila: fila.gravado)
        por_iva = _mapa_importe(filas, lambda fila: fila.iva)
        por_comp = _mapa_comprobantes(filas)
        serie_total = _serie_spark(_valores_rango(desde, hasta, por_total))
        clases = _clases_dona(filas)
        return PanelGastos(
            desde=_texto_fecha(desde),
            hasta=_texto_fecha(hasta),
            total=_indicador(
                "Total gastos",
                actual["subtotal"],
                anterior["subtotal"],
                serie_total,
                mostrar_guaranies,
            ),
            gravado=_indicador(
                "Gravado",
                actual["gravado"],
                anterior["gravado"],
                _serie_spark(_valores_rango(desde, hasta, por_gravado)),
                mostrar_guaranies,
            ),
            iva=_indicador(
                "IVA",
                actual["iva"],
                anterior["iva"],
                _serie_spark(_valores_rango(desde, hasta, por_iva)),
                mostrar_guaranies,
            ),
            comprobantes=_indicador(
                "Comprobantes",
                actual["comprobantes"],
                anterior["comprobantes"],
                _serie_spark(_valores_rango(desde, hasta, por_comp)),
                lambda valor: str(int(valor)),
            ),
            clases=clases,
            hay_clases=any(porcion.porcentaje for porcion in clases),
            evolucion={
                "gastos": True,
                "lineas": {"gastos": _puntos_evolucion(desde, hasta, por_total)},
            },
        )

    def totales_formateados(self):
        datos = self.totales_raw()
        return {
            "gravado": mostrar_guaranies(datos["gravado"]),
            "iva": mostrar_guaranies(datos["iva"]),
            "subtotal": mostrar_guaranies(datos["subtotal"]),
            "gravado_html": html_guaranies(datos["gravado"]),
            "iva_html": html_guaranies(datos["iva"]),
            "subtotal_html": html_guaranies(datos["subtotal"]),
        }

    def get_table(self, **kwargs):
        table = super().get_table(**kwargs)
        table.reporte_totales = self.totales_formateados()
        table.modo_agrupado = bool(self.agrupar() and self.agrupar() != AGRUPAR_DETALLE)
        return table

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        modo = self.agrupar()
        agrupado = bool(modo and modo != AGRUPAR_DETALLE)
        context["reporte_agrupado"] = modo if agrupado else ""
        context["reporte_agrupado_label"] = AGRUPAR_LABELS.get(modo, "")
        context["reporte_resumen_filtros"] = self.resumen_filtros()
        context["reporte_totales"] = self.totales_formateados()
        context["reporte_panel"] = self._panel()
        context["record_noun"] = "fila" if agrupado else self.record_noun
        return context

    def resumen_filtros(self):
        partes = []
        valores = filter_values(self.request, filter_specs_for(self))
        for spec in filter_specs_for(self):
            name = spec["name"]
            value = valores.get(name)
            if not value:
                continue
            label = spec["label"]
            kind = spec.get("kind", "choice")
            if kind == "fk":
                for option in (
                    spec["queryset"]() if callable(spec["queryset"]) else spec["queryset"]
                ):
                    if str(option.pk) == value:
                        partes.append(f"{label}: {option}")
                        break
            elif kind in ("choice", "skip"):
                for val, texto in spec.get("choices", ()):
                    if val == value:
                        partes.append(f"{label}: {texto}")
                        break
            elif kind == "date":
                partes.append(f"{label}: {value}")
        query = self.query()
        if query:
            partes.insert(0, f"Búsqueda: {query}")
        return partes

    def salida_extra_context(self):
        return {
            "reporte_resumen_filtros": self.resumen_filtros(),
            "reporte_agrupado_label": AGRUPAR_LABELS.get(self.agrupar(), ""),
            "reporte_totales": self.totales_formateados(),
        }

    def _salida_context(self):
        context = super()._salida_context()
        if self.export_totals and context["rows"]:
            context["record_count"] = max(0, len(context["rows"]) - 1)
        return context

    def export_dataset(self):
        from core.mantenimiento import _skip_export

        table_class = self.table_class
        queryset = self.get_queryset()
        table = table_class([])
        columns = [column for column in table.columns if not _skip_export(column)]
        headers = [str(column.header) for column in columns]
        rows = []
        for record in queryset:
            row = []
            for column in columns:
                row.append(self._celda_export(column, record))
            rows.append(row)
        if self.export_totals:
            total_row = self.export_totals_row(columns)
            if total_row is not None:
                rows.append(total_row)
        return headers, rows

    def export_totals_row(self, columns):
        totales = self.totales_formateados()
        modo = self.agrupar()
        agrupado = bool(modo and modo != AGRUPAR_DETALLE)
        row = []
        for column in columns:
            name = column.name
            if name in ("gravado", "iva", "subtotal"):
                row.append(totales[name])
            elif name == "etiqueta" and agrupado:
                row.append("Total")
            elif name == "fecha" and not agrupado:
                row.append("Total")
            else:
                row.append("")
        if row and not any(cell == "Total" for cell in row):
            row[0] = "Total"
        return row

    def _celda_export(self, column, record):
        value = column.accessor.resolve(record)
        if value is None or value == "":
            return ""
        name = column.name
        if name in ("gravado", "iva", "subtotal"):
            return mostrar_guaranies(value)
        if name == "fecha" and hasattr(value, "strftime"):
            return value.strftime("%d/%m/%Y")
        if name == "tasa_iva":
            return f"{value}%"
        return value

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from django.db.models import DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce

from compras.models import Compra, EstadoCompra, TipoCompra
from core.listado import filter_specs_for, filter_values
from core.mantenimiento import MantenimientoListView
from core.moneda import html_guaranies, mostrar_guaranies
from cuentas.models import Cuenta
from cuentas.tables import DisponibilidadDetalleTable, DisponibilidadResumenTable
from ventas.models import EstadoVenta, Venta

CERO = Decimal("0")
VISTA_DETALLE = "detalle"
VISTA_CUENTA = "cuenta"
ORIGEN_VENTA = "Venta"
ORIGEN_COMPRA = "Compra"
ORIGEN_EGRESO = "Egreso"

VISTA_CHOICES = (
    (VISTA_DETALLE, "Detalle"),
    (VISTA_CUENTA, "Por cuenta"),
)

VISTA_LABELS = {
    VISTA_CUENTA: "Por cuenta",
}

IMPORTE = DecimalField(max_digits=15, decimal_places=3)


@dataclass
class FilaDisponibilidad:
    pk: str
    cuenta_id: int
    cuenta: str
    fecha: date | None
    comprobante: str
    origen: str
    debe: Decimal | None
    haber: Decimal | None
    saldo: Decimal
    es_saldo_anterior: bool = False


@dataclass
class FilaResumenDisponibilidad:
    pk: int
    cuenta: str
    saldo_anterior: Decimal
    debe: Decimal
    haber: Decimal
    saldo: Decimal


def _cero():
    return Value(CERO, output_field=IMPORTE)


def _parse_fecha(valor):
    if not valor:
        return None
    if isinstance(valor, date):
        return valor
    try:
        return datetime.strptime(str(valor), "%Y-%m-%d").date()
    except ValueError:
        return None


def _coincide(query, *partes):
    if not query:
        return True
    buscado = query.casefold()
    return any(buscado in str(parte or "").casefold() for parte in partes)


def _importe_venta():
    return Coalesce(Sum("detalles__subtotal"), _cero()) - Coalesce(F("descuento"), _cero())


def _importe_compra():
    return Coalesce(Sum("detalles__subtotal"), _cero())


def _comprobante_compra(compra):
    if compra.numero_completo:
        return compra.numero_completo
    if compra.tipo == TipoCompra.EGRESO:
        return f"Egreso {compra.pk}"
    return "—"


def _origen_compra(compra):
    if compra.tipo == TipoCompra.EGRESO:
        return ORIGEN_EGRESO
    return ORIGEN_COMPRA


def movimientos_caja(cuenta_id=None):
    """Ventas cobradas y compras al contado o egresos confirmados, con importe."""
    ventas = (
        Venta.objects.filter(estado=EstadoVenta.COBRADA, cuenta_cobro_id__isnull=False)
        .select_related("cuenta_cobro")
        .annotate(importe=_importe_venta())
    )
    compras = (
        Compra.objects.filter(
            estado=EstadoCompra.CONFIRMADA,
            cuenta_id__isnull=False,
            tipo__in=(TipoCompra.FACTURA_CONTADO, TipoCompra.EGRESO),
        )
        .select_related("cuenta")
        .annotate(importe=_importe_compra())
    )
    if cuenta_id:
        ventas = ventas.filter(cuenta_cobro_id=cuenta_id)
        compras = compras.filter(cuenta_id=cuenta_id)

    filas = []
    for venta in ventas:
        filas.append(
            {
                "cuenta_id": venta.cuenta_cobro_id,
                "cuenta": venta.cuenta_cobro.descripcion,
                "fecha": venta.fecha,
                "comprobante": venta.numero_completo or "—",
                "origen": ORIGEN_VENTA,
                "debe": venta.importe or CERO,
                "haber": CERO,
                "orden": 0,
                "origen_id": venta.pk,
                "clave": f"v-{venta.pk}",
            }
        )
    for compra in compras:
        filas.append(
            {
                "cuenta_id": compra.cuenta_id,
                "cuenta": compra.cuenta.descripcion,
                "fecha": compra.fecha,
                "comprobante": _comprobante_compra(compra),
                "origen": _origen_compra(compra),
                "debe": CERO,
                "haber": compra.importe or CERO,
                "orden": 1,
                "origen_id": compra.pk,
                "clave": f"c-{compra.pk}",
            }
        )
    filas.sort(key=lambda fila: (fila["cuenta"], fila["fecha"], fila["orden"], fila["origen_id"]))
    return filas


def mayor_disponibilidad(*, cuenta_id=None, fecha_desde=None, fecha_hasta=None, query=""):
    desde = _parse_fecha(fecha_desde)
    hasta = _parse_fecha(fecha_hasta)
    movimientos = movimientos_caja(cuenta_id)
    por_cuenta = {}
    for movimiento in movimientos:
        if not _coincide(
            query, movimiento["cuenta"], movimiento["comprobante"], movimiento["origen"]
        ):
            continue
        por_cuenta.setdefault(movimiento["cuenta_id"], []).append(movimiento)

    detalle = []
    resumen = []
    total_debe = CERO
    total_haber = CERO
    total_anterior = CERO
    for cuenta_id_grupo, items in sorted(por_cuenta.items(), key=lambda par: par[1][0]["cuenta"]):
        saldo_anterior = CERO
        periodo = []
        for movimiento in items:
            fecha = movimiento["fecha"]
            if desde and fecha < desde:
                saldo_anterior += movimiento["debe"] - movimiento["haber"]
                continue
            if hasta and fecha > hasta:
                continue
            periodo.append(movimiento)
        if not periodo and saldo_anterior == CERO:
            continue
        cuenta_nombre = items[0]["cuenta"]
        debe_periodo = sum((fila["debe"] for fila in periodo), CERO)
        haber_periodo = sum((fila["haber"] for fila in periodo), CERO)
        total_debe += debe_periodo
        total_haber += haber_periodo
        total_anterior += saldo_anterior
        resumen.append(
            FilaResumenDisponibilidad(
                pk=cuenta_id_grupo,
                cuenta=cuenta_nombre,
                saldo_anterior=saldo_anterior,
                debe=debe_periodo,
                haber=haber_periodo,
                saldo=saldo_anterior + debe_periodo - haber_periodo,
            )
        )
        saldo = saldo_anterior
        if desde:
            detalle.append(
                FilaDisponibilidad(
                    pk=f"a-{cuenta_id_grupo}",
                    cuenta_id=cuenta_id_grupo,
                    cuenta=cuenta_nombre,
                    fecha=None,
                    comprobante="Saldo anterior",
                    origen="",
                    debe=None,
                    haber=None,
                    saldo=saldo,
                    es_saldo_anterior=True,
                )
            )
        for movimiento in periodo:
            saldo = saldo + movimiento["debe"] - movimiento["haber"]
            detalle.append(
                FilaDisponibilidad(
                    pk=movimiento["clave"],
                    cuenta_id=cuenta_id_grupo,
                    cuenta=cuenta_nombre,
                    fecha=movimiento["fecha"],
                    comprobante=movimiento["comprobante"],
                    origen=movimiento["origen"],
                    debe=movimiento["debe"] if movimiento["debe"] else None,
                    haber=movimiento["haber"] if movimiento["haber"] else None,
                    saldo=saldo,
                )
            )
    totales = {
        "debe": total_debe,
        "haber": total_haber,
        "saldo_anterior": total_anterior,
        "saldo": total_anterior + total_debe - total_haber,
    }
    return detalle, resumen, totales


class ReporteDisponibilidadListView(MantenimientoListView):
    template_name = "cuentas/disponibilidad_list.html"
    model = Cuenta
    permiso_formulario = "reporte_disponibilidad"
    page_title = "Disponibilidad"
    eyebrow = "Gestión"
    title = "Disponibilidad"
    create_label = ""
    show_create = False
    list_hint = (
        "Movimientos de caja, banco y tarjeta: ventas cobradas en el debe y compras "
        "al contado o egresos en el haber. El saldo anterior es el de antes de la fecha desde."
    )
    search_label = "Buscar"
    search_placeholder = "Buscar por cuenta, comprobante u origen..."
    search_fields = ()
    filters = (
        {
            "name": "cuenta",
            "label": "Cuenta",
            "kind": "fk",
            "queryset": lambda: Cuenta.objects.order_by("descripcion"),
        },
        {
            "name": "fecha_desde",
            "label": "Desde",
            "kind": "date",
        },
        {
            "name": "fecha_hasta",
            "label": "Hasta",
            "kind": "date",
        },
        {
            "name": "vista",
            "label": "Vista",
            "kind": "skip",
            "choices": VISTA_CHOICES,
        },
    )
    record_noun = "movimiento"
    order_by = ("pk",)
    list_url_name = "reporte_disponibilidad"
    per_page = 15
    back_url_name = "home"
    print_url_name = "reporte_disponibilidad_print"
    export_xlsx_url_name = "reporte_disponibilidad_export_xlsx"
    export_pdf_url_name = "reporte_disponibilidad_export_pdf"
    export_basename = "disponibilidad"
    export_totals = True
    selection_param = "dispon_sel"

    def vista(self):
        return filter_values(self.request, filter_specs_for(self)).get("vista", VISTA_DETALLE)

    def _resultado(self):
        if hasattr(self, "_resultado_cache"):
            return self._resultado_cache
        valores = filter_values(self.request, filter_specs_for(self))
        cuenta = valores.get("cuenta")
        self._resultado_cache = mayor_disponibilidad(
            cuenta_id=int(cuenta) if cuenta and cuenta.isdigit() else None,
            fecha_desde=valores.get("fecha_desde"),
            fecha_hasta=valores.get("fecha_hasta"),
            query=self.query(),
        )
        return self._resultado_cache

    def get_queryset(self):
        detalle, resumen, _totales = self._resultado()
        if self.vista() == VISTA_CUENTA:
            return resumen
        return detalle

    @property
    def table_class(self):
        if self.vista() == VISTA_CUENTA:
            return DisponibilidadResumenTable
        return DisponibilidadDetalleTable

    def creating(self):
        return False

    def panel_pk(self):
        return None

    def page_number_for_pk(self, pk):
        return None

    def get_table_kwargs(self):
        return {}

    def totales_formateados(self):
        _detalle, _resumen, totales = self._resultado()
        return {
            "debe": mostrar_guaranies(totales["debe"]),
            "haber": mostrar_guaranies(totales["haber"]),
            "saldo_anterior": mostrar_guaranies(totales["saldo_anterior"]),
            "saldo": mostrar_guaranies(totales["saldo"]),
            "debe_html": html_guaranies(totales["debe"]),
            "haber_html": html_guaranies(totales["haber"]),
            "saldo_anterior_html": html_guaranies(totales["saldo_anterior"]),
            "saldo_html": html_guaranies(totales["saldo"]),
            "debe_raw": totales["debe"],
            "haber_raw": totales["haber"],
            "saldo_anterior_raw": totales["saldo_anterior"],
            "saldo_raw": totales["saldo"],
        }

    def get_table(self, **kwargs):
        table = super().get_table(**kwargs)
        table.reporte_totales = self.totales_formateados()
        table.modo_resumen = self.vista() == VISTA_CUENTA
        return table

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        modo = self.vista()
        context["reporte_agrupado"] = modo if modo == VISTA_CUENTA else ""
        context["reporte_agrupado_label"] = VISTA_LABELS.get(modo, "")
        context["reporte_resumen_filtros"] = self.resumen_filtros()
        context["reporte_totales"] = self.totales_formateados()
        context["record_noun"] = "cuenta" if modo == VISTA_CUENTA else self.record_noun
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
        totales = self.totales_formateados()
        return {
            "reporte_resumen_filtros": self.resumen_filtros(),
            "reporte_agrupado_label": VISTA_LABELS.get(self.vista(), ""),
            "reporte_totales": totales,
            "footer_label": "Total",
            "footer_debe": totales["debe"],
            "footer_haber": totales["haber"],
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
        resumen = self.vista() == VISTA_CUENTA
        row = []
        for column in columns:
            name = column.name
            if name == "debe":
                row.append(totales["debe"])
            elif name == "haber":
                row.append(totales["haber"])
            elif name == "saldo_anterior" and resumen:
                row.append(totales["saldo_anterior"])
            elif name == "saldo":
                row.append(totales["saldo"])
            elif name == "cuenta":
                row.append("Total")
            else:
                row.append("")
        if not any(cell == "Total" for cell in row):
            row[0] = "Total"
        return row

    def _celda_export(self, column, record):
        value = column.accessor.resolve(record)
        if value is None:
            return ""
        name = column.name
        if name in ("debe", "haber", "saldo", "saldo_anterior"):
            return mostrar_guaranies(value)
        if name == "fecha" and hasattr(value, "strftime"):
            return value.strftime("%d/%m/%Y")
        return value

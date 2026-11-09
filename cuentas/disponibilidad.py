from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from django.db.models import DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce

from compras.models import Compra, EstadoCompra, EstadoPagoProveedor, PagoProveedor, TipoCompra
from core.listado import filter_specs_for, filter_values
from core.mantenimiento import MantenimientoListView
from core.moneda import html_guaranies, mostrar_guaranies
from cuentas.models import Cuenta, EstadoTransferencia, Transferencia
from cuentas.tables import DisponibilidadDetalleTable, DisponibilidadResumenTable
from ventas.models import EstadoVenta, Venta

CERO = Decimal("0")
VISTA_DETALLE = "detalle"
VISTA_CUENTA = "cuenta"
ORIGEN_VENTA = "Venta"
ORIGEN_COMPRA = "Compra"
ORIGEN_EGRESO = "Egreso"
ORIGEN_TRANSFERENCIA = "Transferencia"
ORIGEN_PAGO_PROVEEDOR = "Pago proveedor"

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
    entra: Decimal | None
    salida: Decimal | None
    saldo: Decimal
    es_saldo_anterior: bool = False
    origen_id: int | None = None


@dataclass
class FilaResumenDisponibilidad:
    pk: int
    cuenta: str
    saldo_anterior: Decimal
    entra: Decimal
    salida: Decimal
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


def _comprobante_transferencia(transferencia):
    texto = (transferencia.comprobante or "").strip()
    return texto or f"Transferencia {transferencia.pk}"


def movimientos_caja(cuenta_id=None):
    """Ventas cobradas, compras al contado o egresos y transferencias entre cuentas."""
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
    transferencias = Transferencia.objects.filter(
        estado=EstadoTransferencia.CONFIRMADA
    ).select_related("cuenta_origen", "cuenta_destino")
    pagos_proveedor = PagoProveedor.objects.filter(
        estado=EstadoPagoProveedor.CONFIRMADO
    ).select_related("cuenta", "proveedor")
    if cuenta_id:
        ventas = ventas.filter(cuenta_cobro_id=cuenta_id)
        compras = compras.filter(cuenta_id=cuenta_id)
        transferencias = transferencias.filter(
            Q(cuenta_origen_id=cuenta_id) | Q(cuenta_destino_id=cuenta_id)
        )
        pagos_proveedor = pagos_proveedor.filter(cuenta_id=cuenta_id)

    filas = []
    for venta in ventas:
        filas.append(
            {
                "cuenta_id": venta.cuenta_cobro_id,
                "cuenta": venta.cuenta_cobro.descripcion,
                "fecha": venta.fecha,
                "comprobante": venta.numero_completo or "—",
                "origen": ORIGEN_VENTA,
                "entra": venta.importe or CERO,
                "salida": CERO,
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
                "entra": CERO,
                "salida": compra.importe or CERO,
                "orden": 1,
                "origen_id": compra.pk,
                "clave": f"c-{compra.pk}",
            }
        )
    for pago in pagos_proveedor:
        proveedor = str(pago.proveedor) if pago.proveedor_id else "—"
        filas.append(
            {
                "cuenta_id": pago.cuenta_id,
                "cuenta": pago.cuenta.descripcion,
                "fecha": pago.fecha,
                "comprobante": f"Pago {pago.pk} · {proveedor}",
                "origen": ORIGEN_PAGO_PROVEEDOR,
                "entra": CERO,
                "salida": pago.importe or CERO,
                "orden": 1,
                "origen_id": pago.pk,
                "clave": f"p-{pago.pk}",
            }
        )
    for transferencia in transferencias:
        comprobante = _comprobante_transferencia(transferencia)
        if not cuenta_id or transferencia.cuenta_origen_id == cuenta_id:
            filas.append(
                {
                    "cuenta_id": transferencia.cuenta_origen_id,
                    "cuenta": transferencia.cuenta_origen.descripcion,
                    "fecha": transferencia.fecha,
                    "comprobante": comprobante,
                    "origen": ORIGEN_TRANSFERENCIA,
                    "entra": CERO,
                    "salida": transferencia.importe or CERO,
                    "orden": 2,
                    "origen_id": transferencia.pk,
                    "clave": f"t-{transferencia.pk}-s",
                }
            )
        if not cuenta_id or transferencia.cuenta_destino_id == cuenta_id:
            filas.append(
                {
                    "cuenta_id": transferencia.cuenta_destino_id,
                    "cuenta": transferencia.cuenta_destino.descripcion,
                    "fecha": transferencia.fecha,
                    "comprobante": comprobante,
                    "origen": ORIGEN_TRANSFERENCIA,
                    "entra": transferencia.importe or CERO,
                    "salida": CERO,
                    "orden": 3,
                    "origen_id": transferencia.pk,
                    "clave": f"t-{transferencia.pk}-e",
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
    total_entra = CERO
    total_salida = CERO
    total_anterior = CERO
    for cuenta_id_grupo, items in sorted(por_cuenta.items(), key=lambda par: par[1][0]["cuenta"]):
        saldo_anterior = CERO
        entra_anterior = CERO
        salida_anterior = CERO
        hubo_anterior = False
        periodo = []
        for movimiento in items:
            fecha = movimiento["fecha"]
            if desde and fecha < desde:
                hubo_anterior = True
                entra_anterior += movimiento["entra"]
                salida_anterior += movimiento["salida"]
                saldo_anterior += movimiento["entra"] - movimiento["salida"]
                continue
            if hasta and fecha > hasta:
                continue
            periodo.append(movimiento)
        if not periodo and not hubo_anterior:
            continue
        cuenta_nombre = items[0]["cuenta"]
        entra_periodo = sum((fila["entra"] for fila in periodo), CERO)
        salida_periodo = sum((fila["salida"] for fila in periodo), CERO)
        total_entra += entra_periodo
        total_salida += salida_periodo
        total_anterior += saldo_anterior
        resumen.append(
            FilaResumenDisponibilidad(
                pk=cuenta_id_grupo,
                cuenta=cuenta_nombre,
                saldo_anterior=saldo_anterior,
                entra=entra_periodo,
                salida=salida_periodo,
                saldo=saldo_anterior + entra_periodo - salida_periodo,
            )
        )
        saldo = saldo_anterior
        if hubo_anterior:
            detalle.append(
                FilaDisponibilidad(
                    pk=f"a-{cuenta_id_grupo}",
                    cuenta_id=cuenta_id_grupo,
                    cuenta=cuenta_nombre,
                    fecha=None,
                    comprobante="Saldo anterior",
                    origen="",
                    entra=entra_anterior,
                    salida=salida_anterior,
                    saldo=entra_anterior - salida_anterior,
                    es_saldo_anterior=True,
                    origen_id=None,
                )
            )
        for movimiento in periodo:
            saldo = saldo + movimiento["entra"] - movimiento["salida"]
            detalle.append(
                FilaDisponibilidad(
                    pk=movimiento["clave"],
                    cuenta_id=cuenta_id_grupo,
                    cuenta=cuenta_nombre,
                    fecha=movimiento["fecha"],
                    comprobante=movimiento["comprobante"],
                    origen=movimiento["origen"],
                    entra=movimiento["entra"] if movimiento["entra"] else None,
                    salida=movimiento["salida"] if movimiento["salida"] else None,
                    saldo=saldo,
                    origen_id=movimiento["origen_id"],
                )
            )
    totales = {
        "entra": total_entra,
        "salida": total_salida,
        "saldo_anterior": total_anterior,
        "saldo": total_anterior + total_entra - total_salida,
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
        "Por defecto muestra el mes en curso hasta hoy. "
        "El saldo de cada fila es el saldo anterior más la entra menos la salida. "
        "Los movimientos de antes de esa fecha se agrupan en Saldo anterior."
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
            "required": True,
            "default": "month_start",
        },
        {
            "name": "fecha_hasta",
            "label": "Hasta",
            "kind": "date",
            "required": True,
            "default": "today",
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

    def _fechas(self):
        valores = filter_values(self.request, filter_specs_for(self))
        return _parse_fecha(valores.get("fecha_desde")), _parse_fecha(valores.get("fecha_hasta"))

    def fechas_listas(self):
        desde, hasta = self._fechas()
        return desde is not None and hasta is not None and desde <= hasta

    def _resultado(self):
        if hasattr(self, "_resultado_cache"):
            return self._resultado_cache
        if not self.fechas_listas():
            self._resultado_cache = ([], [], {
                "entra": CERO,
                "salida": CERO,
                "saldo_anterior": CERO,
                "saldo": CERO,
            })
            return self._resultado_cache
        valores = filter_values(self.request, filter_specs_for(self))
        cuenta = valores.get("cuenta")
        desde, hasta = self._fechas()
        self._resultado_cache = mayor_disponibilidad(
            cuenta_id=int(cuenta) if cuenta and cuenta.isdigit() else None,
            fecha_desde=desde,
            fecha_hasta=hasta,
            query=self.query(),
        )
        return self._resultado_cache

    def get_queryset(self):
        if not self.fechas_listas():
            return []
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
            "entra": mostrar_guaranies(totales["entra"]),
            "salida": mostrar_guaranies(totales["salida"]),
            "saldo_anterior": mostrar_guaranies(totales["saldo_anterior"]),
            "saldo": mostrar_guaranies(totales["saldo"]),
            "entra_html": html_guaranies(totales["entra"]),
            "salida_html": html_guaranies(totales["salida"]),
            "saldo_anterior_html": html_guaranies(totales["saldo_anterior"]),
            "saldo_html": html_guaranies(totales["saldo"]),
            "entra_raw": totales["entra"],
            "salida_raw": totales["salida"],
            "saldo_anterior_raw": totales["saldo_anterior"],
            "saldo_raw": totales["saldo"],
        }

    def get_table(self, **kwargs):
        table = super().get_table(**kwargs)
        desde, hasta = self._fechas()
        if desde is None or hasta is None:
            table.empty_text = "Elegí las fechas desde y hasta para ver la disponibilidad."
            table.reporte_totales = None
        elif desde > hasta:
            table.empty_text = "La fecha desde no puede ser posterior a la fecha hasta."
            table.reporte_totales = None
        else:
            table.reporte_totales = self.totales_formateados()
        table.modo_resumen = self.vista() == VISTA_CUENTA
        return table

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        modo = self.vista()
        desde, hasta = self._fechas()
        context["reporte_agrupado"] = modo if modo == VISTA_CUENTA else ""
        context["reporte_agrupado_label"] = VISTA_LABELS.get(modo, "")
        context["reporte_resumen_filtros"] = self.resumen_filtros()
        context["reporte_totales"] = self.totales_formateados() if self.fechas_listas() else None
        context["record_noun"] = "cuenta" if modo == VISTA_CUENTA else self.record_noun
        if desde is None or hasta is None or desde > hasta:
            context["filters_open"] = True
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
            "footer_entra": totales["entra"],
            "footer_salida": totales["salida"],
        }

    def _salida_context(self):
        context = super()._salida_context()
        if self.export_totals and self.fechas_listas() and context["rows"]:
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
        if self.export_totals and self.fechas_listas():
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
            if name == "entra":
                row.append(totales["entra"])
            elif name == "salida":
                row.append(totales["salida"])
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
        if name in ("entra", "salida", "saldo", "saldo_anterior"):
            return mostrar_guaranies(value)
        if name == "fecha" and hasattr(value, "strftime"):
            return value.strftime("%d/%m/%Y")
        return value

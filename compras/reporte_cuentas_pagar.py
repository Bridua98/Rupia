from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.utils import timezone

from compras.models import CompraCuota, EstadoCompra, TipoCompra
from compras.tables import ReporteCuentasPagarTable
from core.listado import apply_filters, apply_search, filter_specs_for, filter_values, search_fields_for
from core.mantenimiento import MantenimientoListView
from core.moneda import html_guaranies, mostrar_guaranies
from inventario.precios import redondear_guarani
from personas.models import Persona

CERO = Decimal("0")

ESTADO_PENDIENTE = "pendiente"
ESTADO_VENCIDA = "vencida"
ESTADO_PARCIAL = "parcial"
ESTADO_CANCELADA = "cancelada"

ESTADO_CHOICES = (
    (ESTADO_PENDIENTE, "Pendiente"),
    (ESTADO_VENCIDA, "Vencida"),
    (ESTADO_PARCIAL, "Parcial"),
    (ESTADO_CANCELADA, "Cancelada"),
)

ESTADO_LABELS = dict(ESTADO_CHOICES)


@dataclass
class FilaCuentaPagar:
    pk: int
    compra_id: int
    proveedor: str
    comprobante: str
    numero: int
    vencimiento: date
    importe: Decimal
    pagado: Decimal
    saldo: Decimal
    estado: str
    estado_clave: str


def _estado_cuota(vencimiento: date, pagado: Decimal, saldo: Decimal, hoy: date):
    if saldo <= 0:
        return ESTADO_CANCELADA, "Cancelada"
    if pagado > 0:
        return ESTADO_PARCIAL, "Parcial"
    if vencimiento < hoy:
        return ESTADO_VENCIDA, "Vencida"
    return ESTADO_PENDIENTE, "Pendiente"


class ReporteCuentasPagarListView(MantenimientoListView):
    template_name = "compras/reporte_cuentas_pagar_list.html"
    model = CompraCuota
    table_class = ReporteCuentasPagarTable
    permiso_formulario = "reporte_cuentas_pagar"
    page_title = "Cuentas a pagar"
    eyebrow = "Gestión"
    title = "Cuentas a pagar"
    create_label = ""
    show_create = False
    list_hint = "Cuotas de facturas a crédito confirmadas, con pagos aplicados."
    search_label = "Buscar"
    search_placeholder = "Buscar por proveedor o número de factura..."
    search_fields = (
        "compra__numero_completo",
        "compra__proveedor__razon_social",
        "compra__proveedor__documento",
    )
    filters = (
        {
            "name": "compra__proveedor",
            "label": "Proveedor",
            "kind": "fk",
            "queryset": lambda: Persona.objects.filter(es_proveedor=True).order_by("razon_social"),
        },
        {
            "name": "vencimiento_desde",
            "label": "Vence desde",
            "kind": "date",
            "field": "vencimiento",
            "lookup": "gte",
        },
        {
            "name": "vencimiento_hasta",
            "label": "Vence hasta",
            "kind": "date",
            "field": "vencimiento",
            "lookup": "lte",
        },
        {
            "name": "situacion",
            "label": "Estado",
            "kind": "skip",
            "choices": ESTADO_CHOICES,
        },
    )
    record_noun = "cuota"
    order_by = ("vencimiento", "compra_id", "numero")
    list_url_name = "reporte_cuentas_pagar"
    per_page = 15
    back_url_name = "home"
    print_url_name = "reporte_cuentas_pagar_print"
    export_xlsx_url_name = "reporte_cuentas_pagar_export_xlsx"
    export_pdf_url_name = "reporte_cuentas_pagar_export_pdf"
    export_basename = "cuentas-a-pagar"
    export_totals = True
    selection_param = "reporte_sel"

    def situacion(self):
        return filter_values(self.request, filter_specs_for(self)).get("situacion", "")

    def cuotas_queryset(self):
        queryset = (
            CompraCuota.objects.filter(
                compra__estado=EstadoCompra.CONFIRMADA,
                compra__tipo=TipoCompra.FACTURA_CREDITO,
            )
            .select_related("compra", "compra__proveedor")
            .order_by(*self.order_by)
        )
        queryset = apply_search(queryset, self.query(), search_fields_for(self))
        specs = [s for s in filter_specs_for(self) if s.get("kind") != "skip"]
        return apply_filters(queryset, filter_values(self.request, specs), specs)

    def _armar_filas(self):
        if not hasattr(self, "_detalle_cache"):
            hoy = timezone.localdate()
            situacion = self.situacion()
            filas = []
            for cuota in self.cuotas_queryset():
                pagado = cuota.importe_pagado()
                saldo = cuota.saldo_pendiente()
                clave, etiqueta = _estado_cuota(cuota.vencimiento, pagado, saldo, hoy)
                if situacion and clave != situacion:
                    continue
                compra = cuota.compra
                filas.append(
                    FilaCuentaPagar(
                        pk=cuota.pk,
                        compra_id=compra.pk,
                        proveedor=(
                            compra.proveedor.razon_social if compra.proveedor_id else "—"
                        ),
                        comprobante=compra.numero_completo or f"Compra {compra.pk}",
                        numero=cuota.numero,
                        vencimiento=cuota.vencimiento,
                        importe=cuota.importe,
                        pagado=pagado,
                        saldo=saldo,
                        estado=etiqueta,
                        estado_clave=clave,
                    )
                )
            self._detalle_cache = filas
        return self._detalle_cache

    def get_queryset(self):
        return self._armar_filas()

    def creating(self):
        return False

    def panel_pk(self):
        return None

    def totales_raw(self):
        filas = self._armar_filas()
        return {
            "importe": sum((fila.importe for fila in filas), CERO),
            "pagado": sum((fila.pagado for fila in filas), CERO),
            "saldo": sum((fila.saldo for fila in filas), CERO),
        }

    def totales_formateados(self):
        datos = self.totales_raw()
        return {
            "importe": mostrar_guaranies(datos["importe"]),
            "pagado": mostrar_guaranies(datos["pagado"]),
            "saldo": mostrar_guaranies(datos["saldo"]),
            "importe_html": html_guaranies(datos["importe"]),
            "pagado_html": html_guaranies(datos["pagado"]),
            "saldo_html": html_guaranies(datos["saldo"]),
        }

    def get_table(self, **kwargs):
        table = super().get_table(**kwargs)
        table.reporte_totales = self.totales_formateados()
        return table

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        situacion = self.situacion()
        if situacion:
            context["reporte_agrupado_label"] = f"Estado: {ESTADO_LABELS.get(situacion, situacion)}"
        context["reporte_resumen_filtros"] = self.resumen_filtros()
        context["reporte_totales"] = self.totales_formateados()
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
            "reporte_totales": self.totales_formateados(),
        }

    def export_totals_row(self, columns):
        totales = self.totales_formateados()
        row = []
        for column in columns:
            name = column.name
            if name in ("importe", "pagado", "saldo"):
                row.append(totales[name])
            elif name == "proveedor":
                row.append("Total")
            else:
                row.append("")
        if row and row[0] != "Total":
            row[0] = "Total"
        return row

    def _celda_export(self, column, record):
        value = column.accessor.resolve(record)
        if value is None or value == "":
            return ""
        name = column.name
        if name in ("importe", "pagado", "saldo"):
            return mostrar_guaranies(value)
        if name == "vencimiento" and hasattr(value, "strftime"):
            return value.strftime("%d/%m/%Y")
        return value

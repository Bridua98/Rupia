from dataclasses import dataclass
from decimal import Decimal

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
        },
        {
            "name": "fecha_hasta",
            "label": "Hasta",
            "kind": "date",
            "field": "compra__fecha",
            "lookup": "lte",
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

    def detalles_queryset(self):
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
        return apply_filters(queryset, filter_values(self.request, specs), specs)

    def _detalle(self):
        if not hasattr(self, "_detalle_cache"):
            self._detalle_cache = self._armar_detalle()
        return self._detalle_cache

    def _armar_detalle(self):
        filas = []
        for detalle in self.detalles_queryset():
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
        filas = self._detalle()
        return {
            "gravado": sum((fila.gravado for fila in filas), CERO),
            "iva": sum((fila.iva for fila in filas), CERO),
            "subtotal": sum((fila.subtotal for fila in filas), CERO),
        }

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

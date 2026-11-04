from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Count, Sum

from core.cantidad import formatear_cantidad
from core.listado import (
    apply_filters,
    apply_search,
    filter_specs_for,
    filter_values,
    search_fields_for,
)
from core.mantenimiento import MantenimientoListView
from core.moneda import formatear_guaranies
from inventario.models import Item, ItemCategoria, ItemMovimiento, Marca, TipoItem, TipoMovimiento
from inventario.tables import ReporteProductosAgrupadoTable, ReporteProductosDetalleTable

AGRUPAR_DETALLE = ""
AGRUPAR_ITEM = "item"
AGRUPAR_CATEGORIA = "categoria"
AGRUPAR_MARCA = "marca"

AGRUPAR_CHOICES = (
    (AGRUPAR_DETALLE, "Sin agrupar (cada movimiento)"),
    (AGRUPAR_ITEM, "Por ítem"),
    (AGRUPAR_CATEGORIA, "Por categoría"),
    (AGRUPAR_MARCA, "Por marca"),
)

AGRUPAR_LABELS = {
    AGRUPAR_ITEM: "Por ítem",
    AGRUPAR_CATEGORIA: "Por categoría",
    AGRUPAR_MARCA: "Por marca",
}


@dataclass
class FilaReporteAgrupada:
    pk: int
    etiqueta: str
    detalle: str
    movimientos: int
    cantidad: Decimal
    subtotal: Decimal


def _specs_movimiento(view):
    return [spec for spec in filter_specs_for(view) if spec.get("kind") != "skip"]


class ReporteProductosListView(MantenimientoListView):
    template_name = "inventario/reporte_productos_list.html"
    model = ItemMovimiento
    permiso_formulario = "reporte_productos"
    page_title = "Reporte de productos"
    eyebrow = "Inventario"
    title = "Reporte de productos"
    create_label = ""
    show_create = False
    list_hint = (
        "Movimientos vigentes de productos. Filtrá, agrupá en una fila e imprimí o exportá."
    )
    search_label = "Buscar"
    search_placeholder = "Buscar por ítem, marca o categoría..."
    search_fields = (
        "item__descripcion",
        "item__codigo_barra",
        "item__marca__descripcion",
        "item__categoria__descripcion",
    )
    filters = (
        {
            "name": "item",
            "label": "Ítem",
            "kind": "fk",
            "queryset": lambda: Item.objects.filter(tipo=TipoItem.PRODUCTO, activo=True).order_by(
                "descripcion"
            ),
        },
        {
            "name": "item__categoria",
            "label": "Categoría",
            "kind": "fk",
            "queryset": lambda: ItemCategoria.objects.order_by("descripcion"),
        },
        {
            "name": "item__marca",
            "label": "Marca",
            "kind": "fk",
            "queryset": lambda: Marca.objects.order_by("descripcion"),
        },
        {
            "name": "tipo",
            "label": "Tipo de movimiento",
            "kind": "choice",
            "choices": TipoMovimiento.choices,
        },
        {
            "name": "fecha_desde",
            "label": "Desde",
            "kind": "date",
            "field": "fecha_movimiento",
            "lookup": "gte",
        },
        {
            "name": "fecha_hasta",
            "label": "Hasta",
            "kind": "date",
            "field": "fecha_movimiento",
            "lookup": "lte",
        },
        {
            "name": "agrupar",
            "label": "Agrupar por",
            "kind": "skip",
            "choices": AGRUPAR_CHOICES,
        },
    )
    record_noun = "movimiento"
    order_by = ("-fecha_movimiento", "-id")
    list_url_name = "reporte_productos"
    per_page = 15
    back_url_name = "home"
    print_url_name = "reporte_productos_print"
    export_xlsx_url_name = "reporte_productos_export_xlsx"
    export_pdf_url_name = "reporte_productos_export_pdf"
    export_basename = "reporte-productos"
    export_totals = True
    selection_param = "reporte_sel"

    def agrupar(self):
        return filter_values(self.request, filter_specs_for(self)).get("agrupar", AGRUPAR_DETALLE)

    def movimientos_queryset(self):
        specs = _specs_movimiento(self)
        queryset = (
            ItemMovimiento.objects.filter(es_vigente=True, item__tipo=TipoItem.PRODUCTO)
            .select_related(
                "item",
                "item__marca",
                "item__categoria",
                "unidad_medida",
            )
            .order_by()
        )
        queryset = apply_search(queryset, self.query(), search_fields_for(self))
        queryset = apply_filters(queryset, filter_values(self.request, specs), specs)
        return queryset

    def totales_raw(self):
        return self.movimientos_queryset().aggregate(
            cantidad=Sum("cantidad"),
            subtotal=Sum("subtotal"),
        )

    def totales_formateados(self):
        datos = self.totales_raw()
        cantidad = datos.get("cantidad") or Decimal("0")
        subtotal = datos.get("subtotal") or Decimal("0")
        return {
            "cantidad": formatear_cantidad(cantidad),
            "subtotal": formatear_guaranies(subtotal),
            "cantidad_raw": cantidad,
            "subtotal_raw": subtotal,
        }

    def _filas_agrupadas(self, queryset, modo):
        if modo == AGRUPAR_ITEM:
            filas = (
                queryset.values(
                    "item_id",
                    "item__descripcion",
                    "item__marca__descripcion",
                    "item__categoria__descripcion",
                )
                .annotate(
                    cantidad=Sum("cantidad"),
                    subtotal=Sum("subtotal"),
                    movimientos=Count("id"),
                )
                .order_by("item__descripcion")
            )
            return [
                FilaReporteAgrupada(
                    pk=row["item_id"],
                    etiqueta=row["item__descripcion"],
                    detalle=(
                        f"{row['item__marca__descripcion']} · "
                        f"{row['item__categoria__descripcion']}"
                    ),
                    movimientos=row["movimientos"],
                    cantidad=row["cantidad"],
                    subtotal=row["subtotal"],
                )
                for row in filas
            ]
        if modo == AGRUPAR_CATEGORIA:
            filas = (
                queryset.values("item__categoria_id", "item__categoria__descripcion")
                .annotate(
                    cantidad=Sum("cantidad"),
                    subtotal=Sum("subtotal"),
                    movimientos=Count("id"),
                )
                .order_by("item__categoria__descripcion")
            )
            return [
                FilaReporteAgrupada(
                    pk=row["item__categoria_id"],
                    etiqueta=row["item__categoria__descripcion"],
                    detalle="",
                    movimientos=row["movimientos"],
                    cantidad=row["cantidad"],
                    subtotal=row["subtotal"],
                )
                for row in filas
            ]
        if modo == AGRUPAR_MARCA:
            filas = (
                queryset.values("item__marca_id", "item__marca__descripcion")
                .annotate(
                    cantidad=Sum("cantidad"),
                    subtotal=Sum("subtotal"),
                    movimientos=Count("id"),
                )
                .order_by("item__marca__descripcion")
            )
            return [
                FilaReporteAgrupada(
                    pk=row["item__marca_id"],
                    etiqueta=row["item__marca__descripcion"],
                    detalle="",
                    movimientos=row["movimientos"],
                    cantidad=row["cantidad"],
                    subtotal=row["subtotal"],
                )
                for row in filas
            ]
        return []

    def get_queryset(self):
        queryset = self.movimientos_queryset()
        modo = self.agrupar()
        if modo and modo != AGRUPAR_DETALLE:
            return self._filas_agrupadas(queryset, modo)
        return queryset.order_by(*self.order_by)

    @property
    def table_class(self):
        modo = self.agrupar()
        if modo and modo != AGRUPAR_DETALLE:
            return ReporteProductosAgrupadoTable
        return ReporteProductosDetalleTable

    def creating(self):
        return False

    def panel_pk(self):
        return None

    def get_table_kwargs(self):
        return {}

    def get_table(self, **kwargs):
        table = super().get_table(**kwargs)
        table.reporte_totales = self.totales_formateados()
        table.modo_agrupado = bool(self.agrupar() and self.agrupar() != AGRUPAR_DETALLE)
        return table

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        modo = self.agrupar()
        context["reporte_agrupado"] = modo if modo and modo != AGRUPAR_DETALLE else ""
        context["reporte_agrupado_label"] = AGRUPAR_LABELS.get(modo, "")
        context["reporte_resumen_filtros"] = self.resumen_filtros()
        context["reporte_totales"] = self.totales_formateados()
        context["record_noun"] = "fila" if context["reporte_agrupado"] else self.record_noun
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
            "reporte_agrupado_label": AGRUPAR_LABELS.get(self.agrupar(), ""),
            "reporte_totales": totales,
            "footer_label": "Total",
            "footer_cantidad": totales["cantidad"],
            "footer_subtotal": totales["subtotal"],
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
        empty = queryset.none() if hasattr(queryset, "none") else []
        table = table_class(empty)
        columns = [column for column in table.columns if not _skip_export(column)]
        headers = [str(column.header) for column in columns]
        rows = []
        for record in queryset:
            row = []
            for column in columns:
                value = column.accessor.resolve(record)
                row.append("" if value is None else value)
            rows.append(row)
        if self.export_totals:
            total_row = self.export_totals_row(columns)
            if total_row is not None:
                rows.append(total_row)
        return headers, rows

    def export_totals_row(self, columns):
        totales = self.totales_formateados()
        modo = self.agrupar()
        agrupado = modo and modo != AGRUPAR_DETALLE
        row = []
        for column in columns:
            name = column.name
            if name in ("cantidad",):
                row.append(totales["cantidad"])
            elif name in ("subtotal",):
                row.append(totales["subtotal"])
            elif name == "etiqueta" and agrupado:
                row.append("Total")
            elif name == "fecha_movimiento" and not agrupado:
                row.append("Total")
            else:
                row.append("")
        if not any(cell == "Total" for cell in row):
            row[0] = "Total"
        return row

from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Prefetch

from core.listado import (
    apply_filters,
    apply_search,
    filter_specs_for,
    filter_values,
    search_fields_for,
)
from core.mantenimiento import MantenimientoListView
from inventario.models import (
    Item,
    ItemCategoria,
    ItemMovimiento,
    Marca,
    TasaIva,
    TipoItem,
    TipoMovimiento,
    UnidadMedida,
)
from inventario.tables import ReporteStockTable
from inventario.unidades import convertir_a_base, redondear_cantidad
from negocio.models import UnidadNegocio

TIPOS_SALIDA = frozenset({TipoMovimiento.VENTA, TipoMovimiento.AJUSTE_NEGATIVO})


@dataclass
class FilaReporteStock:
    pk: int
    descripcion: str
    marca: str
    categoria: str
    unidad: str
    stock: Decimal
    aviso: str = ""


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


class ReporteStockListView(MantenimientoListView):
    template_name = "inventario/reporte_productos_list.html"
    model = Item
    table_class = ReporteStockTable
    page_title = "Stock"
    eyebrow = "Inventario"
    title = "Stock"
    create_label = ""
    show_create = False
    list_hint = (
        "Existencia por producto en su unidad de medida base, según movimientos vigentes."
    )
    search_label = "Buscar"
    search_placeholder = "Buscar por descripción, código, marca o categoría..."
    search_fields = (
        "descripcion",
        "codigo_barra",
        "marca__descripcion",
        "categoria__descripcion",
    )
    filters = (
        {
            "name": "marca",
            "label": "Marca",
            "kind": "fk",
            "queryset": lambda: Marca.objects.order_by("descripcion"),
        },
        {
            "name": "categoria",
            "label": "Categoría",
            "kind": "fk",
            "queryset": lambda: ItemCategoria.objects.order_by("descripcion"),
        },
        {
            "name": "unidad_medida",
            "label": "Unidad",
            "kind": "fk",
            "queryset": lambda: UnidadMedida.objects.order_by("descripcion"),
        },
        {
            "name": "unidad_negocio",
            "label": "Unidad de negocio",
            "kind": "fk",
            "queryset": lambda: UnidadNegocio.objects.order_by("descripcion"),
        },
        {
            "name": "tasa_iva",
            "label": "Tasa IVA",
            "kind": "choice",
            "choices": [(str(valor), etiqueta) for valor, etiqueta in TasaIva.choices],
        },
        {"name": "activo", "label": "Activo", "kind": "bool"},
    )
    record_noun = "producto"
    order_by = ("descripcion", "pk")
    list_url_name = "reporte_stock"
    per_page = 15
    back_url_name = "home"
    print_url_name = "reporte_stock_print"
    export_xlsx_url_name = "reporte_stock_export_xlsx"
    export_pdf_url_name = "reporte_stock_export_pdf"
    export_basename = "stock"
    export_totals = False
    selection_param = "stock_sel"

    def productos_queryset(self):
        movimientos_vigentes = ItemMovimiento.objects.filter(es_vigente=True).select_related(
            "unidad_medida"
        )
        queryset = (
            Item.objects.filter(tipo=TipoItem.PRODUCTO)
            .select_related("marca", "categoria", "unidad_medida")
            .prefetch_related(
                Prefetch("movimientos", queryset=movimientos_vigentes),
                "unidades",
            )
            .order_by()
        )
        queryset = apply_search(queryset, self.query(), search_fields_for(self))
        queryset = apply_filters(
            queryset, filter_values(self.request, filter_specs_for(self)), filter_specs_for(self)
        )
        return queryset.order_by(*self.order_by)

    def get_queryset(self):
        filas = []
        for item in self.productos_queryset():
            stock, omitidos = stock_desde_movimientos(item, item.movimientos.all())
            aviso = ""
            if omitidos:
                aviso = "Hay movimientos con unidad no relacionada; no entraron en el stock."
            filas.append(
                FilaReporteStock(
                    pk=item.pk,
                    descripcion=item.descripcion,
                    marca=item.marca.descripcion,
                    categoria=item.categoria.descripcion,
                    unidad=item.unidad_medida.simbolo,
                    stock=stock,
                    aviso=aviso,
                )
            )
        return filas

    def creating(self):
        return False

    def panel_pk(self):
        return None

    def get_table_kwargs(self):
        return {}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["reporte_agrupado"] = ""
        context["reporte_agrupado_label"] = ""
        context["reporte_resumen_filtros"] = self.resumen_filtros()
        context.pop("reporte_totales", None)
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
            elif kind == "choice":
                for val, texto in spec.get("choices", ()):
                    if val == value:
                        partes.append(f"{label}: {texto}")
                        break
            elif kind == "bool":
                partes.append(f"{label}: {'Sí' if value == '1' else 'No'}")
        query = self.query()
        if query:
            partes.insert(0, f"Búsqueda: {query}")
        return partes

    def salida_extra_context(self):
        return {"reporte_resumen_filtros": self.resumen_filtros()}

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
                value = column.accessor.resolve(record)
                row.append("" if value is None else value)
            rows.append(row)
        return headers, rows

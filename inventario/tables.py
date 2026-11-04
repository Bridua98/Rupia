import django_tables2 as tables
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from core.cantidad import formatear_cantidad
from core.moneda import formatear_guaranies
from core.tables import ActionMenuColumn
from core.vista import html_bool
from inventario.models import (
    AjusteStock,
    Item,
    ItemCategoria,
    ItemMovimiento,
    ItemPrecioHistorial,
    Marca,
    UnidadMedida,
)


class MarcaTable(tables.Table):
    descripcion = tables.Column(verbose_name="Descripción")
    acciones = ActionMenuColumn()

    class Meta:
        model = Marca
        fields = ("descripcion", "acciones")
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay marcas."
        attrs = {"class": "sheet"}


class CategoriaTable(tables.Table):
    descripcion = tables.Column(verbose_name="Descripción")
    acciones = ActionMenuColumn()

    class Meta:
        model = ItemCategoria
        fields = ("descripcion", "acciones")
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay categorías."
        attrs = {"class": "sheet"}


class UnidadTable(tables.Table):
    descripcion = tables.Column(verbose_name="Descripción")
    simbolo = tables.Column(verbose_name="Símbolo")
    acciones = ActionMenuColumn()

    class Meta:
        model = UnidadMedida
        fields = ("descripcion", "simbolo", "acciones")
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay unidades."
        attrs = {"class": "sheet"}


class ItemTable(tables.Table):
    descripcion = tables.Column(verbose_name="Descripción")
    tipo = tables.Column(verbose_name="Tipo", accessor="get_tipo_display")
    unidad_negocio = tables.Column(
        verbose_name="Negocio",
        accessor="unidad_negocio__abreviado",
    )
    marca = tables.Column(verbose_name="Marca")
    categoria = tables.Column(verbose_name="Categoría")
    unidad_medida = tables.Column(verbose_name="Unidad", accessor="unidad_medida__simbolo")
    tasa_iva = tables.Column(verbose_name="Tasa IVA", accessor="get_tasa_iva_display")
    acciones = ActionMenuColumn()

    class Meta:
        model = Item
        fields = (
            "descripcion",
            "tipo",
            "unidad_negocio",
            "marca",
            "categoria",
            "unidad_medida",
            "tasa_iva",
            "acciones",
        )
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay ítems."
        attrs = {"class": "sheet"}

    def render_unidad_negocio(self, value):
        return value or "—"


def texto_moneda(valor):
    if valor is None:
        return "—"
    return formatear_guaranies(valor)


class PrecioTable(tables.Table):
    seleccionar = tables.Column(
        verbose_name=mark_safe(
            '<input type="checkbox" data-precios-todos-pagina aria-label="Seleccionar la página">'
        ),
        empty_values=(),
        orderable=False,
        attrs={"th": {"class": "sheet-col-check"}, "td": {"class": "sheet-col-check"}},
    )
    descripcion = tables.Column(verbose_name="Descripción")
    ultimo_costo = tables.Column(
        verbose_name="Último costo",
        attrs={"th": {"class": "sheet-col-moneda"}, "td": {"class": "sheet-col-moneda"}},
    )
    precio = tables.Column(
        verbose_name="Precio",
        attrs={"th": {"class": "sheet-col-moneda"}, "td": {"class": "sheet-col-moneda"}},
    )
    precio_segun_costo = tables.Column(verbose_name="Base")
    precio_nuevo = tables.Column(
        verbose_name="Precio nuevo",
        empty_values=(),
        accessor="pk",
        attrs={
            "th": {"class": "sheet-col-moneda"},
            "td": {"class": "sheet-col-moneda", "data-precios-nuevo": ""},
        },
    )

    class Meta:
        model = Item
        fields = (
            "seleccionar",
            "descripcion",
            "ultimo_costo",
            "precio",
            "precio_segun_costo",
            "precio_nuevo",
        )
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay ítems."
        attrs = {"class": "sheet"}

    def render_seleccionar(self, record):
        checked = " checked" if getattr(record, "seleccionado", False) else ""
        return mark_safe(f'<input type="checkbox" name="item" value="{record.pk}"{checked}>')

    def render_ultimo_costo(self, value):
        return texto_moneda(value)

    def render_precio(self, value):
        return texto_moneda(value)

    def render_precio_segun_costo(self, value):
        if value:
            return mark_safe('<span class="precios-base is-costo">Último costo</span>')
        return mark_safe('<span class="precios-base is-precio">Precio actual</span>')

    def render_precio_nuevo(self, record):
        calculado = getattr(record, "precio_preview", None)
        if calculado is None:
            return mark_safe('<span class="precios-nuevo is-vacio">—</span>')
        if calculado.omitido and calculado.precio_nuevo is None:
            return format_html(
                '<span class="precios-nuevo is-omitido">{}</span>',
                calculado.omitido,
            )
        extra = " is-igual"
        if not calculado.omitido and record.precio is not None:
            if calculado.precio_nuevo > record.precio:
                extra = " is-up"
            elif calculado.precio_nuevo < record.precio:
                extra = " is-down"
        elif not calculado.omitido:
            extra = " is-up"
        texto = texto_moneda(calculado.precio_nuevo)
        if calculado.omitido:
            return format_html(
                '<span class="precios-nuevo{}">{}</span> <span class="precios-omitido">{}</span>',
                extra,
                texto,
                calculado.omitido,
            )
        return format_html('<span class="precios-nuevo{}">{}</span>', extra, texto)


class PrecioHistorialTable(tables.Table):
    fecha = tables.Column(verbose_name="Fecha")
    usuario = tables.Column(verbose_name="Usuario", accessor="usuario__username")
    item = tables.Column(verbose_name="Ítem")
    precio_anterior = tables.Column(verbose_name="Anterior")
    precio_nuevo = tables.Column(verbose_name="Nuevo")
    porcentaje = tables.Column(verbose_name="%")
    segun_costo = tables.Column(verbose_name="Según costo")
    origen = tables.Column(verbose_name="Origen", accessor="get_origen_display")

    class Meta:
        model = ItemPrecioHistorial
        fields = (
            "fecha",
            "usuario",
            "item",
            "precio_anterior",
            "precio_nuevo",
            "porcentaje",
            "segun_costo",
            "origen",
        )
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay cambios de precio."
        attrs = {"class": "sheet"}

    def render_fecha(self, value):
        return timezone.localtime(value).strftime("%d/%m/%Y %H:%M")

    def render_precio_anterior(self, value):
        return texto_moneda(value)

    def render_precio_nuevo(self, value):
        return texto_moneda(value)

    def render_porcentaje(self, value):
        if value is None:
            return "—"
        if value == value.to_integral():
            return str(int(value))
        return format(value, "f").rstrip("0").replace(".", ",")

    def render_segun_costo(self, value):
        return html_bool(value)


class ReporteProductosDetalleTable(tables.Table):
    fecha_movimiento = tables.Column(verbose_name="Fecha")
    tipo = tables.Column(verbose_name="Tipo", accessor="get_tipo_display")
    item = tables.Column(verbose_name="Ítem", accessor="item__descripcion")
    categoria = tables.Column(verbose_name="Categoría", accessor="item__categoria__descripcion")
    marca = tables.Column(verbose_name="Marca", accessor="item__marca__descripcion")
    unidad = tables.Column(verbose_name="Unidad", accessor="unidad_medida__simbolo")
    cantidad = tables.Column(verbose_name="Cantidad")
    precio = tables.Column(verbose_name="Precio")
    costo = tables.Column(verbose_name="Costo")
    subtotal = tables.Column(verbose_name="Subtotal")

    class Meta:
        model = ItemMovimiento
        fields = (
            "fecha_movimiento",
            "tipo",
            "item",
            "categoria",
            "marca",
            "unidad",
            "cantidad",
            "precio",
            "costo",
            "subtotal",
        )
        orderable = False
        template_name = "django_tables2/rupia_totales.html"
        empty_text = "No hay movimientos para los filtros elegidos."
        attrs = {"class": "sheet"}

    def render_fecha_movimiento(self, value):
        return value.strftime("%d/%m/%Y")

    def render_cantidad(self, value):
        return formatear_cantidad(value)

    def render_precio(self, value):
        return texto_moneda(value)

    def render_costo(self, value):
        return texto_moneda(value)

    def render_subtotal(self, value):
        return texto_moneda(value)


class ReporteProductosAgrupadoTable(tables.Table):
    etiqueta = tables.Column(verbose_name="Nombre")
    detalle = tables.Column(verbose_name="Detalle")
    movimientos = tables.Column(verbose_name="Movimientos")
    cantidad = tables.Column(verbose_name="Cantidad total")
    subtotal = tables.Column(verbose_name="Subtotal")

    class Meta:
        orderable = False
        template_name = "django_tables2/rupia_totales.html"
        empty_text = "No hay movimientos para los filtros elegidos."
        attrs = {"class": "sheet"}

    def render_detalle(self, value):
        return value or "—"

    def render_cantidad(self, value):
        return formatear_cantidad(value)

    def render_subtotal(self, value):
        return texto_moneda(value)


class ReporteStockTable(tables.Table):
    descripcion = tables.Column(verbose_name="Producto")
    marca = tables.Column(verbose_name="Marca")
    categoria = tables.Column(verbose_name="Categoría")
    unidad = tables.Column(verbose_name="Unidad")
    stock = tables.Column(verbose_name="Stock")
    aviso = tables.Column(verbose_name="Nota", empty_values=())

    class Meta:
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "No hay productos para los filtros elegidos."
        attrs = {"class": "sheet"}

    def render_stock(self, value):
        return formatear_cantidad(value)

    def render_aviso(self, value):
        return value or "—"


def ajuste_stock_row_actions(record, table=None):
    if table is None:
        return []
    actions = [
        {
            "label": "Ver",
            "icon": "eye",
            "href": table.list_query(**{table.selection_param: record.pk, "ver": 1}),
        }
    ]
    if getattr(table, "update_url_name", ""):
        actions.append(
            {
                "label": "Modificar",
                "icon": "pencil",
                "href": reverse(table.update_url_name, args=[record.pk]),
            }
        )
    if getattr(table, "delete_url_name", ""):
        actions.append(
            {
                "label": "Eliminar",
                "icon": "trash",
                "delete_url": reverse(table.delete_url_name, args=[record.pk]),
                "confirm_message": f"¿Eliminar {record}?",
            }
        )
    return actions


class AjusteStockTable(tables.Table):
    numero = tables.Column(verbose_name="N.º", accessor="pk")
    fecha = tables.Column(verbose_name="Fecha")
    observacion = tables.Column(verbose_name="Observación")
    lineas = tables.Column(verbose_name="Líneas", accessor="lineas")
    acciones = ActionMenuColumn(ajuste_stock_row_actions)

    class Meta:
        model = AjusteStock
        fields = ("numero", "fecha", "observacion", "lineas", "acciones")
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay ajustes de stock."
        attrs = {"class": "sheet"}

    def render_fecha(self, value):
        return value.strftime("%d/%m/%Y") if value else "—"

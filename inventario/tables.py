from urllib.parse import urlencode

import django_tables2 as tables
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from core.moneda import formatear_guaranies
from core.tables import ActionMenuColumn
from inventario.models import Item, ItemCategoria, ItemPrecioHistorial, Marca, UnidadMedida


def marca_row_actions(record, table=None):
    params = {"marca": record.pk}
    request = getattr(table, "request", None)
    if request is not None:
        q = request.GET.get("q", "").strip()
        if q:
            params["q"] = q
        page = request.GET.get("page", "").strip()
        if page:
            params["page"] = page
    return [
        {
            "label": "Modificar",
            "href": f"{reverse('marca_list')}?{urlencode(params)}",
        },
        {
            "label": "Eliminar",
            "delete_url": reverse("marca_delete", args=[record.pk]),
            "confirm_message": f"¿Eliminar {record.descripcion}?",
        },
    ]


class MarcaTable(tables.Table):
    descripcion = tables.Column(verbose_name="Descripción")
    acciones = ActionMenuColumn(
        marca_row_actions,
        verbose_name="",
        attrs={"th": {"class": "sheet-col-acciones"}, "td": {"class": "sheet-col-acciones"}},
    )

    class Meta:
        model = Marca
        fields = ("descripcion", "acciones")
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay marcas."
        attrs = {"class": "sheet"}


def categoria_row_actions(record, table=None):
    params = {"categoria": record.pk}
    request = getattr(table, "request", None)
    if request is not None:
        q = request.GET.get("q", "").strip()
        if q:
            params["q"] = q
        page = request.GET.get("page", "").strip()
        if page:
            params["page"] = page
    return [
        {
            "label": "Modificar",
            "href": f"{reverse('categoria_list')}?{urlencode(params)}",
        },
        {
            "label": "Eliminar",
            "delete_url": reverse("categoria_delete", args=[record.pk]),
            "confirm_message": f"¿Eliminar {record.descripcion}?",
        },
    ]


class CategoriaTable(tables.Table):
    descripcion = tables.Column(verbose_name="Descripción")
    acciones = ActionMenuColumn(
        categoria_row_actions,
        verbose_name="",
        attrs={"th": {"class": "sheet-col-acciones"}, "td": {"class": "sheet-col-acciones"}},
    )

    class Meta:
        model = ItemCategoria
        fields = ("descripcion", "acciones")
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay categorías."
        attrs = {"class": "sheet"}


def unidad_row_actions(record, table=None):
    params = {"unidad": record.pk}
    request = getattr(table, "request", None)
    if request is not None:
        q = request.GET.get("q", "").strip()
        if q:
            params["q"] = q
        page = request.GET.get("page", "").strip()
        if page:
            params["page"] = page
    return [
        {
            "label": "Modificar",
            "href": f"{reverse('unidad_list')}?{urlencode(params)}",
        },
        {
            "label": "Eliminar",
            "delete_url": reverse("unidad_delete", args=[record.pk]),
            "confirm_message": f"¿Eliminar {record}?",
        },
    ]


class UnidadTable(tables.Table):
    id = tables.Column(verbose_name="Código")
    descripcion = tables.Column(verbose_name="Descripción")
    simbolo = tables.Column(verbose_name="Símbolo")
    acciones = ActionMenuColumn(
        unidad_row_actions,
        verbose_name="",
        attrs={"th": {"class": "sheet-col-acciones"}, "td": {"class": "sheet-col-acciones"}},
    )

    class Meta:
        model = UnidadMedida
        fields = ("id", "descripcion", "simbolo", "acciones")
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay unidades."
        attrs = {"class": "sheet"}


def item_row_actions(record, table=None):
    params = {"item": record.pk}
    request = getattr(table, "request", None)
    if request is not None:
        q = request.GET.get("q", "").strip()
        if q:
            params["q"] = q
        page = request.GET.get("page", "").strip()
        if page:
            params["page"] = page
    return [
        {
            "label": "Modificar",
            "href": f"{reverse('item_list')}?{urlencode(params)}",
        },
        {
            "label": "Eliminar",
            "delete_url": reverse("item_delete", args=[record.pk]),
            "confirm_message": f"¿Eliminar {record.descripcion}?",
        },
    ]


class ItemTable(tables.Table):
    descripcion = tables.Column(verbose_name="Descripción")
    tipo = tables.Column(verbose_name="Tipo", accessor="get_tipo_display")
    marca = tables.Column(verbose_name="Marca")
    categoria = tables.Column(verbose_name="Categoría")
    unidad_medida = tables.Column(verbose_name="Unidad", accessor="unidad_medida__simbolo")
    tasa_iva = tables.Column(verbose_name="Tasa IVA", accessor="get_tasa_iva_display")
    acciones = ActionMenuColumn(
        item_row_actions,
        verbose_name="",
        attrs={"th": {"class": "sheet-col-acciones"}, "td": {"class": "sheet-col-acciones"}},
    )

    class Meta:
        model = Item
        fields = (
            "descripcion",
            "tipo",
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
        return "Sí" if value else "No"

from urllib.parse import urlencode

import django_tables2 as tables
from django.urls import reverse

from core.tables import ActionMenuColumn
from inventario.models import Item, ItemCategoria, Marca, UnidadMedida


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
    unidad_medida = tables.Column(verbose_name="Unidad")
    acciones = ActionMenuColumn(
        item_row_actions,
        verbose_name="",
        attrs={"th": {"class": "sheet-col-acciones"}, "td": {"class": "sheet-col-acciones"}},
    )

    class Meta:
        model = Item
        fields = ("descripcion", "tipo", "marca", "categoria", "unidad_medida", "acciones")
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay ítems."
        attrs = {"class": "sheet"}

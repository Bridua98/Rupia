import django_tables2 as tables
from django.template.loader import render_to_string
from django.urls import reverse

ATTRS_MONEDA = {
    "th": {"class": "sheet-col-moneda"},
    "td": {"class": "sheet-col-moneda"},
}
ATTRS_NUM = {
    "th": {"class": "sheet-col-num"},
    "td": {"class": "sheet-col-num"},
}


def mantenimiento_row_actions(record, table=None):
    """Opciones estándar de un mantenimiento: Ver, Modificar y Eliminar."""
    if table is None:
        return []
    list_query = getattr(table, "list_query", None)
    selection_param = getattr(table, "selection_param", None)
    if not list_query or not selection_param:
        return []

    actions = [
        {
            "label": "Ver",
            "icon": "eye",
            "href": list_query(**{selection_param: record.pk, "ver": 1}),
        },
    ]
    if getattr(table, "update_url_name", ""):
        actions.append(
            {
                "label": "Modificar",
                "href": list_query(**{selection_param: record.pk}),
            }
        )
    delete_url_name = getattr(table, "delete_url_name", "")
    if delete_url_name:
        actions.append(
            {
                "label": "Eliminar",
                "delete_url": reverse(delete_url_name, args=[record.pk]),
                "confirm_message": f"¿Eliminar {record}?",
            }
        )
    return actions


class ActionMenuColumn(tables.Column):
    """Columna con el menú estándar de acciones por fila."""

    empty_values = ()
    exclude_from_export = True

    def __init__(self, get_actions=None, **extra):
        self.get_actions = get_actions or mantenimiento_row_actions
        extra.setdefault("verbose_name", "")
        extra.setdefault("orderable", False)
        extra.setdefault(
            "attrs",
            {"th": {"class": "sheet-col-acciones"}, "td": {"class": "sheet-col-acciones"}},
        )
        super().__init__(**extra)

    def render(self, value, record, table):
        return render_to_string(
            "core/action_menu.html",
            {
                "record": record,
                "actions": self.get_actions(record, table),
            },
            request=getattr(table, "request", None),
        )

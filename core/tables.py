import django_tables2 as tables
from django.template.loader import render_to_string


class ActionMenuColumn(tables.Column):
    """Columna con menú desplegable de acciones por fila."""

    empty_values = ()
    exclude_from_export = True

    def __init__(self, get_actions, **extra):
        self.get_actions = get_actions
        extra.setdefault("verbose_name", "Acciones")
        extra.setdefault("orderable", False)
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

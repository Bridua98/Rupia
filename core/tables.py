from django.template.loader import render_to_string

import django_tables2 as tables


class ActionMenuColumn(tables.Column):
    """Columna con menú desplegable de acciones por fila."""

    empty_values = ()

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
                "actions": self.get_actions(record),
            },
        )

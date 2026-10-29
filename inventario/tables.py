from django.urls import reverse

import django_tables2 as tables

from core.tables import ActionMenuColumn
from inventario.models import Marca


def marca_row_actions(record):
    return [
        {
            "label": "Modificar",
            "href": reverse("marca_update", args=[record.pk]),
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
        attrs={"th": {"class": "sheet-col-acciones"}, "td": {"class": "sheet-col-acciones"}},
    )

    class Meta:
        model = Marca
        fields = ("descripcion", "acciones")
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay marcas."
        attrs = {"class": "sheet"}

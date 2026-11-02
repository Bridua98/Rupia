from urllib.parse import urlencode

import django_tables2 as tables
from django.urls import reverse

from core.tables import ActionMenuColumn
from cuentas.models import Cuenta


def cuenta_row_actions(record, table=None):
    params = {"cuenta": record.pk}
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
            "href": f"{reverse('cuenta_list')}?{urlencode(params)}",
        },
        {
            "label": "Eliminar",
            "delete_url": reverse("cuenta_delete", args=[record.pk]),
            "confirm_message": f"¿Eliminar {record.descripcion}?",
        },
    ]


class CuentaTable(tables.Table):
    descripcion = tables.Column(verbose_name="Descripción")
    nombre_corto = tables.Column(verbose_name="Nombre corto")
    tipo = tables.Column(verbose_name="Tipo", accessor="tipo_caja")
    numero = tables.Column(verbose_name="Número")
    acciones = ActionMenuColumn(
        cuenta_row_actions,
        verbose_name="",
        attrs={"th": {"class": "sheet-col-acciones"}, "td": {"class": "sheet-col-acciones"}},
    )

    class Meta:
        model = Cuenta
        fields = ("descripcion", "nombre_corto", "tipo", "numero", "acciones")
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay cuentas."
        attrs = {"class": "sheet"}

    def render_numero(self, value):
        return value or "—"

from urllib.parse import urlencode

import django_tables2 as tables
from django.urls import reverse

from core.tables import ActionMenuColumn
from negocio.models import UnidadNegocio


def unidad_negocio_row_actions(record, table=None):
    params = {"unidad_negocio": record.pk}
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
            "href": f"{reverse('unidad_negocio_list')}?{urlencode(params)}",
        },
        {
            "label": "Eliminar",
            "delete_url": reverse("unidad_negocio_delete", args=[record.pk]),
            "confirm_message": f"¿Eliminar {record}?",
        },
    ]


class UnidadNegocioTable(tables.Table):
    descripcion = tables.Column(verbose_name="Descripción")
    abreviado = tables.Column(verbose_name="Abreviado")
    acciones = ActionMenuColumn(
        unidad_negocio_row_actions,
        verbose_name="",
        attrs={"th": {"class": "sheet-col-acciones"}, "td": {"class": "sheet-col-acciones"}},
    )

    class Meta:
        model = UnidadNegocio
        fields = ("descripcion", "abreviado", "acciones")
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay unidades de negocio."
        attrs = {"class": "sheet"}

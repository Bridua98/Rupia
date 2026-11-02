from urllib.parse import urlencode

import django_tables2 as tables
from django.urls import reverse
from django.utils.html import format_html_join

from core.tables import ActionMenuColumn
from personas.models import Persona


def persona_row_actions(record, table=None):
    params = {"persona": record.pk}
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
            "href": f"{reverse('persona_list')}?{urlencode(params)}",
        },
        {
            "label": "Eliminar",
            "delete_url": reverse("persona_delete", args=[record.pk]),
            "confirm_message": f"¿Eliminar {record}?",
        },
    ]


class PersonaTable(tables.Table):
    razon_social = tables.Column(verbose_name="Razón social")
    tipo = tables.Column(verbose_name="Tipo", accessor="roles_texto")
    documento = tables.Column(verbose_name="Documento", accessor="documento")
    celular = tables.Column(verbose_name="Celular")
    activo = tables.Column(verbose_name="Activo")
    acciones = ActionMenuColumn(
        persona_row_actions,
        verbose_name="",
        attrs={"th": {"class": "sheet-col-acciones"}, "td": {"class": "sheet-col-acciones"}},
    )

    class Meta:
        model = Persona
        fields = (
            "razon_social",
            "tipo",
            "documento",
            "celular",
            "activo",
            "acciones",
        )
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay personas."
        attrs = {"class": "sheet"}

    def render_tipo(self, value, record):
        if not record.roles_lista:
            return "—"
        return format_html_join(
            "",
            '<span class="persona-rol">{}</span>',
            ((rol,) for rol in record.roles_lista),
        )

    def render_activo(self, value):
        return "Sí" if value else "No"

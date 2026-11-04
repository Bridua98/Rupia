import django_tables2 as tables
from django.utils.html import format_html_join

from core.tables import ActionMenuColumn
from core.vista import html_bool
from personas.models import Persona


class PersonaTable(tables.Table):
    razon_social = tables.Column(verbose_name="Razón social")
    tipo = tables.Column(verbose_name="Tipo", accessor="roles_texto")
    documento = tables.Column(verbose_name="Documento", accessor="documento")
    celular = tables.Column(verbose_name="Celular")
    activo = tables.Column(verbose_name="Activo")
    acciones = ActionMenuColumn()

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
        return html_bool(value)

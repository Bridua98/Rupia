import django_tables2 as tables

from core.tables import ActionMenuColumn
from negocio.models import UnidadNegocio


class UnidadNegocioTable(tables.Table):
    descripcion = tables.Column(verbose_name="Descripción")
    abreviado = tables.Column(verbose_name="Abreviado")
    acciones = ActionMenuColumn()

    class Meta:
        model = UnidadNegocio
        fields = ("descripcion", "abreviado", "acciones")
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay unidades de negocio."
        attrs = {"class": "sheet"}

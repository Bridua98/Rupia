import django_tables2 as tables

from inventario.models import Marca


class MarcaTable(tables.Table):
    descripcion = tables.Column(verbose_name="Descripción")

    class Meta:
        model = Marca
        fields = ("descripcion",)
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay marcas."
        attrs = {"class": "sheet"}

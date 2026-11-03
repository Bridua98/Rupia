import django_tables2 as tables

from core.tables import ActionMenuColumn
from cuentas.models import Cuenta


class CuentaTable(tables.Table):
    descripcion = tables.Column(verbose_name="Descripción")
    nombre_corto = tables.Column(verbose_name="Nombre corto")
    tipo = tables.Column(verbose_name="Tipo", accessor="tipo_caja")
    numero = tables.Column(verbose_name="Número")
    acciones = ActionMenuColumn()

    class Meta:
        model = Cuenta
        fields = ("descripcion", "nombre_corto", "tipo", "numero", "acciones")
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay cuentas."
        attrs = {"class": "sheet"}

    def render_numero(self, value):
        return value or "—"

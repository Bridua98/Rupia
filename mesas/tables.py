import django_tables2 as tables

from core.tables import ActionMenuColumn
from core.vista import html_bool
from mesas.models import Mesa, Sector, SectorItem


class SectorTable(tables.Table):
    nombre = tables.Column(verbose_name="Sector")
    categorias = tables.Column(verbose_name="Categorías", empty_values=())
    activo = tables.Column(verbose_name="Activo")
    acciones = ActionMenuColumn()

    class Meta:
        model = Sector
        fields = ("nombre", "categorias", "activo", "acciones")
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay sectores de preparación."
        attrs = {"class": "sheet"}

    def render_categorias(self, record):
        nombres = [fila.categoria.descripcion for fila in record.categorias.all()]
        return ", ".join(sorted(nombres)) or "—"

    def value_categorias(self, record):
        return self.render_categorias(record)

    def render_activo(self, value):
        return html_bool(value)


class SectorItemTable(tables.Table):
    item = tables.Column(verbose_name="Producto", accessor="item__descripcion")
    sector = tables.Column(verbose_name="Va a", accessor="sector__nombre")
    acciones = ActionMenuColumn()

    class Meta:
        model = SectorItem
        fields = ("item", "sector", "acciones")
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Ningún producto tiene un sector distinto al de su categoría."
        attrs = {"class": "sheet"}


class MesaTable(tables.Table):
    nombre = tables.Column(verbose_name="Mesa")
    zona = tables.Column(verbose_name="Zona")
    capacidad = tables.Column(verbose_name="Capacidad")
    orden = tables.Column(verbose_name="Orden")
    activa = tables.Column(verbose_name="Activa")
    acciones = ActionMenuColumn()

    class Meta:
        model = Mesa
        fields = ("nombre", "zona", "capacidad", "orden", "activa", "acciones")
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay mesas."
        attrs = {"class": "sheet"}

    def render_activa(self, value):
        return html_bool(value)

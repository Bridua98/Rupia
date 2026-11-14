import django_tables2 as tables
from django.utils import timezone
from django.utils.html import format_html

from core.enlaces import html_enlace_origen, url_ver_registro
from core.moneda import html_guaranies
from core.tables import ATTRS_MONEDA, ActionMenuColumn
from core.vista import html_bool, html_situacion
from mesas.historial import nombre_usuario
from mesas.models import Mesa, Sector, SectorItem
from ventas.models import EstadoVenta


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


class ServicioHistorialTable(tables.Table):
    abierta_en = tables.DateTimeColumn(verbose_name="Fecha")
    origen = tables.Column(verbose_name="Origen", empty_values=(), accessor="pk")
    mozo = tables.Column(verbose_name="Mozo")
    estado = tables.Column(verbose_name="Estado")
    total = tables.Column(verbose_name="Total", accessor="total_consumo", attrs=ATTRS_MONEDA)
    comprobante = tables.Column(verbose_name="Comprobante", empty_values=(), accessor="pk")
    acciones = ActionMenuColumn()

    class Meta:
        fields = ("abierta_en", "origen", "mozo", "estado", "total", "comprobante", "acciones")
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay servicios cerrados."
        attrs = {"class": "sheet"}

    def render_abierta_en(self, value):
        if value is None:
            return "—"
        return timezone.localtime(value).strftime("%d/%m/%Y %H:%M")

    def render_origen(self, record):
        return record.titulo

    def render_mozo(self, value):
        return nombre_usuario(value) or "—"

    def render_estado(self, value, record):
        return html_situacion(value, record.get_estado_display())

    def render_total(self, value):
        return html_guaranies(value or 0)

    def render_comprobante(self, record):
        partes = []
        vistos = set()
        for linea in getattr(record, "lineas_cobradas", ()):
            venta = linea.venta_detalle.venta
            if venta.pk in vistos:
                continue
            vistos.add(venta.pk)
            numero = venta.numero_completo or f"Venta {venta.pk}"
            texto = f"{venta.get_tipo_comprobante_display()} {numero}"
            if venta.estado in (EstadoVenta.COBRADA, EstadoVenta.ANULADA):
                partes.append(
                    html_enlace_origen(texto, url_ver_registro("venta_list", "venta", venta.pk))
                )
            else:
                partes.append(texto)
        if not partes:
            return "—"
        resultado = partes[0]
        for parte in partes[1:]:
            resultado = format_html("{}, {}", resultado, parte)
        return resultado

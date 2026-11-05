import django_tables2 as tables

from core.moneda import html_guaranies
from core.tables import ATTRS_MONEDA, ActionMenuColumn
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


def _clase_detalle(record):
    if getattr(record, "es_saldo_anterior", False):
        return "is-saldo-anterior"
    return ""


class DisponibilidadDetalleTable(tables.Table):
    cuenta = tables.Column(verbose_name="Cuenta")
    fecha = tables.Column(verbose_name="Fecha", empty_values=())
    comprobante = tables.Column(verbose_name="Comprobante")
    origen = tables.Column(verbose_name="Origen", empty_values=())
    debe = tables.Column(verbose_name="Debe", empty_values=(), attrs=ATTRS_MONEDA)
    haber = tables.Column(verbose_name="Haber", empty_values=(), attrs=ATTRS_MONEDA)
    saldo = tables.Column(verbose_name="Saldo", attrs=ATTRS_MONEDA)

    class Meta:
        orderable = False
        template_name = "django_tables2/rupia_totales_disponibilidad.html"
        empty_text = "No hay movimientos para los filtros elegidos."
        attrs = {"class": "sheet sheet-reporte"}
        row_attrs = {"class": _clase_detalle}

    def render_fecha(self, value):
        return value.strftime("%d/%m/%Y") if value else "—"

    def render_origen(self, value):
        return value or "—"

    def render_debe(self, value):
        return html_guaranies(value)

    def render_haber(self, value):
        return html_guaranies(value)

    def render_saldo(self, value):
        return html_guaranies(value)


class DisponibilidadResumenTable(tables.Table):
    cuenta = tables.Column(verbose_name="Cuenta")
    saldo_anterior = tables.Column(verbose_name="Saldo anterior", attrs=ATTRS_MONEDA)
    debe = tables.Column(verbose_name="Debe", attrs=ATTRS_MONEDA)
    haber = tables.Column(verbose_name="Haber", attrs=ATTRS_MONEDA)
    saldo = tables.Column(verbose_name="Saldo", attrs=ATTRS_MONEDA)

    class Meta:
        orderable = False
        template_name = "django_tables2/rupia_totales_disponibilidad.html"
        empty_text = "No hay movimientos para los filtros elegidos."
        attrs = {"class": "sheet sheet-reporte"}

    def render_saldo_anterior(self, value):
        return html_guaranies(value)

    def render_debe(self, value):
        return html_guaranies(value)

    def render_haber(self, value):
        return html_guaranies(value)

    def render_saldo(self, value):
        return html_guaranies(value)

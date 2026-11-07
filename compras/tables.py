import django_tables2 as tables
from django.urls import reverse
from django.utils.html import format_html

from compras.models import Compra, EstadoCompra
from core.enlaces import html_enlace_origen, url_ver_registro
from core.moneda import html_guaranies
from core.tables import ATTRS_MONEDA, ATTRS_NUM, ActionMenuColumn
from core.vista import html_situacion


def compra_row_actions(record, table=None):
    if table is None:
        return []
    list_query = getattr(table, "list_query", None)
    selection_param = getattr(table, "selection_param", None)
    actions = []
    if list_query and selection_param:
        actions.append(
            {
                "label": "Ver",
                "icon": "eye",
                "href": list_query(**{selection_param: record.pk, "ver": 1}),
            }
        )
    if record.estado == EstadoCompra.CONFIRMADA and getattr(table, "puede_anular", False):
        actions.append(
            {
                "label": "Anular",
                "icon": "trash",
                "delete_url": reverse("compra_anular", args=[record.pk]),
                "confirm_message": f"¿Anular {record}?",
                "submit_label": "Anular",
            }
        )
    return actions


class CompraTable(tables.Table):
    fecha = tables.Column(verbose_name="Fecha")
    numero_completo = tables.Column(verbose_name="Número", empty_values=())
    tipo = tables.Column(verbose_name="Tipo")
    proveedor = tables.Column(verbose_name="Proveedor", empty_values=())
    estado = tables.Column(verbose_name="Estado")
    importe = tables.Column(
        verbose_name="Total",
        empty_values=(),
        attrs=ATTRS_MONEDA,
    )
    acciones = ActionMenuColumn(get_actions=compra_row_actions)

    class Meta:
        model = Compra
        fields = (
            "fecha",
            "numero_completo",
            "tipo",
            "proveedor",
            "estado",
            "importe",
            "acciones",
        )
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay compras."
        attrs = {"class": "sheet"}

    def render_fecha(self, value):
        return value.strftime("%d/%m/%Y") if value else "—"

    def render_numero_completo(self, value, record):
        if value:
            return value
        if not record.es_factura:
            return f"Egreso {record.pk}"
        return "—"

    def render_tipo(self, value, record):
        return record.get_tipo_display()

    def render_proveedor(self, value):
        return str(value) if value else "—"

    def render_estado(self, value, record):
        return html_situacion(value, record.get_estado_display())

    def render_importe(self, value):
        return html_guaranies(value or 0)


class ReporteGastosDetalleTable(tables.Table):
    fecha = tables.Column(verbose_name="Fecha")
    comprobante = tables.Column(verbose_name="Comprobante")
    tipo_comprobante = tables.Column(verbose_name="Tipo")
    proveedor = tables.Column(verbose_name="Proveedor")
    timbrado = tables.Column(verbose_name="Timbrado")
    cuenta = tables.Column(verbose_name="Cuenta")
    unidad_negocio = tables.Column(verbose_name="Unidad de negocio")
    producto = tables.Column(verbose_name="Producto")
    tipo_item = tables.Column(verbose_name="Clase")
    tasa_iva = tables.Column(verbose_name="IVA %", attrs=ATTRS_NUM)
    gravado = tables.Column(verbose_name="Gravado", attrs=ATTRS_MONEDA)
    iva = tables.Column(verbose_name="IVA", attrs=ATTRS_MONEDA)
    subtotal = tables.Column(verbose_name="Total", attrs=ATTRS_MONEDA)

    class Meta:
        fields = (
            "fecha",
            "comprobante",
            "tipo_comprobante",
            "proveedor",
            "timbrado",
            "cuenta",
            "unidad_negocio",
            "producto",
            "tipo_item",
            "tasa_iva",
            "gravado",
            "iva",
            "subtotal",
        )
        orderable = False
        template_name = "django_tables2/rupia_totales.html"
        empty_text = "No hay gastos para los filtros elegidos."
        attrs = {"class": "sheet sheet-reporte sheet-gastos"}

    def render_fecha(self, value):
        return value.strftime("%d/%m/%Y")

    def render_comprobante(self, value, record):
        texto = value or "—"
        compra_id = getattr(record, "compra_id", None)
        return html_enlace_origen(texto, url_ver_registro("compra_list", "compra", compra_id))

    def render_tipo_item(self, value):
        clase = "is-salida" if value == "Gasto" else "is-entrada"
        return format_html('<span class="rupia-badge {}">{}</span>', clase, value)

    def render_tasa_iva(self, value):
        return f"{value}%"

    def render_gravado(self, value):
        return html_guaranies(value)

    def render_iva(self, value):
        return html_guaranies(value)

    def render_subtotal(self, value):
        return html_guaranies(value)


class ReporteGastosAgrupadoTable(tables.Table):
    etiqueta = tables.Column(verbose_name="Agrupación")
    detalle = tables.Column(verbose_name="Detalle")
    lineas = tables.Column(verbose_name="Líneas", attrs=ATTRS_NUM)
    gravado = tables.Column(verbose_name="Gravado", attrs=ATTRS_MONEDA)
    iva = tables.Column(verbose_name="IVA", attrs=ATTRS_MONEDA)
    subtotal = tables.Column(verbose_name="Total", attrs=ATTRS_MONEDA)

    class Meta:
        orderable = False
        template_name = "django_tables2/rupia_totales.html"
        empty_text = "No hay gastos para los filtros elegidos."
        attrs = {"class": "sheet sheet-reporte sheet-gastos-agrupado"}

    def render_detalle(self, value):
        return value or "—"

    def render_gravado(self, value):
        return html_guaranies(value)

    def render_iva(self, value):
        return html_guaranies(value)

    def render_subtotal(self, value):
        return html_guaranies(value)

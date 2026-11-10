import django_tables2 as tables
from django.urls import reverse

from core.enlaces import html_enlace_origen, url_origen_caja
from core.moneda import html_guaranies
from core.tables import ATTRS_MONEDA, ActionMenuColumn
from core.vista import html_situacion
from cuentas.models import Cuenta, EstadoTransferencia, Transferencia


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


def transferencia_row_actions(record, table=None):
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
    if record.estado == EstadoTransferencia.CONFIRMADA and getattr(table, "puede_anular", False):
        actions.append(
            {
                "label": "Anular",
                "icon": "trash",
                "delete_url": reverse("transferencia_anular", args=[record.pk]),
                "confirm_message": f"¿Anular {record}?",
                "submit_label": "Anular",
            }
        )
    return actions


class TransferenciaTable(tables.Table):
    fecha = tables.Column(verbose_name="Fecha")
    cuenta_origen = tables.Column(verbose_name="Salida")
    cuenta_destino = tables.Column(verbose_name="Entrada")
    importe = tables.Column(verbose_name="Importe", empty_values=(), attrs=ATTRS_MONEDA)
    comprobante = tables.Column(verbose_name="Comprobante", empty_values=())
    estado = tables.Column(verbose_name="Estado")
    acciones = ActionMenuColumn(get_actions=transferencia_row_actions)

    class Meta:
        model = Transferencia
        fields = (
            "fecha",
            "cuenta_origen",
            "cuenta_destino",
            "importe",
            "comprobante",
            "estado",
            "acciones",
        )
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay transferencias."
        attrs = {"class": "sheet"}

    def render_fecha(self, value):
        return value.strftime("%d/%m/%Y") if value else "—"

    def render_importe(self, value):
        return html_guaranies(value or 0)

    def render_comprobante(self, value):
        return value or "—"

    def render_estado(self, value, record):
        return html_situacion(value, record.get_estado_display())


def _clase_detalle(record):
    if getattr(record, "es_saldo_anterior", False):
        return "is-saldo-anterior"
    return ""


class DisponibilidadDetalleTable(tables.Table):
    cuenta = tables.Column(verbose_name="Cuenta")
    fecha = tables.Column(verbose_name="Fecha", empty_values=())
    comprobante = tables.Column(verbose_name="Comprobante")
    origen = tables.Column(verbose_name="Origen", empty_values=())
    persona = tables.Column(verbose_name="Persona", empty_values=())
    entra = tables.Column(verbose_name="Entra", empty_values=(), attrs=ATTRS_MONEDA)
    salida = tables.Column(verbose_name="Salida", empty_values=(), attrs=ATTRS_MONEDA)
    saldo = tables.Column(verbose_name="Saldo", attrs=ATTRS_MONEDA)

    class Meta:
        orderable = False
        template_name = "django_tables2/rupia_totales_disponibilidad.html"
        empty_text = "No hay movimientos para los filtros elegidos."
        attrs = {"class": "sheet sheet-reporte"}
        row_attrs = {"class": _clase_detalle}

    def render_fecha(self, value):
        return value.strftime("%d/%m/%Y") if value else "—"

    def render_comprobante(self, value, record):
        texto = value or "—"
        if getattr(record, "es_saldo_anterior", False):
            return texto
        return html_enlace_origen(texto, url_origen_caja(record.origen, record.origen_id))

    def render_origen(self, value):
        return value or "—"

    def render_persona(self, value):
        return value or "—"

    def render_entra(self, value):
        return html_guaranies(value)

    def render_salida(self, value):
        return html_guaranies(value)

    def render_saldo(self, value):
        return html_guaranies(value)


class DisponibilidadResumenTable(tables.Table):
    cuenta = tables.Column(verbose_name="Cuenta")
    saldo_anterior = tables.Column(verbose_name="Saldo anterior", attrs=ATTRS_MONEDA)
    entra = tables.Column(verbose_name="Entra", attrs=ATTRS_MONEDA)
    salida = tables.Column(verbose_name="Salida", attrs=ATTRS_MONEDA)
    saldo = tables.Column(verbose_name="Saldo", attrs=ATTRS_MONEDA)

    class Meta:
        orderable = False
        template_name = "django_tables2/rupia_totales_disponibilidad.html"
        empty_text = "No hay movimientos para los filtros elegidos."
        attrs = {"class": "sheet sheet-reporte"}

    def render_saldo_anterior(self, value):
        return html_guaranies(value)

    def render_entra(self, value):
        return html_guaranies(value)

    def render_salida(self, value):
        return html_guaranies(value)

    def render_saldo(self, value):
        return html_guaranies(value)

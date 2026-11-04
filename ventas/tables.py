import django_tables2 as tables
from django.urls import reverse

from core.moneda import html_guaranies
from core.tables import ATTRS_MONEDA, ActionMenuColumn
from ventas.models import EstadoVenta, PuntoExpedicion, TipoAnulacion, TipoComprobante, Venta


def venta_row_actions(record, table=None):
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
    if record.estado == EstadoVenta.COBRADA:
        if record.tipo_comprobante == TipoComprobante.TICKET:
            actions.append(
                {
                    "label": "Ticket",
                    "icon": "receipt",
                    "href": reverse("venta_ticket", args=[record.pk]),
                }
            )
        elif record.tipo_comprobante == TipoComprobante.FACTURA:
            actions.append(
                {
                    "label": "Factura",
                    "icon": "receipt",
                    "href": reverse("venta_factura", args=[record.pk]),
                }
            )
        if getattr(table, "puede_anular", False):
            actions.append(
                {
                    "label": "Anular",
                    "icon": "trash",
                    "delete_url": reverse("venta_anular", args=[record.pk]),
                    "confirm_message": f"¿Anular {record}?",
                    "submit_label": "Anular",
                    "confirm_field": "tipo_anulacion",
                    "confirm_choices": [
                        {
                            "value": TipoAnulacion.FISICA,
                            "label": "Anulación física (el número no se reutiliza)",
                            "checked": True,
                        },
                        {
                            "value": TipoAnulacion.REUTILIZABLE,
                            "label": "El número puede volver a usarse",
                        },
                    ],
                }
            )
    return actions


class TimbradoTable(tables.Table):
    tipo = tables.Column(verbose_name="Comprobante")
    timbrado = tables.Column(verbose_name="Timbrado")
    serie = tables.Column(verbose_name="Serie", empty_values=())
    numero_proximo = tables.Column(verbose_name="Próximo")
    vigencia_hasta = tables.Column(verbose_name="Vigencia hasta")
    habilitado = tables.Column(verbose_name="Habilitado")
    acciones = ActionMenuColumn()

    class Meta:
        model = PuntoExpedicion
        fields = (
            "tipo",
            "timbrado",
            "serie",
            "numero_proximo",
            "vigencia_hasta",
            "habilitado",
            "acciones",
        )
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay timbrados."
        attrs = {"class": "sheet"}

    def render_tipo(self, value, record):
        return record.get_tipo_display()

    def render_serie(self, value, record):
        return record.serie

    def render_habilitado(self, value):
        return "Sí" if value else "No"


class VentaTable(tables.Table):
    fecha = tables.Column(verbose_name="Fecha")
    numero_completo = tables.Column(verbose_name="Número", empty_values=())
    tipo_comprobante = tables.Column(verbose_name="Comprobante")
    cliente = tables.Column(verbose_name="Cliente", empty_values=())
    estado = tables.Column(verbose_name="Estado")
    importe = tables.Column(
        verbose_name="Total",
        empty_values=(),
        attrs=ATTRS_MONEDA,
    )
    acciones = ActionMenuColumn(get_actions=venta_row_actions)

    class Meta:
        model = Venta
        fields = (
            "fecha",
            "numero_completo",
            "tipo_comprobante",
            "cliente",
            "estado",
            "importe",
            "acciones",
        )
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay ventas."
        attrs = {"class": "sheet"}

    def render_fecha(self, value):
        return value.strftime("%d/%m/%Y") if value else "—"

    def render_numero_completo(self, value):
        return value or "—"

    def render_tipo_comprobante(self, value, record):
        return record.get_tipo_comprobante_display()

    def render_cliente(self, value):
        return str(value) if value else "—"

    def render_estado(self, value, record):
        return record.get_estado_display()

    def render_importe(self, value):
        return html_guaranies(value or 0)

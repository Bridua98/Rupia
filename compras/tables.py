import django_tables2 as tables
from django.urls import reverse

from compras.models import Compra, EstadoCompra
from core.moneda import html_guaranies
from core.tables import ATTRS_MONEDA, ActionMenuColumn


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
        return record.get_estado_display()

    def render_importe(self, value):
        return html_guaranies(value or 0)

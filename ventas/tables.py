import django_tables2 as tables

from core.tables import ActionMenuColumn
from ventas.models import PuntoExpedicion


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

from django.contrib import admin

from ventas.models import PuntoExpedicion, Venta, VentaDetalle


@admin.register(PuntoExpedicion)
class PuntoExpedicionAdmin(admin.ModelAdmin):
    list_display = (
        "tipo",
        "establecimiento",
        "codigo",
        "timbrado",
        "numero_proximo",
        "vigencia_hasta",
        "habilitado",
    )


class VentaDetalleInline(admin.TabularInline):
    model = VentaDetalle
    extra = 0


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "numero_completo",
        "fecha",
        "estado",
        "tipo_comprobante",
        "usuario",
    )
    list_filter = ("estado", "tipo_comprobante")
    inlines = [VentaDetalleInline]

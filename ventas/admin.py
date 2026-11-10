from django.contrib import admin

from ventas.models import Maquina, PuntoExpedicion, Venta, VentaDetalle


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


@admin.register(Maquina)
class MaquinaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "punto_ticket", "punto_factura")


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

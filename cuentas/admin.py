from django.contrib import admin

from cuentas.models import Cuenta, Transferencia


@admin.register(Cuenta)
class CuentaAdmin(admin.ModelAdmin):
    list_display = ("descripcion", "nombre_corto", "es_banco", "es_tarjeta", "numero")
    list_filter = ("es_banco", "es_tarjeta")
    search_fields = ("descripcion", "nombre_corto", "numero")


@admin.register(Transferencia)
class TransferenciaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "fecha",
        "cuenta_origen",
        "cuenta_destino",
        "importe",
        "comprobante",
        "estado",
    )
    list_filter = ("estado",)
    search_fields = ("comprobante",)

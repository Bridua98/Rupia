from django.contrib import admin

from cuentas.models import Cuenta


@admin.register(Cuenta)
class CuentaAdmin(admin.ModelAdmin):
    list_display = ("descripcion", "nombre_corto", "es_banco", "es_tarjeta", "numero")
    list_filter = ("es_banco", "es_tarjeta")
    search_fields = ("descripcion", "nombre_corto", "numero")

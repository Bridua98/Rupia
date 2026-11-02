from django.contrib import admin

from negocio.models import UnidadNegocio


@admin.register(UnidadNegocio)
class UnidadNegocioAdmin(admin.ModelAdmin):
    list_display = ("descripcion", "abreviado")
    search_fields = ("descripcion", "abreviado")

from django.contrib import admin

from personas.models import Persona


@admin.register(Persona)
class PersonaAdmin(admin.ModelAdmin):
    list_display = (
        "razon_social",
        "tipo_documento",
        "documento",
        "es_cliente",
        "es_proveedor",
        "es_empleado",
        "activo",
    )
    list_filter = (
        "tipo_documento",
        "genero",
        "es_cliente",
        "es_proveedor",
        "es_empleado",
        "activo",
    )
    search_fields = ("razon_social", "documento", "celular")

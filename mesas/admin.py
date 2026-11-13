from django.contrib import admin

from mesas.models import Mesa, Sector, SectorCategoria, SectorItem


class SectorCategoriaInline(admin.TabularInline):
    model = SectorCategoria
    extra = 0


@admin.register(Sector)
class SectorAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo")
    search_fields = ("nombre",)
    inlines = (SectorCategoriaInline,)


@admin.register(SectorItem)
class SectorItemAdmin(admin.ModelAdmin):
    list_display = ("item", "sector")
    search_fields = ("item__descripcion", "sector__nombre")


@admin.register(Mesa)
class MesaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "zona", "capacidad", "orden", "activa")
    search_fields = ("nombre", "zona")

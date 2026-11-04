from django.contrib import admin

from configuracion.models import Perfil, PerfilPermiso


class PerfilPermisoInline(admin.TabularInline):
    model = PerfilPermiso
    extra = 0


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ("descripcion", "activo")
    search_fields = ("descripcion",)
    filter_horizontal = ("usuarios",)
    inlines = (PerfilPermisoInline,)

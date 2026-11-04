from django.contrib import admin

from compras.models import Compra, CompraDetalle


class CompraDetalleInline(admin.TabularInline):
    model = CompraDetalle
    extra = 0


@admin.register(Compra)
class CompraAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "numero_completo",
        "fecha",
        "estado",
        "tipo",
        "proveedor",
        "usuario",
    )
    list_filter = ("estado", "tipo")
    inlines = [CompraDetalleInline]

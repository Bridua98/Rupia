from django.contrib import admin

from inventario.models import (
    AjusteStock,
    AjusteStockDetalle,
    Item,
    ItemCategoria,
    ItemMovimiento,
    ItemPrecioHistorial,
    Marca,
    UnidadMedida,
)


@admin.register(Marca)
class MarcaAdmin(admin.ModelAdmin):
    list_display = ("descripcion",)
    search_fields = ("descripcion",)


@admin.register(ItemCategoria)
class ItemCategoriaAdmin(admin.ModelAdmin):
    list_display = ("descripcion",)
    search_fields = ("descripcion",)


@admin.register(UnidadMedida)
class UnidadMedidaAdmin(admin.ModelAdmin):
    list_display = ("id", "descripcion", "simbolo")
    search_fields = ("descripcion", "simbolo")


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = (
        "descripcion",
        "tipo",
        "marca",
        "categoria",
        "precio",
        "precio_segun_costo",
        "tasa_iva",
        "activo",
    )
    list_filter = ("tipo", "tasa_iva", "activo", "precio_segun_costo", "marca", "categoria")
    search_fields = ("descripcion", "codigo_barra")
    autocomplete_fields = ("marca", "categoria", "unidad_medida")


@admin.register(ItemMovimiento)
class ItemMovimientoAdmin(admin.ModelAdmin):
    list_display = ("id", "item", "tipo", "fecha_movimiento", "cantidad", "subtotal", "es_vigente")
    list_filter = ("tipo", "es_vigente", "fecha_movimiento")
    search_fields = ("item__descripcion", "secuencia_origen")
    autocomplete_fields = ("item", "unidad_medida")


class AjusteStockDetalleInline(admin.TabularInline):
    model = AjusteStockDetalle
    extra = 0
    autocomplete_fields = ("item", "unidad_medida")


@admin.register(AjusteStock)
class AjusteStockAdmin(admin.ModelAdmin):
    list_display = ("id", "fecha", "observacion")
    search_fields = ("observacion", "fecha")
    inlines = [AjusteStockDetalleInline]


@admin.register(AjusteStockDetalle)
class AjusteStockDetalleAdmin(admin.ModelAdmin):
    list_display = ("id", "ajuste", "item", "cantidad_anterior", "cantidad_nueva", "cantidad")
    autocomplete_fields = ("ajuste", "item", "unidad_medida")


@admin.register(ItemPrecioHistorial)
class ItemPrecioHistorialAdmin(admin.ModelAdmin):
    list_display = (
        "fecha",
        "usuario",
        "item",
        "precio_anterior",
        "precio_nuevo",
        "porcentaje",
        "origen",
    )
    list_filter = ("origen", "segun_costo")
    search_fields = ("item__descripcion", "usuario__username")
    autocomplete_fields = ("item", "usuario")
    readonly_fields = (
        "item",
        "precio_anterior",
        "precio_nuevo",
        "ultimo_costo",
        "porcentaje",
        "segun_costo",
        "origen",
        "usuario",
        "fecha",
        "lote",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

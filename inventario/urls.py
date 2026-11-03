from django.urls import path

from core.mantenimiento import mantenimiento_salida
from inventario.reporte_productos import ReporteProductosListView
from inventario.views import (
    CategoriaCreateView,
    CategoriaDeleteView,
    CategoriaListView,
    CategoriaUpdateView,
    ItemCreateView,
    ItemDeleteView,
    ItemImagenView,
    ItemListView,
    ItemUpdateView,
    MarcaCreateView,
    MarcaDeleteView,
    MarcaListView,
    MarcaUpdateView,
    PrecioHistorialListView,
    PrecioListView,
    UnidadCreateView,
    UnidadDeleteView,
    UnidadListView,
    UnidadUpdateView,
)

urlpatterns = [
    path("marcas/", MarcaListView.as_view(), name="marca_list"),
    path(
        "marcas/imprimir/",
        mantenimiento_salida(MarcaListView, "print").as_view(),
        name="marca_print",
    ),
    path(
        "marcas/exportar.xlsx",
        mantenimiento_salida(MarcaListView, "xlsx").as_view(),
        name="marca_export_xlsx",
    ),
    path(
        "marcas/exportar.pdf",
        mantenimiento_salida(MarcaListView, "pdf").as_view(),
        name="marca_export_pdf",
    ),
    path("marcas/nueva/", MarcaCreateView.as_view(), name="marca_create"),
    path("marcas/<int:pk>/", MarcaUpdateView.as_view(), name="marca_update"),
    path("marcas/<int:pk>/eliminar/", MarcaDeleteView.as_view(), name="marca_delete"),
    path("categorias/", CategoriaListView.as_view(), name="categoria_list"),
    path(
        "categorias/imprimir/",
        mantenimiento_salida(CategoriaListView, "print").as_view(),
        name="categoria_print",
    ),
    path(
        "categorias/exportar.xlsx",
        mantenimiento_salida(CategoriaListView, "xlsx").as_view(),
        name="categoria_export_xlsx",
    ),
    path(
        "categorias/exportar.pdf",
        mantenimiento_salida(CategoriaListView, "pdf").as_view(),
        name="categoria_export_pdf",
    ),
    path("categorias/nueva/", CategoriaCreateView.as_view(), name="categoria_create"),
    path("categorias/<int:pk>/", CategoriaUpdateView.as_view(), name="categoria_update"),
    path(
        "categorias/<int:pk>/eliminar/",
        CategoriaDeleteView.as_view(),
        name="categoria_delete",
    ),
    path("unidades/", UnidadListView.as_view(), name="unidad_list"),
    path(
        "unidades/imprimir/",
        mantenimiento_salida(UnidadListView, "print").as_view(),
        name="unidad_print",
    ),
    path(
        "unidades/exportar.xlsx",
        mantenimiento_salida(UnidadListView, "xlsx").as_view(),
        name="unidad_export_xlsx",
    ),
    path(
        "unidades/exportar.pdf",
        mantenimiento_salida(UnidadListView, "pdf").as_view(),
        name="unidad_export_pdf",
    ),
    path("unidades/nueva/", UnidadCreateView.as_view(), name="unidad_create"),
    path("unidades/<int:pk>/", UnidadUpdateView.as_view(), name="unidad_update"),
    path("unidades/<int:pk>/eliminar/", UnidadDeleteView.as_view(), name="unidad_delete"),
    path("items/", ItemListView.as_view(), name="item_list"),
    path(
        "items/imprimir/",
        mantenimiento_salida(ItemListView, "print").as_view(),
        name="item_print",
    ),
    path(
        "items/exportar.xlsx",
        mantenimiento_salida(ItemListView, "xlsx").as_view(),
        name="item_export_xlsx",
    ),
    path(
        "items/exportar.pdf",
        mantenimiento_salida(ItemListView, "pdf").as_view(),
        name="item_export_pdf",
    ),
    path("items/nueva/", ItemCreateView.as_view(), name="item_create"),
    path("items/imagen/<str:nombre>/", ItemImagenView.as_view(), name="item_imagen"),
    path("items/<int:pk>/", ItemUpdateView.as_view(), name="item_update"),
    path("items/<int:pk>/eliminar/", ItemDeleteView.as_view(), name="item_delete"),
    path("precios/", PrecioListView.as_view(), name="precio_list"),
    path("precios/historial/", PrecioHistorialListView.as_view(), name="precio_historial"),
    path(
        "precios/historial/imprimir/",
        mantenimiento_salida(PrecioHistorialListView, "print").as_view(),
        name="precio_historial_print",
    ),
    path(
        "precios/historial/exportar.xlsx",
        mantenimiento_salida(PrecioHistorialListView, "xlsx").as_view(),
        name="precio_historial_export_xlsx",
    ),
    path(
        "precios/historial/exportar.pdf",
        mantenimiento_salida(PrecioHistorialListView, "pdf").as_view(),
        name="precio_historial_export_pdf",
    ),
    path("reportes/productos/", ReporteProductosListView.as_view(), name="reporte_productos"),
    path(
        "reportes/productos/imprimir/",
        mantenimiento_salida(ReporteProductosListView, "print").as_view(),
        name="reporte_productos_print",
    ),
    path(
        "reportes/productos/exportar.xlsx",
        mantenimiento_salida(ReporteProductosListView, "xlsx").as_view(),
        name="reporte_productos_export_xlsx",
    ),
    path(
        "reportes/productos/exportar.pdf",
        mantenimiento_salida(ReporteProductosListView, "pdf").as_view(),
        name="reporte_productos_export_pdf",
    ),
]

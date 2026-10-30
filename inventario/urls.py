from django.urls import path

from core.mantenimiento import mantenimiento_salida
from inventario.views import (
    CategoriaCreateView,
    CategoriaDeleteView,
    CategoriaListView,
    CategoriaUpdateView,
    UnidadCreateView,
    UnidadDeleteView,
    UnidadListView,
    UnidadUpdateView,
    MarcaCreateView,
    MarcaDeleteView,
    MarcaListView,
    MarcaUpdateView,
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
]

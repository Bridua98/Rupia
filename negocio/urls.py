from django.urls import path

from core.mantenimiento import mantenimiento_salida
from negocio.views import (
    UnidadNegocioCreateView,
    UnidadNegocioDeleteView,
    UnidadNegocioListView,
    UnidadNegocioUpdateView,
)

urlpatterns = [
    path("", UnidadNegocioListView.as_view(), name="unidad_negocio_list"),
    path(
        "imprimir/",
        mantenimiento_salida(UnidadNegocioListView, "print").as_view(),
        name="unidad_negocio_print",
    ),
    path(
        "exportar.xlsx",
        mantenimiento_salida(UnidadNegocioListView, "xlsx").as_view(),
        name="unidad_negocio_export_xlsx",
    ),
    path(
        "exportar.pdf",
        mantenimiento_salida(UnidadNegocioListView, "pdf").as_view(),
        name="unidad_negocio_export_pdf",
    ),
    path("nueva/", UnidadNegocioCreateView.as_view(), name="unidad_negocio_create"),
    path("<int:pk>/", UnidadNegocioUpdateView.as_view(), name="unidad_negocio_update"),
    path(
        "<int:pk>/eliminar/",
        UnidadNegocioDeleteView.as_view(),
        name="unidad_negocio_delete",
    ),
]

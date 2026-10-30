from django.urls import path

from core.mantenimiento import mantenimiento_salida
from inventario.views import MarcaCreateView, MarcaDeleteView, MarcaListView, MarcaUpdateView

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
]

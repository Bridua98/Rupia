from django.urls import path

from core.mantenimiento import mantenimiento_salida
from cuentas.views import (
    CuentaCreateView,
    CuentaDeleteView,
    CuentaListView,
    CuentaUpdateView,
)

urlpatterns = [
    path("", CuentaListView.as_view(), name="cuenta_list"),
    path(
        "imprimir/",
        mantenimiento_salida(CuentaListView, "print").as_view(),
        name="cuenta_print",
    ),
    path(
        "exportar.xlsx",
        mantenimiento_salida(CuentaListView, "xlsx").as_view(),
        name="cuenta_export_xlsx",
    ),
    path(
        "exportar.pdf",
        mantenimiento_salida(CuentaListView, "pdf").as_view(),
        name="cuenta_export_pdf",
    ),
    path("nueva/", CuentaCreateView.as_view(), name="cuenta_create"),
    path("<int:pk>/", CuentaUpdateView.as_view(), name="cuenta_update"),
    path("<int:pk>/eliminar/", CuentaDeleteView.as_view(), name="cuenta_delete"),
]

from django.urls import path

from core.mantenimiento import mantenimiento_salida
from cuentas.disponibilidad import ReporteDisponibilidadListView
from cuentas.views import (
    CuentaCreateView,
    CuentaDeleteView,
    CuentaListView,
    CuentaUpdateView,
)

urlpatterns = [
    path("", CuentaListView.as_view(), name="cuenta_list"),
    path(
        "disponibilidad/",
        ReporteDisponibilidadListView.as_view(),
        name="reporte_disponibilidad",
    ),
    path(
        "disponibilidad/imprimir/",
        mantenimiento_salida(ReporteDisponibilidadListView, "print").as_view(),
        name="reporte_disponibilidad_print",
    ),
    path(
        "disponibilidad/exportar.xlsx",
        mantenimiento_salida(ReporteDisponibilidadListView, "xlsx").as_view(),
        name="reporte_disponibilidad_export_xlsx",
    ),
    path(
        "disponibilidad/exportar.pdf",
        mantenimiento_salida(ReporteDisponibilidadListView, "pdf").as_view(),
        name="reporte_disponibilidad_export_pdf",
    ),
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

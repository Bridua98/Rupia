from django.urls import path

from core.mantenimiento import mantenimiento_salida
from cuentas.disponibilidad import ReporteDisponibilidadListView
from cuentas.views import (
    AnularTransferenciaView,
    CuentaCreateView,
    CuentaDeleteView,
    CuentaListView,
    CuentaUpdateView,
    TransferenciaCreateView,
    TransferenciaListView,
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
    path("transferencias/", TransferenciaListView.as_view(), name="transferencia_list"),
    path(
        "transferencias/imprimir/",
        mantenimiento_salida(TransferenciaListView, "print").as_view(),
        name="transferencia_print",
    ),
    path(
        "transferencias/exportar.xlsx",
        mantenimiento_salida(TransferenciaListView, "xlsx").as_view(),
        name="transferencia_export_xlsx",
    ),
    path(
        "transferencias/exportar.pdf",
        mantenimiento_salida(TransferenciaListView, "pdf").as_view(),
        name="transferencia_export_pdf",
    ),
    path(
        "transferencias/nueva/",
        TransferenciaCreateView.as_view(),
        name="transferencia_create",
    ),
    path(
        "transferencias/<int:pk>/anular/",
        AnularTransferenciaView.as_view(),
        name="transferencia_anular",
    ),
    path("nueva/", CuentaCreateView.as_view(), name="cuenta_create"),
    path("<int:pk>/", CuentaUpdateView.as_view(), name="cuenta_update"),
    path("<int:pk>/eliminar/", CuentaDeleteView.as_view(), name="cuenta_delete"),
]

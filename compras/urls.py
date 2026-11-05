from django.urls import path

from compras.reporte_gastos import ReporteGastosListView
from compras.views import (
    AgregarItemView,
    AnularCompraView,
    BuscarItemsView,
    BuscarProveedoresView,
    CancelarCompraView,
    CompraFormView,
    CompraListView,
    ConfirmarCompraView,
    LineaCompraView,
    ValidarNumeroView,
)
from core.mantenimiento import mantenimiento_salida

urlpatterns = [
    path("", CompraListView.as_view(), name="compra_list"),
    path(
        "imprimir/",
        mantenimiento_salida(CompraListView, "print").as_view(),
        name="compra_print",
    ),
    path(
        "exportar.xlsx",
        mantenimiento_salida(CompraListView, "xlsx").as_view(),
        name="compra_export_xlsx",
    ),
    path(
        "exportar.pdf",
        mantenimiento_salida(CompraListView, "pdf").as_view(),
        name="compra_export_pdf",
    ),
    path("nueva/", CompraFormView.as_view(), name="compra_nueva"),
    path("nueva/buscar/", BuscarItemsView.as_view(), name="compra_buscar"),
    path("nueva/numero/", ValidarNumeroView.as_view(), name="compra_numero"),
    path("nueva/proveedores/", BuscarProveedoresView.as_view(), name="compra_proveedores"),
    path("nueva/agregar/", AgregarItemView.as_view(), name="compra_agregar"),
    path("nueva/lineas/<int:pk>/", LineaCompraView.as_view(), name="compra_linea"),
    path("nueva/confirmar/", ConfirmarCompraView.as_view(), name="compra_confirmar"),
    path("nueva/cancelar/", CancelarCompraView.as_view(), name="compra_cancelar"),
    path("reportes/gastos/", ReporteGastosListView.as_view(), name="reporte_gastos"),
    path(
        "reportes/gastos/imprimir/",
        mantenimiento_salida(ReporteGastosListView, "print").as_view(),
        name="reporte_gastos_print",
    ),
    path(
        "reportes/gastos/exportar.xlsx",
        mantenimiento_salida(ReporteGastosListView, "xlsx").as_view(),
        name="reporte_gastos_export_xlsx",
    ),
    path(
        "reportes/gastos/exportar.pdf",
        mantenimiento_salida(ReporteGastosListView, "pdf").as_view(),
        name="reporte_gastos_export_pdf",
    ),
    path("<int:pk>/anular/", AnularCompraView.as_view(), name="compra_anular"),
]

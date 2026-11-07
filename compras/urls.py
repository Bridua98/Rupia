from django.urls import path

from compras.pagos_views import (
    AnularPagoProveedorView,
    PagoProveedorListView,
    PagoProveedorNuevoView,
)
from compras.reporte_cuentas_pagar import ReporteCuentasPagarListView
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
    CuotaCompraView,
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
    path("nueva/cuotas/", CuotaCompraView.as_view(), name="compra_cuota_agregar"),
    path("nueva/cuotas/<int:pk>/", CuotaCompraView.as_view(), name="compra_cuota"),
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
    path("pagos/", PagoProveedorListView.as_view(), name="pago_proveedor_list"),
    path(
        "pagos/imprimir/",
        mantenimiento_salida(PagoProveedorListView, "print").as_view(),
        name="pago_proveedor_print",
    ),
    path(
        "pagos/exportar.xlsx",
        mantenimiento_salida(PagoProveedorListView, "xlsx").as_view(),
        name="pago_proveedor_export_xlsx",
    ),
    path(
        "pagos/exportar.pdf",
        mantenimiento_salida(PagoProveedorListView, "pdf").as_view(),
        name="pago_proveedor_export_pdf",
    ),
    path("pagos/nueva/", PagoProveedorNuevoView.as_view(), name="pago_proveedor_nuevo"),
    path(
        "pagos/<int:pk>/anular/",
        AnularPagoProveedorView.as_view(),
        name="pago_proveedor_anular",
    ),
    path(
        "reportes/cuentas-a-pagar/",
        ReporteCuentasPagarListView.as_view(),
        name="reporte_cuentas_pagar",
    ),
    path(
        "reportes/cuentas-a-pagar/imprimir/",
        mantenimiento_salida(ReporteCuentasPagarListView, "print").as_view(),
        name="reporte_cuentas_pagar_print",
    ),
    path(
        "reportes/cuentas-a-pagar/exportar.xlsx",
        mantenimiento_salida(ReporteCuentasPagarListView, "xlsx").as_view(),
        name="reporte_cuentas_pagar_export_xlsx",
    ),
    path(
        "reportes/cuentas-a-pagar/exportar.pdf",
        mantenimiento_salida(ReporteCuentasPagarListView, "pdf").as_view(),
        name="reporte_cuentas_pagar_export_pdf",
    ),
]

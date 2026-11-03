from django.urls import path

from core.mantenimiento import mantenimiento_salida
from ventas.views import (
    AgregarProductoView,
    BuscarClientesView,
    BuscarProductosView,
    CancelarVentaView,
    ConfirmarVentaView,
    FacturaView,
    LineaVentaView,
    PuntoVentaView,
    TicketView,
    TimbradoCreateView,
    TimbradoDeleteView,
    TimbradoListView,
    TimbradoUpdateView,
)

urlpatterns = [
    path("timbrados/", TimbradoListView.as_view(), name="timbrado_list"),
    path(
        "timbrados/imprimir/",
        mantenimiento_salida(TimbradoListView, "print").as_view(),
        name="timbrado_print",
    ),
    path(
        "timbrados/exportar.xlsx",
        mantenimiento_salida(TimbradoListView, "xlsx").as_view(),
        name="timbrado_export_xlsx",
    ),
    path(
        "timbrados/exportar.pdf",
        mantenimiento_salida(TimbradoListView, "pdf").as_view(),
        name="timbrado_export_pdf",
    ),
    path("timbrados/nueva/", TimbradoCreateView.as_view(), name="timbrado_create"),
    path("timbrados/<int:pk>/", TimbradoUpdateView.as_view(), name="timbrado_update"),
    path(
        "timbrados/<int:pk>/eliminar/",
        TimbradoDeleteView.as_view(),
        name="timbrado_delete",
    ),
    path("punto-de-venta/", PuntoVentaView.as_view(), name="punto_de_venta"),
    path(
        "punto-de-venta/buscar/",
        BuscarProductosView.as_view(),
        name="punto_de_venta_buscar",
    ),
    path(
        "punto-de-venta/clientes/",
        BuscarClientesView.as_view(),
        name="punto_de_venta_clientes",
    ),
    path(
        "punto-de-venta/agregar/",
        AgregarProductoView.as_view(),
        name="punto_de_venta_agregar",
    ),
    path(
        "punto-de-venta/lineas/<int:pk>/",
        LineaVentaView.as_view(),
        name="punto_de_venta_linea",
    ),
    path(
        "punto-de-venta/confirmar/",
        ConfirmarVentaView.as_view(),
        name="punto_de_venta_confirmar",
    ),
    path(
        "punto-de-venta/cancelar/",
        CancelarVentaView.as_view(),
        name="punto_de_venta_cancelar",
    ),
    path("<int:pk>/ticket/", TicketView.as_view(), name="venta_ticket"),
    path("<int:pk>/factura/", FacturaView.as_view(), name="venta_factura"),
]

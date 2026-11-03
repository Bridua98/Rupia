from django.urls import path

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
)

urlpatterns = [
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

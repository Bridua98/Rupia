from django.urls import path

from core.mantenimiento import mantenimiento_salida
from ventas.views import (
    AgregarProductoView,
    AnularVentaView,
    BuscarClientesView,
    BuscarProductosView,
    CancelarVentaView,
    ConfirmarVentaView,
    ElegirMaquinaView,
    FacturaView,
    LineaVentaView,
    MaquinaCreateView,
    MaquinaDeleteView,
    MaquinaListView,
    MaquinaUpdateView,
    PuntoVentaView,
    TicketView,
    TimbradoCreateView,
    TimbradoDeleteView,
    TimbradoListView,
    TimbradoUpdateView,
    ValidarNumeroView,
    VentaListView,
)

urlpatterns = [
    path("", VentaListView.as_view(), name="venta_list"),
    path(
        "imprimir/",
        mantenimiento_salida(VentaListView, "print").as_view(),
        name="venta_print",
    ),
    path(
        "exportar.xlsx",
        mantenimiento_salida(VentaListView, "xlsx").as_view(),
        name="venta_export_xlsx",
    ),
    path(
        "exportar.pdf",
        mantenimiento_salida(VentaListView, "pdf").as_view(),
        name="venta_export_pdf",
    ),
    path("<int:pk>/anular/", AnularVentaView.as_view(), name="venta_anular"),
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
    path("maquinas/", MaquinaListView.as_view(), name="maquina_list"),
    path(
        "maquinas/imprimir/",
        mantenimiento_salida(MaquinaListView, "print").as_view(),
        name="maquina_print",
    ),
    path(
        "maquinas/exportar.xlsx",
        mantenimiento_salida(MaquinaListView, "xlsx").as_view(),
        name="maquina_export_xlsx",
    ),
    path(
        "maquinas/exportar.pdf",
        mantenimiento_salida(MaquinaListView, "pdf").as_view(),
        name="maquina_export_pdf",
    ),
    path("maquinas/nueva/", MaquinaCreateView.as_view(), name="maquina_create"),
    path("maquinas/<int:pk>/", MaquinaUpdateView.as_view(), name="maquina_update"),
    path(
        "maquinas/<int:pk>/eliminar/",
        MaquinaDeleteView.as_view(),
        name="maquina_delete",
    ),
    path("punto-de-venta/", PuntoVentaView.as_view(), name="punto_de_venta"),
    path(
        "punto-de-venta/maquina/",
        ElegirMaquinaView.as_view(),
        name="punto_de_venta_maquina",
    ),
    path(
        "punto-de-venta/buscar/",
        BuscarProductosView.as_view(),
        name="punto_de_venta_buscar",
    ),
    path(
        "punto-de-venta/numero/",
        ValidarNumeroView.as_view(),
        name="punto_de_venta_numero",
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

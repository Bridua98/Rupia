from django.urls import path

from core.mantenimiento import mantenimiento_salida
from mesas import comandas_views
from mesas.views import (
    MesaCreateView,
    MesaDeleteView,
    MesaListView,
    MesaUpdateView,
    SectorCreateView,
    SectorDeleteView,
    SectorItemCreateView,
    SectorItemDeleteView,
    SectorItemListView,
    SectorItemUpdateView,
    SectorListView,
    SectorUpdateView,
)


def _mantenimiento(prefijo, nombre, listado, alta, edicion, baja):
    return [
        path(f"{prefijo}", listado.as_view(), name=f"{nombre}_list"),
        path(
            f"{prefijo}imprimir/",
            mantenimiento_salida(listado, "print").as_view(),
            name=f"{nombre}_print",
        ),
        path(
            f"{prefijo}exportar.xlsx",
            mantenimiento_salida(listado, "xlsx").as_view(),
            name=f"{nombre}_export_xlsx",
        ),
        path(
            f"{prefijo}exportar.pdf",
            mantenimiento_salida(listado, "pdf").as_view(),
            name=f"{nombre}_export_pdf",
        ),
        path(f"{prefijo}nueva/", alta.as_view(), name=f"{nombre}_create"),
        path(f"{prefijo}<int:pk>/", edicion.as_view(), name=f"{nombre}_update"),
        path(f"{prefijo}<int:pk>/eliminar/", baja.as_view(), name=f"{nombre}_delete"),
    ]


urlpatterns = [
    path("tablero/", comandas_views.TableroView.as_view(), name="mesas_tablero"),
    path("clientes/", comandas_views.BuscarClientesView.as_view(), name="mesas_clientes"),
    path(
        "comandas/abrir/",
        comandas_views.AbrirComandaView.as_view(),
        name="comanda_abrir",
    ),
    path(
        "comandas/<int:pk>/",
        comandas_views.ComandaDetalleView.as_view(),
        name="comanda_detalle",
    ),
    path(
        "comandas/<int:pk>/agregar/",
        comandas_views.AgregarView.as_view(),
        name="comanda_agregar",
    ),
    path(
        "comandas/<int:pk>/enviar/",
        comandas_views.EnviarView.as_view(),
        name="comanda_enviar",
    ),
    path(
        "comandas/<int:pk>/datos/",
        comandas_views.DatosView.as_view(),
        name="comanda_datos",
    ),
    path(
        "comandas/<int:pk>/cuenta/",
        comandas_views.PedirCuentaView.as_view(),
        name="comanda_pedir_cuenta",
    ),
    path(
        "comandas/<int:pk>/precuenta/",
        comandas_views.PrecuentaView.as_view(),
        name="comanda_precuenta",
    ),
    path(
        "comandas/<int:pk>/anular/",
        comandas_views.AnularComandaView.as_view(),
        name="comanda_anular",
    ),
    path(
        "comandas/<int:pk>/descartar/",
        comandas_views.DescartarView.as_view(),
        name="comanda_descartar",
    ),
    path(
        "comandas/lineas/<int:pk>/",
        comandas_views.LineaView.as_view(),
        name="comanda_linea",
    ),
    path(
        "comandas/lineas/<int:pk>/anular/",
        comandas_views.AnularLineaView.as_view(),
        name="comanda_linea_anular",
    ),
    *_mantenimiento(
        "sectores/productos/",
        "sector_item",
        SectorItemListView,
        SectorItemCreateView,
        SectorItemUpdateView,
        SectorItemDeleteView,
    ),
    *_mantenimiento(
        "sectores/",
        "sector",
        SectorListView,
        SectorCreateView,
        SectorUpdateView,
        SectorDeleteView,
    ),
    *_mantenimiento("", "mesa", MesaListView, MesaCreateView, MesaUpdateView, MesaDeleteView),
]

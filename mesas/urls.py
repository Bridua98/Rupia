from django.urls import path

from core.mantenimiento import mantenimiento_salida
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

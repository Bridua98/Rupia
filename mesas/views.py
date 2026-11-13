from django.db.models import Prefetch
from django.http import Http404

from configuracion.ajustes import mesas_habilitadas
from core.mantenimiento import (
    MantenimientoCreateView,
    MantenimientoDeleteView,
    MantenimientoListView,
    MantenimientoUpdateView,
)
from mesas.forms import MesaForm, SectorForm, SectorItemForm
from mesas.models import Mesa, Sector, SectorCategoria, SectorItem
from mesas.tables import MesaTable, SectorItemTable, SectorTable


class ModuloMesasMixin:
    """Con el módulo apagado, las pantallas de mesas no existen."""

    def dispatch(self, request, *args, **kwargs):
        if not mesas_habilitadas():
            raise Http404("El módulo de mesas está apagado.")
        return super().dispatch(request, *args, **kwargs)


class SectorMantenimiento(ModuloMesasMixin):
    model = Sector
    form_class = SectorForm
    table_class = SectorTable
    form_fields_template = "mesas/sector_form_fields.html"
    permiso_formulario = "sectores"
    page_title = "Sectores de preparación"
    eyebrow = "Mesas"
    title = "Sectores de preparación"
    create_label = "Nuevo sector"
    list_hint = "Flechas para moverse. Enter abre el sector."
    search_label = "Buscar"
    search_placeholder = "Buscar por nombre..."
    search_field = "nombre"
    search_fields = ("nombre",)
    selection_param = "sector"
    record_noun = "sector"
    order_by = ("nombre", "pk")
    list_url_name = "sector_list"
    create_url_name = "sector_create"
    update_url_name = "sector_update"
    delete_url_name = "sector_delete"
    print_url_name = "sector_print"
    export_xlsx_url_name = "sector_export_xlsx"
    export_pdf_url_name = "sector_export_pdf"
    export_basename = "sectores"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .prefetch_related(
                Prefetch(
                    "categorias",
                    queryset=SectorCategoria.objects.select_related("categoria"),
                )
            )
        )


class SectorListView(SectorMantenimiento, MantenimientoListView):
    pass


class SectorCreateView(SectorMantenimiento, MantenimientoCreateView):
    list_view_class = SectorListView


class SectorUpdateView(SectorMantenimiento, MantenimientoUpdateView):
    list_view_class = SectorListView


class SectorDeleteView(SectorMantenimiento, MantenimientoDeleteView):
    pass


class SectorItemMantenimiento(ModuloMesasMixin):
    model = SectorItem
    form_class = SectorItemForm
    table_class = SectorItemTable
    permiso_formulario = "sectores"
    page_title = "Productos con otro sector"
    eyebrow = "Mesas"
    title = "Productos con otro sector"
    create_label = "Nuevo producto"
    list_hint = "Productos que no van al sector de su categoría. Enter abre el producto."
    search_label = "Buscar"
    search_placeholder = "Buscar por producto o sector..."
    search_field = "item__descripcion"
    search_fields = ("item__descripcion", "sector__nombre")
    selection_param = "producto"
    record_noun = "producto"
    order_by = ("item__descripcion", "pk")
    list_url_name = "sector_item_list"
    create_url_name = "sector_item_create"
    update_url_name = "sector_item_update"
    delete_url_name = "sector_item_delete"
    print_url_name = "sector_item_print"
    export_xlsx_url_name = "sector_item_export_xlsx"
    export_pdf_url_name = "sector_item_export_pdf"
    export_basename = "productos-por-sector"

    def get_queryset(self):
        return super().get_queryset().select_related("item", "sector")


class SectorItemListView(SectorItemMantenimiento, MantenimientoListView):
    pass


class SectorItemCreateView(SectorItemMantenimiento, MantenimientoCreateView):
    list_view_class = SectorItemListView


class SectorItemUpdateView(SectorItemMantenimiento, MantenimientoUpdateView):
    list_view_class = SectorItemListView


class SectorItemDeleteView(SectorItemMantenimiento, MantenimientoDeleteView):
    pass


class MesaMantenimiento(ModuloMesasMixin):
    model = Mesa
    form_class = MesaForm
    table_class = MesaTable
    permiso_formulario = "mesas"
    page_title = "Mesas"
    eyebrow = "Mesas"
    title = "Mesas"
    create_label = "Nueva mesa"
    list_hint = "Flechas para moverse. Enter abre la mesa."
    search_label = "Buscar"
    search_placeholder = "Buscar por nombre o zona..."
    search_field = "nombre"
    search_fields = ("nombre", "zona")
    selection_param = "mesa"
    record_noun = "mesa"
    order_by = ("zona", "orden", "nombre", "pk")
    list_url_name = "mesa_list"
    create_url_name = "mesa_create"
    update_url_name = "mesa_update"
    delete_url_name = "mesa_delete"
    print_url_name = "mesa_print"
    export_xlsx_url_name = "mesa_export_xlsx"
    export_pdf_url_name = "mesa_export_pdf"
    export_basename = "mesas"


class MesaListView(MesaMantenimiento, MantenimientoListView):
    pass


class MesaCreateView(MesaMantenimiento, MantenimientoCreateView):
    list_view_class = MesaListView


class MesaUpdateView(MesaMantenimiento, MantenimientoUpdateView):
    list_view_class = MesaListView


class MesaDeleteView(MesaMantenimiento, MantenimientoDeleteView):
    pass

from core.mantenimiento import (
    MantenimientoCreateView,
    MantenimientoDeleteView,
    MantenimientoListView,
    MantenimientoUpdateView,
)
from negocio.forms import UnidadNegocioForm
from negocio.models import UnidadNegocio
from negocio.tables import UnidadNegocioTable


class UnidadNegocioMantenimiento:
    model = UnidadNegocio
    form_class = UnidadNegocioForm
    table_class = UnidadNegocioTable
    permiso_formulario = "unidades_negocio"
    page_title = "Unidades de negocio"
    eyebrow = "Gestión"
    title = "Unidades de negocio"
    create_label = "Nueva unidad de negocio"
    list_hint = "Flechas para moverse. Enter abre la unidad de negocio."
    search_label = "Buscar"
    search_placeholder = "Buscar por descripción o abreviado..."
    search_field = "descripcion"
    search_fields = ("descripcion", "abreviado")
    selection_param = "unidad_negocio"
    record_noun = "unidad de negocio"
    order_by = ("descripcion", "pk")
    list_url_name = "unidad_negocio_list"
    create_url_name = "unidad_negocio_create"
    update_url_name = "unidad_negocio_update"
    delete_url_name = "unidad_negocio_delete"
    print_url_name = "unidad_negocio_print"
    export_xlsx_url_name = "unidad_negocio_export_xlsx"
    export_pdf_url_name = "unidad_negocio_export_pdf"
    export_basename = "unidades-negocio"


class UnidadNegocioListView(UnidadNegocioMantenimiento, MantenimientoListView):
    pass


class UnidadNegocioCreateView(UnidadNegocioMantenimiento, MantenimientoCreateView):
    list_view_class = UnidadNegocioListView


class UnidadNegocioUpdateView(UnidadNegocioMantenimiento, MantenimientoUpdateView):
    list_view_class = UnidadNegocioListView


class UnidadNegocioDeleteView(UnidadNegocioMantenimiento, MantenimientoDeleteView):
    pass

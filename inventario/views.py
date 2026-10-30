from core.mantenimiento import (
    MantenimientoCreateView,
    MantenimientoDeleteView,
    MantenimientoListView,
    MantenimientoUpdateView,
)
from inventario.forms import CategoriaForm, MarcaForm, UnidadForm
from inventario.models import ItemCategoria, Marca, UnidadMedida
from inventario.tables import CategoriaTable, MarcaTable, UnidadTable


class MarcaMantenimiento:
    model = Marca
    form_class = MarcaForm
    table_class = MarcaTable
    page_title = "Marcas"
    eyebrow = "Inventario"
    title = "Marcas"
    create_label = "Nueva marca"
    list_hint = "Flechas para moverse. Enter abre la marca al costado."
    search_label = "Buscar por descripción"
    search_placeholder = "Buscar por descripción..."
    search_field = "descripcion"
    selection_param = "marca"
    record_noun = "marca"
    order_by = ("descripcion", "pk")
    list_url_name = "marca_list"
    create_url_name = "marca_create"
    update_url_name = "marca_update"
    delete_url_name = "marca_delete"
    print_url_name = "marca_print"
    export_xlsx_url_name = "marca_export_xlsx"
    export_pdf_url_name = "marca_export_pdf"
    export_basename = "marcas"


class MarcaListView(MarcaMantenimiento, MantenimientoListView):
    pass


class MarcaCreateView(MarcaMantenimiento, MantenimientoCreateView):
    list_view_class = MarcaListView


class MarcaUpdateView(MarcaMantenimiento, MantenimientoUpdateView):
    list_view_class = MarcaListView


class MarcaDeleteView(MarcaMantenimiento, MantenimientoDeleteView):
    pass


class CategoriaMantenimiento:
    model = ItemCategoria
    form_class = CategoriaForm
    table_class = CategoriaTable
    page_title = "Categorías"
    eyebrow = "Inventario"
    title = "Categorías"
    create_label = "Nueva categoría"
    list_hint = "Flechas para moverse. Enter abre la categoría al costado."
    search_label = "Buscar por descripción"
    search_placeholder = "Buscar por descripción..."
    search_field = "descripcion"
    selection_param = "categoria"
    record_noun = "categoría"
    order_by = ("descripcion", "pk")
    list_url_name = "categoria_list"
    create_url_name = "categoria_create"
    update_url_name = "categoria_update"
    delete_url_name = "categoria_delete"
    print_url_name = "categoria_print"
    export_xlsx_url_name = "categoria_export_xlsx"
    export_pdf_url_name = "categoria_export_pdf"
    export_basename = "categorias"


class CategoriaListView(CategoriaMantenimiento, MantenimientoListView):
    pass


class CategoriaCreateView(CategoriaMantenimiento, MantenimientoCreateView):
    list_view_class = CategoriaListView


class CategoriaUpdateView(CategoriaMantenimiento, MantenimientoUpdateView):
    list_view_class = CategoriaListView


class CategoriaDeleteView(CategoriaMantenimiento, MantenimientoDeleteView):
    pass


class UnidadMantenimiento:
    model = UnidadMedida
    form_class = UnidadForm
    table_class = UnidadTable
    page_title = "Unidades de medida"
    eyebrow = "Inventario"
    title = "Unidades de medida"
    create_label = "Nueva unidad"
    list_hint = "Flechas para moverse. Enter abre la unidad al costado."
    search_label = "Buscar por descripción"
    search_placeholder = "Buscar por descripción..."
    search_field = "descripcion"
    selection_param = "unidad"
    record_noun = "unidad"
    order_by = ("descripcion", "pk")
    list_url_name = "unidad_list"
    create_url_name = "unidad_create"
    update_url_name = "unidad_update"
    delete_url_name = "unidad_delete"
    print_url_name = "unidad_print"
    export_xlsx_url_name = "unidad_export_xlsx"
    export_pdf_url_name = "unidad_export_pdf"
    export_basename = "unidades"


class UnidadListView(UnidadMantenimiento, MantenimientoListView):
    pass


class UnidadCreateView(UnidadMantenimiento, MantenimientoCreateView):
    list_view_class = UnidadListView


class UnidadUpdateView(UnidadMantenimiento, MantenimientoUpdateView):
    list_view_class = UnidadListView


class UnidadDeleteView(UnidadMantenimiento, MantenimientoDeleteView):
    pass

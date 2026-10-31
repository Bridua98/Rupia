from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, Http404
from django.views import View

from core.mantenimiento import (
    MantenimientoCreateView,
    MantenimientoDeleteView,
    MantenimientoListView,
    MantenimientoUpdateView,
)
from inventario.forms import CategoriaForm, ItemForm, MarcaForm, UnidadForm
from inventario.imagenes import resolver_imagen
from inventario.models import Item, ItemCategoria, Marca, TasaIva, TipoItem, UnidadMedida
from inventario.tables import CategoriaTable, ItemTable, MarcaTable, UnidadTable


class MarcaMantenimiento:
    model = Marca
    form_class = MarcaForm
    table_class = MarcaTable
    page_title = "Marcas"
    eyebrow = "Inventario"
    title = "Marcas"
    create_label = "Nueva marca"
    list_hint = "Flechas para moverse. Enter abre la marca."
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
    list_hint = "Flechas para moverse. Enter abre la categoría."
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
    list_hint = "Flechas para moverse. Enter abre la unidad."
    search_label = "Buscar"
    search_placeholder = "Buscar por descripción o símbolo..."
    search_field = "descripcion"
    search_fields = ("descripcion", "simbolo")
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


class ItemMantenimiento:
    model = Item
    form_class = ItemForm
    table_class = ItemTable
    page_title = "Ítems"
    eyebrow = "Inventario"
    title = "Ítems"
    create_label = "Nuevo ítem"
    list_hint = "Flechas para moverse. Enter abre el ítem."
    search_label = "Buscar"
    search_placeholder = "Buscar por descripción, código, marca o categoría..."
    search_field = "descripcion"
    search_fields = (
        "descripcion",
        "codigo_barra",
        "marca__descripcion",
        "categoria__descripcion",
        "unidad_medida__descripcion",
        "unidad_medida__simbolo",
    )
    filters = (
        {"name": "tipo", "label": "Tipo", "kind": "choice", "choices": TipoItem.choices},
        {
            "name": "tasa_iva",
            "label": "Tasa IVA",
            "kind": "choice",
            "choices": [(str(valor), etiqueta) for valor, etiqueta in TasaIva.choices],
        },
        {
            "name": "marca",
            "label": "Marca",
            "kind": "fk",
            "queryset": lambda: Marca.objects.order_by("descripcion"),
        },
        {
            "name": "categoria",
            "label": "Categoría",
            "kind": "fk",
            "queryset": lambda: ItemCategoria.objects.order_by("descripcion"),
        },
        {
            "name": "unidad_medida",
            "label": "Unidad",
            "kind": "fk",
            "queryset": lambda: UnidadMedida.objects.order_by("descripcion"),
        },
        {"name": "activo", "label": "Activo", "kind": "bool"},
    )
    selection_param = "item"
    record_noun = "ítem"
    order_by = ("descripcion", "pk")
    list_url_name = "item_list"
    create_url_name = "item_create"
    update_url_name = "item_update"
    delete_url_name = "item_delete"
    print_url_name = "item_print"
    export_xlsx_url_name = "item_export_xlsx"
    export_pdf_url_name = "item_export_pdf"
    export_basename = "items"


class ItemListView(ItemMantenimiento, MantenimientoListView):
    pass


class ItemCreateView(ItemMantenimiento, MantenimientoCreateView):
    list_view_class = ItemListView


class ItemUpdateView(ItemMantenimiento, MantenimientoUpdateView):
    list_view_class = ItemListView


class ItemDeleteView(ItemMantenimiento, MantenimientoDeleteView):
    pass


class ItemImagenView(LoginRequiredMixin, View):
    def get(self, request, nombre):
        destino = resolver_imagen(nombre)
        if destino is None:
            raise Http404
        return FileResponse(destino.open("rb"))

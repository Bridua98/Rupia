from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from django_tables2 import SingleTableView

from core.listado import (
    apply_filters,
    apply_search,
    filter_options,
    filter_specs_for,
    filter_values,
)
from core.mantenimiento import (
    MantenimientoCreateView,
    MantenimientoDeleteView,
    MantenimientoListView,
    MantenimientoUpdateView,
)
from inventario.forms import (
    CategoriaForm,
    ItemForm,
    MarcaForm,
    PrecioAjusteForm,
    UnidadForm,
    unidades_formset,
)
from inventario.imagenes import resolver_imagen
from inventario.models import (
    Item,
    ItemCategoria,
    ItemPrecioHistorial,
    Marca,
    OrigenPrecio,
    TasaIva,
    TipoItem,
    UnidadMedida,
)
from inventario.precios import aplicar_ajuste, previsualizar
from inventario.tables import (
    CategoriaTable,
    ItemTable,
    MarcaTable,
    PrecioHistorialTable,
    PrecioTable,
    UnidadTable,
)
from negocio.models import UnidadNegocio


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
        "unidad_negocio__descripcion",
        "unidad_negocio__abreviado",
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
        {
            "name": "unidad_negocio",
            "label": "Unidad de negocio",
            "kind": "fk",
            "queryset": lambda: UnidadNegocio.objects.order_by("descripcion"),
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


class ItemWriteMixin:
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["usuario"] = self.request.user
        return kwargs

    def _unidades_formset(self, form, data=None):
        unidad_base = None
        if getattr(form, "is_bound", False) and form.is_valid():
            unidad_base = form.cleaned_data.get("unidad_medida")
        elif getattr(form.instance, "unidad_medida_id", None):
            unidad_base = form.instance.unidad_medida
        return unidades_formset(item=form.instance, data=data, unidad_base=unidad_base)

    def form_valid(self, form):
        formset = None
        if "unidades-TOTAL_FORMS" in self.request.POST:
            formset = self._unidades_formset(form, data=self.request.POST)
            self.unidades_formset = formset
            if not formset.is_valid():
                return self.form_invalid(form)
        with transaction.atomic():
            self.object = form.save()
            if formset is not None:
                formset.instance = self.object
                formset.save()
        if self.request.POST.get("accion") == "seguir":
            return redirect(self.create_url_name)
        params = {}
        query = self.request.POST.get("q", "").strip()
        if query:
            params["q"] = query
        if self.request.POST.get("desde") == "listado":
            for name, value in filter_values(self.request, filter_specs_for(self)).items():
                params[name] = value
        destino = reverse(self.list_url_name)
        if params:
            destino = f"{destino}?{urlencode(params)}"
        return redirect(destino)

    def form_invalid(self, form):
        if not hasattr(self, "unidades_formset"):
            data = self.request.POST if "unidades-TOTAL_FORMS" in self.request.POST else None
            self.unidades_formset = self._unidades_formset(form, data=data)
        if self.request.POST.get("desde") != "listado":
            return super().form_invalid(form)
        listado = self.list_view_class()
        listado.setup(self.request)
        listado.panel_form_override = form
        listado.unidades_formset_override = self.unidades_formset
        listado.force_nueva = not getattr(form.instance, "pk", None)
        if getattr(form.instance, "pk", None):
            listado.selected_override = form.instance.pk
        return listado.get(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["unidades_formset"] = getattr(self, "unidades_formset", None) or unidades_formset(
            item=context.get("object") or getattr(self, "object", None),
            unidad_base=getattr(
                context.get("object") or getattr(self, "object", None),
                "unidad_medida",
                None,
            ),
        )
        return context


class ItemListView(ItemMantenimiento, MantenimientoListView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        panel_form = context.get("panel_form")
        if panel_form is not None:
            context["unidades_formset"] = getattr(
                self, "unidades_formset_override", None
            ) or unidades_formset(
                item=panel_form.instance,
                unidad_base=(panel_form.instance.unidad_medida if panel_form.instance.pk else None),
            )
        return context


class ItemCreateView(ItemMantenimiento, ItemWriteMixin, MantenimientoCreateView):
    list_view_class = ItemListView


class ItemUpdateView(ItemMantenimiento, ItemWriteMixin, MantenimientoUpdateView):
    list_view_class = ItemListView


class ItemDeleteView(ItemMantenimiento, MantenimientoDeleteView):
    pass


class ItemImagenView(LoginRequiredMixin, View):
    def get(self, request, nombre):
        destino = resolver_imagen(nombre)
        if destino is None:
            raise Http404
        return FileResponse(destino.open("rb"))


class PrecioListView(LoginRequiredMixin, SingleTableView):
    template_name = "inventario/precios.html"
    table_class = PrecioTable
    model = Item
    per_page = 10
    page_title = "Precios"
    eyebrow = "Inventario"
    title = "Precios"
    search_label = "Buscar"
    search_placeholder = "Buscar por descripción, código, marca o categoría..."
    search_fields = (
        "descripcion",
        "codigo_barra",
        "marca__descripcion",
        "categoria__descripcion",
    )
    filters = (
        {"name": "tipo", "label": "Tipo", "kind": "choice", "choices": TipoItem.choices},
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
        {"name": "activo", "label": "Activo", "kind": "bool"},
    )
    list_hint = (
        "El porcentaje se aplica sobre el precio, o sobre el último costo si el ítem está marcado."
    )

    def query(self):
        if "q" in self.request.GET:
            return self.request.GET.get("q", "").strip()
        return self.request.POST.get("q", "").strip()

    def _filter_values(self):
        values = filter_values(self.request, filter_specs_for(self))
        if "activo" not in self.request.GET and self.request.GET.get("filtros") != "1":
            values["activo"] = "1"
        return values

    def get_queryset(self):
        queryset = Item.objects.select_related("marca", "categoria").order_by("descripcion", "pk")
        queryset = apply_search(queryset, self.query(), self.search_fields)
        return apply_filters(queryset, self._filter_values(), filter_specs_for(self))

    def get_table_pagination(self, table):
        return {"per_page": self.per_page}

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.ajuste_form = PrecioAjusteForm()
        self.previews = {}
        self.seleccionados = set()
        self.todos_filtrados = False

    def get(self, request, *args, **kwargs):
        self.ajuste_form = PrecioAjusteForm()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.ajuste_form = PrecioAjusteForm(request.POST)
        self.seleccionados = {int(pk) for pk in request.POST.getlist("item") if str(pk).isdigit()}
        self.todos_filtrados = bool(request.POST.get("todos_filtrados"))
        if not self.ajuste_form.is_valid():
            return super().get(request, *args, **kwargs)
        porcentaje = self.ajuste_form.cleaned_data["porcentaje"]
        self.todos_filtrados = bool(self.ajuste_form.cleaned_data.get("todos_filtrados"))
        if request.POST.get("accion") == "aplicar":
            destino = self._objetivo()
            if destino is None:
                self.ajuste_form.add_error(None, "Elegí al menos un ítem.")
                return super().get(request, *args, **kwargs)
            resultado = aplicar_ajuste(destino, porcentaje, request.user)
            messages.success(request, self._mensaje(resultado))
            return redirect(request.get_full_path())
        destino = self._objetivo(permitir_pagina=True)
        self.previews = previsualizar(destino, porcentaje)
        return super().get(request, *args, **kwargs)

    def _objetivo(self, permitir_pagina=False):
        queryset = self.get_queryset()
        if self.todos_filtrados:
            return queryset
        if self.seleccionados:
            return queryset.filter(pk__in=self.seleccionados)
        if permitir_pagina:
            paginator = Paginator(queryset, self.per_page)
            return paginator.get_page(self.request.GET.get("page") or 1).object_list
        return None

    def _mensaje(self, resultado):
        if resultado.cambiados == 1:
            texto = "Se actualizó 1 precio."
        else:
            texto = f"Se actualizaron {resultado.cambiados} precios."
        if resultado.omitidos == 1:
            return f"{texto} Se omitió 1."
        if resultado.omitidos:
            return f"{texto} Se omitieron {resultado.omitidos}."
        return texto

    def get_table_kwargs(self):
        return {
            "row_attrs": {
                "data-precio": lambda record: (
                    str(record.precio) if record.precio is not None else ""
                ),
                "data-costo": lambda record: (
                    str(record.ultimo_costo) if record.ultimo_costo is not None else ""
                ),
                "data-segun-costo": lambda record: "1" if record.precio_segun_costo else "0",
            }
        }

    def get_table(self, **kwargs):
        table = super().get_table(**kwargs)
        for row in table.paginated_rows:
            item = row.record
            item.seleccionado = self.todos_filtrados or item.pk in self.seleccionados
            item.precio_preview = self.previews.get(item.pk)
        return table

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        specs = filter_specs_for(self)
        values = self._filter_values()
        rows = []
        for spec in specs:
            name = spec["name"]
            rows.append(
                {
                    "name": name,
                    "label": spec["label"],
                    "kind": spec.get("kind", "choice"),
                    "value": values.get(name, ""),
                    "options": filter_options(spec),
                }
            )
        explicit = filter_values(self.request, specs)
        active = sum(1 for row in rows if row["value"])
        context.update(
            {
                "page_title": self.page_title,
                "eyebrow": self.eyebrow,
                "title": self.title,
                "back_url": reverse("home"),
                "list_url": reverse("precio_list"),
                "historial_url": reverse("precio_historial"),
                "record_count": self.get_queryset().count(),
                "list_hint": self.list_hint,
                "query": self.query(),
                "search_label": self.search_label,
                "search_placeholder": self.search_placeholder,
                "list_filters": rows,
                "filters_open": bool(explicit) or self.request.GET.get("filtros") == "1",
                "active_filter_count": active,
                "ajuste_form": self.ajuste_form,
            }
        )
        return context


class PrecioHistorialMantenimiento:
    model = ItemPrecioHistorial
    table_class = PrecioHistorialTable
    page_title = "Historial de precios"
    eyebrow = "Inventario"
    title = "Historial de precios"
    create_label = ""
    show_create = False
    list_hint = "Cada cambio de precio queda registrado con usuario y fecha."
    search_label = "Buscar"
    search_placeholder = "Buscar por ítem o usuario..."
    search_field = "item__descripcion"
    search_fields = ("item__descripcion", "usuario__username")
    filters = (
        {
            "name": "origen",
            "label": "Origen",
            "kind": "choice",
            "choices": OrigenPrecio.choices,
        },
    )
    record_noun = "cambio"
    order_by = ("-fecha", "-pk")
    list_url_name = "precio_historial"
    create_url_name = ""
    back_url_name = "precio_list"
    print_url_name = "precio_historial_print"
    export_xlsx_url_name = "precio_historial_export_xlsx"
    export_pdf_url_name = "precio_historial_export_pdf"
    export_basename = "historial-precios"

    def creating(self):
        return False

    def panel_pk(self):
        return None

    def get_table_kwargs(self):
        return {}

    def get_queryset(self):
        return super().get_queryset().select_related("item", "usuario")


class PrecioHistorialListView(PrecioHistorialMantenimiento, MantenimientoListView):
    pass

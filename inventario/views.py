from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models.deletion import RestrictedError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, UpdateView
from django_tables2 import SingleTableView

from inventario.forms import MarcaForm
from inventario.models import Marca
from inventario.tables import MarcaTable


def neighbors(marca):
    ids = list(Marca.objects.order_by("descripcion", "pk").values_list("pk", flat=True))
    index = ids.index(marca.pk)
    prev_id = ids[index - 1] if index > 0 else None
    next_id = ids[index + 1] if index + 1 < len(ids) else None
    return {
        "position": index + 1,
        "total": len(ids),
        "prev_url": reverse("marca_update", args=[prev_id]) if prev_id else "",
        "next_url": reverse("marca_update", args=[next_id]) if next_id else "",
    }


class MarcaListView(LoginRequiredMixin, SingleTableView):
    model = Marca
    table_class = MarcaTable
    template_name = "inventario/marca_list.html"
    table_pagination = False
    panel_form_override = None
    force_nueva = False
    selected_override = None

    def query(self):
        if "q" in self.request.GET:
            return self.request.GET.get("q", "").strip()
        return self.request.POST.get("q", "").strip()

    def list_query(self, **extra):
        params = {}
        q = self.query()
        if q:
            params["q"] = q
        for key, value in extra.items():
            if value is not None and value != "":
                params[key] = value
        base = reverse("marca_list")
        if not params:
            return base
        return f"{base}?{urlencode(params)}"

    def get_queryset(self):
        qs = Marca.objects.order_by("descripcion", "pk")
        q = self.query()
        if q:
            qs = qs.filter(descripcion__icontains=q)
        return qs

    def creating(self):
        return self.force_nueva or self.request.GET.get("nueva") == "1"

    def panel_pk(self):
        if self.creating():
            return None
        if self.selected_override:
            return self.selected_override
        raw = self.request.GET.get("marca", "")
        if not raw.isdigit():
            return None
        pk = int(raw)
        if self.get_queryset().filter(pk=pk).exists():
            return pk
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        nueva = self.creating()
        selected = self.panel_pk()
        if self.panel_form_override is not None:
            panel_form = self.panel_form_override
        elif nueva:
            panel_form = MarcaForm()
        elif selected:
            panel_form = MarcaForm(instance=Marca.objects.get(pk=selected))
        else:
            panel_form = None
        if panel_form is not None and self.panel_form_override is None:
            widget = panel_form.fields["descripcion"].widget
            widget.attrs = {k: v for k, v in widget.attrs.items() if k != "autofocus"}
        panel_object = None
        if panel_form is not None and getattr(panel_form.instance, "pk", None):
            panel_object = panel_form.instance
        context.update(
            {
                "page_title": "Marcas",
                "eyebrow": "Inventario",
                "title": "Marcas",
                "back_url": reverse("home"),
                "list_url": reverse("marca_list"),
                "create_url": self.list_query(nueva=1),
                "create_label": "Nueva marca",
                "record_count": self.get_queryset().count(),
                "list_hint": "Flechas para moverse. Enter abre la marca al costado.",
                "query": self.query(),
                "search_label": "Buscar por descripción",
                "search_placeholder": "Buscar por descripción",
                "detail_open": panel_form is not None,
                "panel_form": panel_form,
                "panel_object": panel_object,
                "panel_action": reverse("marca_update", args=[panel_object.pk])
                if panel_object
                else reverse("marca_create"),
                "close_url": self.list_query(),
                "ficha_url": (
                    reverse("marca_update", args=[panel_object.pk]) if panel_object else ""
                ),
            }
        )
        return context

    def selected_pk(self):
        if self.creating():
            return None
        opened = self.panel_pk()
        if opened:
            return opened
        ids = list(self.get_queryset().values_list("pk", flat=True))
        return ids[0] if ids else None

    def get_table_kwargs(self):
        selected = self.selected_pk()
        return {
            "row_attrs": {
                "data-id": lambda record: record.pk,
                "data-href": lambda record: self.list_query(marca=record.pk),
                "aria-selected": lambda record: "true" if record.pk == selected else "false",
                "tabindex": lambda record: "0" if record.pk == selected else "-1",
            }
        }


class MarcaWriteMixin:
    model = Marca
    form_class = MarcaForm
    template_name = "inventario/marca_form.html"

    def form_valid(self, form):
        self.object = form.save()
        if self.request.POST.get("accion") == "seguir":
            return redirect("marca_create")
        params = {"marca": self.object.pk}
        q = self.request.POST.get("q", "").strip()
        if q:
            params["q"] = q
        return redirect(f"{reverse('marca_list')}?{urlencode(params)}")

    def form_invalid(self, form):
        if self.request.POST.get("desde") != "listado":
            return super().form_invalid(form)
        listado = MarcaListView()
        listado.setup(self.request)
        listado.panel_form_override = form
        listado.force_nueva = not getattr(form.instance, "pk", None)
        if getattr(form.instance, "pk", None):
            listado.selected_override = form.instance.pk
        return listado.get(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        marca = context.get("object")
        if marca is not None:
            context.update(neighbors(marca))
            context["list_url"] = f"{reverse('marca_list')}?marca={marca.pk}"
        else:
            context["list_url"] = reverse("marca_list")
            context["prev_url"] = ""
            context["next_url"] = ""
        return context


class MarcaCreateView(LoginRequiredMixin, MarcaWriteMixin, CreateView):
    pass


class MarcaUpdateView(LoginRequiredMixin, MarcaWriteMixin, UpdateView):
    pass


class MarcaDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        marca = get_object_or_404(Marca, pk=pk)
        descripcion = marca.descripcion
        try:
            marca.delete()
        except RestrictedError:
            messages.error(request, f"{descripcion} está en uso y no se puede eliminar.")
            return redirect("marca_update", pk=pk)
        return redirect("marca_list")

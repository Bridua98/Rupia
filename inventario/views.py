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

    def get_queryset(self):
        return Marca.objects.order_by("descripcion", "pk")

    def selected_pk(self):
        raw = self.request.GET.get("marca", "")
        ids = list(self.get_queryset().values_list("pk", flat=True))
        if raw.isdigit() and int(raw) in ids:
            return int(raw)
        return ids[0] if ids else None

    def get_table_kwargs(self):
        selected = self.selected_pk()
        return {
            "row_attrs": {
                "data-id": lambda record: record.pk,
                "data-href": lambda record: reverse("marca_update", args=[record.pk]),
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
        return redirect(f"{reverse('marca_list')}?marca={self.object.pk}")

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

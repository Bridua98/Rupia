from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.urls import reverse
from django.views import View

from configuracion.permisos import PermisoRequeridoMixin
from core.combo import ComboChoiceField, ComboWidget

SELECTORES = {}


def registrar(clave, *, queryset, form=None, search_fields, create_label="", formulario):
    SELECTORES[clave] = {
        "queryset": queryset,
        "form": form,
        "search_fields": search_fields,
        "create_label": create_label,
        "formulario": formulario,
    }


def _spec(clave):
    try:
        return SELECTORES[clave]
    except KeyError as exc:
        raise Http404 from exc


class SelectorWidget(ComboWidget):
    template_name = "core/selector_alta.html"
    is_selector = True

    def __init__(self, *, clave, label, create_label, attrs=None):
        self.clave = clave
        self.create_label = create_label
        super().__init__(label=label, attrs=attrs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        spec = _spec(self.clave)
        create_form = spec["form"](prefix=self.clave)
        for field in create_form.fields.values():
            field.widget.attrs.pop("autofocus", None)
        widget = context["widget"]
        widget["clave"] = self.clave
        widget["create_label"] = self.create_label
        widget["search_url"] = reverse("selector_search", args=[self.clave])
        widget["create_url"] = reverse("selector_create", args=[self.clave])
        widget["create_form"] = create_form
        return context


class SelectorAlta(ComboChoiceField):
    """Foráneo con búsqueda y alta del registro relacionado."""

    def __init__(self, *, clave, label, required_message, required=True):
        spec = _spec(clave)
        super().__init__(
            queryset=spec["queryset"](),
            clave=clave,
            label=label,
            required_message=required_message,
            required=required,
            widget=SelectorWidget(
                clave=clave,
                label=label,
                create_label=spec["create_label"],
            ),
        )


class SelectorSearchView(LoginRequiredMixin, PermisoRequeridoMixin, View):
    permiso_accion = "ver"

    def get_permiso_formulario(self):
        return _spec(self.kwargs["clave"])["formulario"]

    def get(self, request, clave):
        spec = _spec(clave)
        queryset = spec["queryset"]()
        query = request.GET.get("q", "").strip()
        if query:
            filtro = Q()
            for field in spec["search_fields"]:
                filtro |= Q(**{f"{field}__icontains": query})
            queryset = queryset.filter(filtro)
        results = [{"id": obj.pk, "label": str(obj)} for obj in queryset.distinct()[:20]]
        return JsonResponse({"results": results, "resultados": results})


class SelectorCreateView(LoginRequiredMixin, PermisoRequeridoMixin, View):
    permiso_accion = "alta"

    def get_permiso_formulario(self):
        return _spec(self.kwargs["clave"])["formulario"]

    def post(self, request, clave):
        spec = _spec(clave)
        if spec.get("form") is None:
            raise Http404
        form = spec["form"](request.POST, prefix=clave)
        if not form.is_valid():
            errors = {}
            for name, messages in form.errors.items():
                key = "__all__" if name == "__all__" else form[name].html_name
                errors[key] = list(messages)
            return JsonResponse({"errors": errors}, status=400)
        obj = form.save()
        return JsonResponse({"id": obj.pk, "label": str(obj)})

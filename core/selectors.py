from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.views import View

SELECTORES = {}


def registrar(clave, *, queryset, form, search_fields, create_label):
    SELECTORES[clave] = {
        "queryset": queryset,
        "form": form,
        "search_fields": search_fields,
        "create_label": create_label,
    }


def _spec(clave):
    try:
        return SELECTORES[clave]
    except KeyError as exc:
        raise Http404 from exc


class SelectorWidget(forms.Widget):
    template_name = "core/selector_alta.html"
    is_selector = True

    def __init__(self, *, clave, label, create_label, attrs=None):
        self.clave = clave
        self.field_label = label
        self.create_label = create_label
        super().__init__(attrs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        spec = _spec(self.clave)
        selected = ""
        if value not in (None, ""):
            obj = spec["queryset"]().filter(pk=value).first()
            selected = str(obj) if obj else ""
        create_form = spec["form"](prefix=self.clave)
        for field in create_form.fields.values():
            field.widget.attrs.pop("autofocus", None)
        widget = context["widget"]
        widget["clave"] = self.clave
        widget["field_label"] = self.field_label
        widget["create_label"] = self.create_label
        widget["selected_label"] = selected
        widget["search_url"] = reverse("selector_search", args=[self.clave])
        widget["create_url"] = reverse("selector_create", args=[self.clave])
        widget["create_form"] = create_form
        return context

    def render(self, name, value, attrs=None, renderer=None):
        context = self.get_context(name, value, attrs)
        return render_to_string(self.template_name, context)


class SelectorAlta(forms.ModelChoiceField):
    """Foráneo con búsqueda y alta del registro relacionado."""

    def __init__(self, *, clave, label, required_message):
        spec = _spec(clave)
        super().__init__(
            queryset=spec["queryset"](),
            label=label,
            empty_label=None,
            error_messages={"required": required_message},
            widget=SelectorWidget(
                clave=clave,
                label=label,
                create_label=spec["create_label"],
            ),
        )


class SelectorSearchView(LoginRequiredMixin, View):
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
        return JsonResponse({"results": results})


class SelectorCreateView(LoginRequiredMixin, View):
    def post(self, request, clave):
        spec = _spec(clave)
        form = spec["form"](request.POST, prefix=clave)
        if not form.is_valid():
            errors = {}
            for name, messages in form.errors.items():
                key = "__all__" if name == "__all__" else form[name].html_name
                errors[key] = list(messages)
            return JsonResponse({"errors": errors}, status=400)
        obj = form.save()
        return JsonResponse({"id": obj.pk, "label": str(obj)})

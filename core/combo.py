import json

from django import forms
from django.forms.models import ModelChoiceIterator
from django.template.loader import render_to_string
from django.urls import reverse

MENSAJE_LISTA = "Elegí una opción de la lista."


def combo_context(
    *,
    name,
    value="",
    label="",
    selected_label="",
    search_url="",
    options=None,
    required=False,
    required_message="",
    submit=False,
    placeholder="Buscar…",
    attrs=None,
    hide_label=False,
    variant="",
    nueva_url="",
    nueva_ayuda="",
    alta_url="",
    padron_label="",
):
    attrs = dict(attrs or {})
    options = list(options or [])
    ident = attrs.get("id") or f"id_{name}"
    attrs["id"] = ident
    payload = {
        "name": name,
        "value": "" if value in (None, "") else value,
        "field_label": label,
        "selected_label": selected_label or "",
        "search_url": search_url,
        "options_json": json.dumps(options, ensure_ascii=False) if options else "",
        "required": required,
        "required_message": required_message or MENSAJE_LISTA,
        "submit": submit,
        "placeholder": placeholder,
        "attrs": attrs,
        "hide_label": hide_label,
        "variant": variant,
        "nueva_url": nueva_url,
        "nueva_ayuda": nueva_ayuda,
        "alta_url": alta_url,
        "padron_label": padron_label,
    }
    return payload


def combo_options(objects):
    return [{"id": obj.pk, "label": str(obj)} for obj in objects]


class ComboWidget(forms.Widget):
    template_name = "core/combo.html"
    is_combo = True
    is_selector = True

    def __init__(
        self,
        attrs=None,
        *,
        label="",
        search_url="",
        clave="",
        options=None,
        required_message="",
        submit=False,
        placeholder="Buscar…",
        hide_label=False,
        variant="",
    ):
        self.field_label = label
        self.search_url = search_url
        self.clave = clave
        self.options = list(options or [])
        self.required_message = required_message or MENSAJE_LISTA
        self.submit = submit
        self.placeholder = placeholder
        self.hide_label = hide_label
        self.variant = variant
        super().__init__(attrs)

    def use_required_attribute(self, initial):
        return False

    def _selected_label(self, value):
        if value in (None, ""):
            return ""
        choices = getattr(self, "choices", None)
        if isinstance(choices, ModelChoiceIterator):
            obj = choices.queryset.filter(pk=value).first()
            if obj:
                return choices.field.label_from_instance(obj)
            return ""
        clave = getattr(self, "clave", "")
        if clave:
            from core.selectors import _spec

            obj = _spec(clave)["queryset"]().filter(pk=value).first()
            return str(obj) if obj else ""
        for row in self.options:
            if str(row.get("id")) == str(value):
                return row.get("label") or ""
        return ""

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        widget = context["widget"]
        search_url = self.search_url
        if not search_url and self.clave:
            search_url = reverse("selector_search", args=[self.clave])
        widget.update(
            combo_context(
                name=name,
                value=widget.get("value"),
                label=self.field_label,
                selected_label=self._selected_label(value),
                search_url=search_url,
                options=self.options,
                required=getattr(self, "is_required", False),
                required_message=self.required_message,
                submit=self.submit,
                placeholder=self.placeholder,
                attrs=widget.get("attrs") or {},
                hide_label=self.hide_label,
                variant=self.variant,
            )
        )
        return context

    def render(self, name, value, attrs=None, renderer=None):
        context = self.get_context(name, value, attrs)
        return render_to_string(self.template_name, context)


class ComboChoiceField(forms.ModelChoiceField):
    """Foráneo con búsqueda; solo acepta un id de la lista."""

    def __init__(
        self,
        queryset,
        *,
        clave="",
        search_url="",
        label,
        required_message,
        required=True,
        submit=False,
        widget=None,
        widget_attrs=None,
        placeholder="Buscar…",
        **kwargs,
    ):
        if widget is None:
            widget = ComboWidget(
                label=label,
                search_url=search_url,
                clave=clave,
                required_message=required_message,
                submit=submit,
                placeholder=placeholder,
                attrs=widget_attrs,
            )
        elif widget_attrs:
            widget.attrs.update(widget_attrs)
        error_messages = kwargs.pop("error_messages", {})
        error_messages.setdefault("required", required_message)
        error_messages.setdefault("invalid_choice", MENSAJE_LISTA)
        super().__init__(
            queryset=queryset,
            label=label,
            required=required,
            empty_label=None,
            widget=widget,
            error_messages=error_messages,
            **kwargs,
        )
        if required_message and hasattr(self.widget, "required_message"):
            self.widget.required_message = required_message
        if label and hasattr(self.widget, "field_label") and not self.widget.field_label:
            self.widget.field_label = label
        if clave and hasattr(self.widget, "clave") and not self.widget.clave:
            self.widget.clave = clave
        if search_url and hasattr(self.widget, "search_url") and not self.widget.search_url:
            self.widget.search_url = search_url

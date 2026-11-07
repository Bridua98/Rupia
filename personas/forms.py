from django import forms
from django.urls import reverse

from core.forms import RupiaModelForm
from personas.models import Genero, Persona, TipoDocumento, TipoPersona


class PersonaForm(RupiaModelForm):
    class Meta:
        model = Persona
        fields = [
            "tipo_persona",
            "tipo_documento",
            "documento",
            "razon_social",
            "fecha_nacimiento",
            "genero",
            "direccion",
            "celular",
            "observacion",
            "es_cliente",
            "es_proveedor",
            "es_empleado",
            "activo",
        ]
        labels = {
            "es_empleado": "Personal",
        }
        widgets = {
            "tipo_persona": forms.RadioSelect(),
            "documento": forms.TextInput(
                attrs={"autofocus": True, "autocomplete": "off"}
            ),
            "razon_social": forms.TextInput(attrs={"autocomplete": "off"}),
            "fecha_nacimiento": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date"},
            ),
            "celular": forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel"}),
            "observacion": forms.Textarea(attrs={"rows": 4}),
        }
        error_messages = {
            "tipo_persona": {
                "required": "Elegí si es persona física o jurídica.",
                "invalid_choice": "Elegí un tipo de persona válido.",
            },
            "tipo_documento": {
                "required": "Elegí el tipo de documento.",
                "invalid_choice": "Elegí un tipo de documento válido.",
            },
            "documento": {
                "required": "Escribí el documento.",
                "max_length": "El documento admite hasta 45 caracteres.",
            },
            "razon_social": {
                "required": "Escribí la razón social.",
                "max_length": "La razón social admite hasta 300 caracteres.",
            },
            "fecha_nacimiento": {
                "invalid": "Escribí una fecha válida.",
            },
            "genero": {
                "required": "Elegí el género.",
                "invalid_choice": "Elegí un género válido.",
            },
            "direccion": {
                "required": "Escribí la dirección.",
                "max_length": "La dirección admite hasta 300 caracteres.",
            },
            "observacion": {
                "max_length": "La observación admite hasta 300 caracteres.",
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        consulta_url = reverse("persona_consulta")
        self.fields["documento"].widget.attrs.update(
            {
                "autocomplete": "off",
                "data-persona-consulta": consulta_url,
                "data-persona-campo": "documento",
            }
        )
        self.fields["razon_social"].widget.attrs.update(
            {
                "autocomplete": "off",
                "data-persona-consulta": consulta_url,
                "data-persona-campo": "razon_social",
            }
        )
        self.fields["tipo_persona"].widget.attrs.pop("placeholder", None)
        if not self.instance.pk:
            self.fields["tipo_persona"].initial = TipoPersona.FISICO
            self.fields["tipo_documento"].initial = TipoDocumento.CEDULA
            self.fields["genero"].initial = Genero.SIN_DEFINIR

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("tipo_persona") == TipoPersona.JURIDICO:
            cleaned["genero"] = Genero.SIN_DEFINIR
        return cleaned

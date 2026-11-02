from django import forms

from core.forms import RupiaModelForm
from personas.models import Genero, Persona, TipoDocumento


class PersonaForm(RupiaModelForm):
    class Meta:
        model = Persona
        fields = [
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
            "documento": forms.TextInput(attrs={"autofocus": True}),
            "fecha_nacimiento": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date"},
            ),
            "celular": forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel"}),
            "observacion": forms.Textarea(attrs={"rows": 4}),
        }
        error_messages = {
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
        if not self.instance.pk:
            self.fields["tipo_documento"].initial = TipoDocumento.CEDULA
            self.fields["genero"].initial = Genero.SIN_DEFINIR

from django import forms

from core.forms import RupiaModelForm
from core.selectors import registrar
from negocio.models import UnidadNegocio


class UnidadNegocioForm(RupiaModelForm):
    descripcion = forms.CharField(
        label="Descripción",
        max_length=200,
        error_messages={
            "required": "Escribí la descripción.",
            "unique": "Ya hay una unidad de negocio con esa descripción.",
        },
        widget=forms.TextInput(
            attrs={
                "placeholder": " ",
                "autocomplete": "off",
                "autofocus": True,
                "maxlength": "200",
            }
        ),
    )
    abreviado = forms.CharField(
        label="Abreviado",
        max_length=20,
        error_messages={
            "required": "Escribí el abreviado.",
            "unique": "Ya hay una unidad de negocio con ese abreviado.",
        },
        widget=forms.TextInput(
            attrs={
                "placeholder": " ",
                "autocomplete": "off",
                "maxlength": "20",
            }
        ),
    )

    class Meta:
        model = UnidadNegocio
        fields = ["descripcion", "abreviado"]


registrar(
    "unidad_negocio",
    queryset=lambda: UnidadNegocio.objects.order_by("descripcion"),
    form=UnidadNegocioForm,
    search_fields=("descripcion", "abreviado"),
    create_label="Nueva unidad de negocio",
    formulario="unidades_negocio",
)

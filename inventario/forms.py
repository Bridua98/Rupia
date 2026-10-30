from django import forms

from core.forms import RupiaModelForm
from inventario.models import ItemCategoria, Marca, UnidadMedida


class MarcaForm(RupiaModelForm):
    descripcion = forms.CharField(
        label="Descripción",
        max_length=200,
        error_messages={"required": "Escribí la descripción."},
        widget=forms.TextInput(
            attrs={
                "placeholder": " ",
                "autocomplete": "off",
                "autofocus": True,
                "maxlength": "200",
            }
        ),
    )

    class Meta:
        model = Marca
        fields = ["descripcion"]


class CategoriaForm(RupiaModelForm):
    descripcion = forms.CharField(
        label="Descripción",
        max_length=300,
        error_messages={"required": "Escribí la descripción."},
        widget=forms.TextInput(
            attrs={
                "placeholder": " ",
                "autocomplete": "off",
                "autofocus": True,
                "maxlength": "300",
            }
        ),
    )

    class Meta:
        model = ItemCategoria
        fields = ["descripcion"]


class UnidadForm(RupiaModelForm):
    descripcion = forms.CharField(
        label="Descripción",
        max_length=100,
        error_messages={"required": "Escribí la descripción."},
        widget=forms.TextInput(
            attrs={
                "placeholder": " ",
                "autocomplete": "off",
                "autofocus": True,
                "maxlength": "100",
            }
        ),
    )
    simbolo = forms.CharField(
        label="Símbolo",
        max_length=10,
        error_messages={"required": "Escribí el símbolo."},
        widget=forms.TextInput(
            attrs={
                "placeholder": " ",
                "autocomplete": "off",
                "maxlength": "10",
            }
        ),
    )

    class Meta:
        model = UnidadMedida
        fields = ["descripcion", "simbolo"]

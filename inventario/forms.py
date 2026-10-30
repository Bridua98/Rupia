from django import forms

from core.forms import RupiaModelForm
from inventario.models import ItemCategoria, Marca


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

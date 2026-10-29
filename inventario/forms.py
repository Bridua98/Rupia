from django import forms

from inventario.models import Marca


class MarcaForm(forms.ModelForm):
    use_required_attribute = False

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

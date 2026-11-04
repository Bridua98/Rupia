from django import forms

from core.forms import RupiaModelForm
from core.selectors import registrar
from cuentas.models import Cuenta


class CuentaForm(RupiaModelForm):
    descripcion = forms.CharField(
        label="Descripción",
        max_length=200,
        error_messages={
            "required": "Escribí la descripción.",
            "unique": "Ya hay una cuenta con esa descripción.",
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
    nombre_corto = forms.CharField(
        label="Nombre corto",
        max_length=20,
        error_messages={
            "required": "Escribí el nombre corto.",
            "unique": "Ya hay una cuenta con ese nombre corto.",
        },
        widget=forms.TextInput(
            attrs={
                "placeholder": " ",
                "autocomplete": "off",
                "maxlength": "20",
            }
        ),
    )
    es_banco = forms.BooleanField(
        label="Banco",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={"data-cuenta-banco": True}),
    )
    es_tarjeta = forms.BooleanField(
        label="Tarjeta",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={"data-cuenta-si-banco": True}),
    )
    numero = forms.CharField(
        label="Número de cuenta",
        max_length=45,
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": " ",
                "autocomplete": "off",
                "maxlength": "45",
                "data-cuenta-si-banco": True,
            }
        ),
    )

    class Meta:
        model = Cuenta
        fields = ["descripcion", "nombre_corto", "es_banco", "es_tarjeta", "numero"]

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("es_banco"):
            cleaned["es_tarjeta"] = False
            cleaned["numero"] = None
        return cleaned


registrar(
    "cuenta",
    queryset=lambda: Cuenta.objects.order_by("descripcion"),
    form=CuentaForm,
    search_fields=("descripcion", "nombre_corto", "numero"),
    create_label="Nueva cuenta",
    formulario="cuentas",
)

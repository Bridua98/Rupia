from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.forms import RupiaModelForm
from core.moneda import MonedaField
from core.selectors import SelectorAlta, registrar
from cuentas.models import Cuenta, EstadoTransferencia, Transferencia


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


class TransferenciaForm(RupiaModelForm):
    fecha = forms.DateField(
        label="Fecha",
        initial=timezone.localdate,
        error_messages={"required": "Elegí la fecha.", "invalid": "Elegí una fecha válida."},
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={"type": "date", "placeholder": " ", "autocomplete": "off", "autofocus": True},
        ),
    )
    cuenta_origen = SelectorAlta(
        clave="cuenta",
        label="Cuenta de salida",
        required_message="Elegí la cuenta de salida.",
    )
    importe_salida = MonedaField(
        label="Importe de salida",
        error_messages={"required": "Escribí el importe de salida."},
    )
    cuenta_destino = SelectorAlta(
        clave="cuenta",
        label="Cuenta de entrada",
        required_message="Elegí la cuenta de entrada.",
    )
    importe_entrada = MonedaField(
        label="Importe de entrada",
        error_messages={"required": "Escribí el importe de entrada."},
    )
    comprobante = forms.CharField(
        label="Comprobante",
        max_length=80,
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": " ",
                "autocomplete": "off",
                "maxlength": "80",
            }
        ),
    )

    class Meta:
        model = Transferencia
        fields = ["fecha", "cuenta_origen", "cuenta_destino", "comprobante"]

    field_order = [
        "fecha",
        "cuenta_origen",
        "importe_salida",
        "cuenta_destino",
        "importe_entrada",
        "comprobante",
    ]

    def clean(self):
        cleaned = super().clean()
        origen = cleaned.get("cuenta_origen")
        destino = cleaned.get("cuenta_destino")
        if origen and destino and origen.pk == destino.pk:
            raise ValidationError("La cuenta de salida y la de entrada tienen que ser distintas.")
        salida = cleaned.get("importe_salida")
        entrada = cleaned.get("importe_entrada")
        if salida is not None and salida <= 0:
            self.add_error("importe_salida", "El importe tiene que ser mayor a cero.")
        if entrada is not None and entrada <= 0:
            self.add_error("importe_entrada", "El importe tiene que ser mayor a cero.")
        if (
            salida is not None
            and entrada is not None
            and salida > 0
            and entrada > 0
            and salida != entrada
        ):
            raise ValidationError("El importe de salida y el de entrada tienen que coincidir.")
        cleaned["importe"] = salida
        return cleaned

    def save(self, commit=True):
        self.instance.importe = self.cleaned_data["importe"]
        self.instance.estado = EstadoTransferencia.CONFIRMADA
        return super().save(commit)

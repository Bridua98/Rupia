from django import forms

from core.forms import RupiaModelForm
from core.timbrado import LONGITUD_TIMBRADO, MENSAJE_TIMBRADO, interpretar_timbrado
from ventas.models import Maquina, PuntoExpedicion, TipoComprobante


class TimbradoForm(RupiaModelForm):
    class Meta:
        model = PuntoExpedicion
        fields = [
            "tipo",
            "establecimiento",
            "codigo",
            "timbrado",
            "vigencia_desde",
            "vigencia_hasta",
            "numero_desde",
            "numero_hasta",
            "numero_proximo",
            "habilitado",
            "emisor_razon_social",
            "emisor_ruc",
            "emisor_direccion",
            "emisor_telefono",
            "emisor_actividad",
        ]
        widgets = {
            "tipo": forms.Select(attrs={"autofocus": True}),
            "timbrado": forms.TextInput(
                attrs={
                    "maxlength": str(LONGITUD_TIMBRADO),
                    "inputmode": "numeric",
                    "autocomplete": "off",
                }
            ),
            "vigencia_desde": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "vigencia_hasta": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }
        error_messages = {
            "tipo": {
                "required": "Elegí el tipo de comprobante.",
                "invalid_choice": "Elegí un tipo de comprobante válido.",
            },
            "establecimiento": {
                "required": "Escribí el establecimiento.",
                "max_length": "El establecimiento tiene tres dígitos.",
            },
            "codigo": {
                "required": "Escribí el punto.",
                "max_length": "El punto tiene tres dígitos.",
            },
            "timbrado": {
                "required": "Escribí el timbrado.",
                "max_length": MENSAJE_TIMBRADO,
            },
            "vigencia_desde": {
                "required": "Escribí la vigencia desde.",
                "invalid": "Escribí una fecha válida.",
            },
            "vigencia_hasta": {
                "required": "Escribí la vigencia hasta.",
                "invalid": "Escribí una fecha válida.",
            },
            "numero_desde": {
                "required": "Escribí el número desde.",
            },
            "numero_hasta": {
                "required": "Escribí el número hasta.",
            },
            "emisor_razon_social": {
                "required": "Escribí la razón social.",
                "max_length": "La razón social admite hasta 300 caracteres.",
            },
            "emisor_ruc": {
                "required": "Escribí el RUC.",
                "max_length": "El RUC admite hasta 45 caracteres.",
            },
            "emisor_direccion": {
                "required": "Escribí la dirección.",
                "max_length": "La dirección admite hasta 300 caracteres.",
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["numero_proximo"].required = False
        self.fields["tipo"].choices = [("", "---------"), *TipoComprobante.choices]
        self.fields["timbrado"].max_length = LONGITUD_TIMBRADO
        self.fields["timbrado"].min_length = LONGITUD_TIMBRADO
        self.fields["timbrado"].error_messages["min_length"] = MENSAJE_TIMBRADO

    def clean_timbrado(self):
        return interpretar_timbrado(self.cleaned_data.get("timbrado"))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("numero_proximo") in (None, "") and cleaned.get("numero_desde"):
            cleaned["numero_proximo"] = cleaned["numero_desde"]
        tipo = cleaned.get("tipo")
        establecimiento = cleaned.get("establecimiento")
        codigo = cleaned.get("codigo")
        timbrado = cleaned.get("timbrado")
        if tipo and establecimiento and codigo and timbrado:
            repetido = PuntoExpedicion.objects.filter(
                tipo=tipo,
                establecimiento=establecimiento,
                codigo=codigo,
                timbrado=timbrado,
            )
            if self.instance.pk:
                repetido = repetido.exclude(pk=self.instance.pk)
            if repetido.exists():
                self.add_error("codigo", "Ya hay un timbrado para esa serie.")
        if (
            tipo
            and self.instance.pk
            and tipo != self.instance.tipo
            and (
                self.instance.maquinas_ticket.exists() or self.instance.maquinas_factura.exists()
            )
        ):
            self.add_error(
                "tipo",
                "Este punto está asignado a una máquina: quitáselo antes de cambiar el tipo.",
            )
        return cleaned


class MaquinaForm(RupiaModelForm):
    class Meta:
        model = Maquina
        fields = ["nombre", "punto_ticket", "punto_factura"]
        widgets = {
            "nombre": forms.TextInput(attrs={"autofocus": True, "autocomplete": "off"}),
        }
        error_messages = {
            "nombre": {
                "required": "Escribí el nombre de la máquina.",
                "unique": "Ya hay una máquina con ese nombre.",
                "max_length": "El nombre admite hasta 80 caracteres.",
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["punto_ticket"].queryset = PuntoExpedicion.objects.filter(
            tipo=TipoComprobante.TICKET
        ).order_by("establecimiento", "codigo", "timbrado")
        self.fields["punto_ticket"].required = False
        self.fields["punto_factura"].queryset = PuntoExpedicion.objects.filter(
            tipo=TipoComprobante.FACTURA
        ).order_by("establecimiento", "codigo", "timbrado")
        self.fields["punto_factura"].required = False
        self.fields["punto_ticket"].label_from_instance = _etiqueta_punto
        self.fields["punto_factura"].label_from_instance = _etiqueta_punto


def _etiqueta_punto(punto):
    estado = "" if punto.habilitado else " (deshabilitado)"
    return f"{punto.serie} · {punto.timbrado}{estado}"

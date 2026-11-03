from django import forms

from core.forms import RupiaModelForm
from ventas.models import PuntoExpedicion, TipoComprobante


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
            "vigencia_desde": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "vigencia_hasta": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }
        error_messages = {
            "tipo": {
                "required": "Elegí el tipo de comprobante.",
                "invalid_choice": "Elegí un tipo de comprobante válido.",
                "unique": "Ya hay un timbrado para ese tipo de comprobante.",
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
                "max_length": "El timbrado admite hasta 20 caracteres.",
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

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("numero_proximo") in (None, "") and cleaned.get("numero_desde"):
            cleaned["numero_proximo"] = cleaned["numero_desde"]
        return cleaned

from django.core.exceptions import ValidationError

LONGITUD_TIMBRADO = 8
MENSAJE_TIMBRADO = "El timbrado tiene 8 dígitos."


def interpretar_timbrado(valor, *, requerido=True) -> str:
    texto = str(valor or "").strip()
    if not texto:
        if requerido:
            raise ValidationError("Escribí el timbrado.", code="timbrado")
        return ""
    if not texto.isdigit() or len(texto) != LONGITUD_TIMBRADO:
        raise ValidationError(MENSAJE_TIMBRADO, code="timbrado")
    return texto

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from cuentas.models import EstadoTransferencia, Transferencia


def anular(transferencia, usuario=None):
    with transaction.atomic():
        transferencia = Transferencia.objects.select_for_update().get(pk=transferencia.pk)
        if transferencia.estado == EstadoTransferencia.ANULADA:
            raise ValidationError("Esa transferencia ya está anulada.", code="anulada")
        if transferencia.estado != EstadoTransferencia.CONFIRMADA:
            raise ValidationError(
                "Solo se puede anular una transferencia confirmada.",
                code="estado",
            )
        transferencia.estado = EstadoTransferencia.ANULADA
        transferencia.anulado_en = timezone.now()
        transferencia.anulado_por = usuario
        transferencia.save(update_fields=["estado", "anulado_en", "anulado_por"])
    return transferencia

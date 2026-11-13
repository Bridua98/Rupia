"""Cola de cada sector de preparación: lo que llega, se imprime y queda listo."""

from django.core.exceptions import ValidationError
from django.utils import timezone

from mesas.models import EnvioSector, EstadoEnvio

ESTADOS_EN_COLA = (EstadoEnvio.PENDIENTE, EstadoEnvio.IMPRESO)


def _base():
    return EnvioSector.objects.select_related(
        "comanda",
        "comanda__mesa",
        "comanda__cliente",
        "ronda",
        "usuario",
        "sector",
    ).prefetch_related("lineas")


def cola(sector):
    """Lo que el sector todavía tiene que preparar, del más viejo al más nuevo."""
    return list(
        _base().filter(sector=sector, estado__in=ESTADOS_EN_COLA).order_by("creado_en", "id")
    )


def recientes_listos(sector, limite=6):
    return list(
        _base()
        .filter(sector=sector, estado=EstadoEnvio.LISTO)
        .order_by("-listo_en", "-id")[:limite]
    )


def _reservar(envio_id) -> bool:
    """Marca impreso un envío pendiente. Devuelve True solo a quien lo reservó.

    Es un UPDATE condicional: aunque haya dos pantallas abiertas del mismo
    sector, cada envío se imprime una sola vez.
    """
    return bool(
        EnvioSector.objects.filter(pk=envio_id, estado=EstadoEnvio.PENDIENTE).update(
            estado=EstadoEnvio.IMPRESO,
            impreso_en=timezone.now(),
        )
    )


def tomar_pendientes(sector):
    """Reserva lo pendiente del sector para imprimirlo. Lo que ya tomó otra pantalla no vuelve."""
    candidatos = list(
        EnvioSector.objects.filter(sector=sector, estado=EstadoEnvio.PENDIENTE)
        .order_by("creado_en", "id")
        .values_list("pk", flat=True)
    )
    tomados = [pk for pk in candidatos if _reservar(pk)]
    if not tomados:
        return []
    return list(_base().filter(pk__in=tomados).order_by("creado_en", "id"))


def imprimir(envio):
    """Para imprimir a mano o reimprimir: si estaba pendiente queda impreso."""
    if envio.estado == EstadoEnvio.PENDIENTE:
        _reservar(envio.pk)
    return _base().get(pk=envio.pk)


def marcar_listo(envio):
    if envio.estado == EstadoEnvio.LISTO:
        raise ValidationError("Ese pedido ya estaba listo.", code="listo")
    ahora = timezone.now()
    EnvioSector.objects.filter(pk=envio.pk).exclude(estado=EstadoEnvio.LISTO).update(
        estado=EstadoEnvio.LISTO,
        listo_en=ahora,
        impreso_en=envio.impreso_en or ahora,
    )
    envio.refresh_from_db()
    return envio


def volver_a_cola(envio):
    """Deshace un 'listo' tocado por error."""
    if envio.estado != EstadoEnvio.LISTO:
        raise ValidationError("Ese pedido sigue en la cola.", code="en_cola")
    EnvioSector.objects.filter(pk=envio.pk).update(estado=EstadoEnvio.IMPRESO, listo_en=None)
    envio.refresh_from_db()
    return envio

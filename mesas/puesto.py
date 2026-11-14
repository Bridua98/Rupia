"""Cola de cada sector de preparación: lo que llega, se imprime y queda listo."""

from django.core.exceptions import ValidationError
from django.utils import timezone

from mesas.models import EnvioSector, EstadoEnvio

ESTADOS_EN_COLA = (EstadoEnvio.PENDIENTE, EstadoEnvio.IMPRESO, EstadoEnvio.PREPARACION)
ESTADOS_SIN_EMPEZAR = (EstadoEnvio.PENDIENTE, EstadoEnvio.IMPRESO)


def _base():
    return EnvioSector.objects.select_related(
        "comanda",
        "comanda__mesa",
        "comanda__cliente",
        "ronda",
        "usuario",
        "sector",
    ).prefetch_related("lineas")


def _ordenados(sector, estados):
    if isinstance(estados, str):
        estados = (estados,)
    return list(_base().filter(sector=sector, estado__in=estados).order_by("creado_en", "id"))


def cola(sector):
    """Lo que el sector todavía tiene que preparar, del más viejo al más nuevo."""
    return _ordenados(sector, ESTADOS_EN_COLA)


def abiertos(sector):
    """Todavía no se empezaron: pendientes, o impresos si el sector pide empezar."""
    if sector.exige_empezar:
        return _ordenados(sector, ESTADOS_SIN_EMPEZAR)
    return _ordenados(sector, EstadoEnvio.PENDIENTE)


def en_preparacion(sector):
    """Ya se están trabajando."""
    if sector.exige_empezar:
        return _ordenados(sector, EstadoEnvio.PREPARACION)
    return _ordenados(sector, EstadoEnvio.IMPRESO)


POR_PAGINA_DIA = 8
DETALLE_CORTO = 3


def _inicio_del_dia():
    return timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)


def _listos_de_hoy(sector):
    return _base().filter(
        sector=sector, estado=EstadoEnvio.LISTO, listo_en__gte=_inicio_del_dia()
    )


def recientes_listos(sector, limite=6):
    return list(
        _base()
        .filter(sector=sector, estado=EstadoEnvio.LISTO)
        .order_by("-listo_en", "-id")[:limite]
    )


def listos_hoy(sector):
    return _listos_de_hoy(sector).count()


def listos_del_dia(sector, pagina=1, por_pagina=POR_PAGINA_DIA):
    """Los listos de hoy, de a una página. La primera es la más reciente."""
    try:
        numero = int(pagina)
    except (TypeError, ValueError):
        numero = 1
    if numero < 1:
        numero = 1
    ordenados = _listos_de_hoy(sector).order_by("-listo_en", "-id")
    total = ordenados.count()
    paginas = max(1, (total + por_pagina - 1) // por_pagina)
    numero = min(numero, paginas)
    desde = (numero - 1) * por_pagina
    return {
        "items": list(ordenados[desde : desde + por_pagina]),
        "total": total,
        "pagina": numero,
        "paginas": paginas if total else 1,
        "hay_anterior": numero > 1,
        "hay_siguiente": numero < paginas,
    }


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


def empezar(envio):
    """Pasa el ticket a preparación. Dos pantallas no lo empiezan dos veces."""
    if envio.estado == EstadoEnvio.LISTO:
        raise ValidationError("Ese pedido ya estaba listo.", code="listo")
    ahora = timezone.now()
    EnvioSector.objects.filter(pk=envio.pk).exclude(
        estado__in=(EstadoEnvio.PREPARACION, EstadoEnvio.LISTO)
    ).update(
        estado=EstadoEnvio.PREPARACION,
        empezado_en=ahora,
        impreso_en=envio.impreso_en or ahora,
    )
    envio.refresh_from_db()
    return envio


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
    if envio.sector.exige_empezar and envio.empezado_en:
        estado = EstadoEnvio.PREPARACION
    else:
        estado = EstadoEnvio.IMPRESO
    EnvioSector.objects.filter(pk=envio.pk).update(estado=estado, listo_en=None)
    envio.refresh_from_db()
    return envio

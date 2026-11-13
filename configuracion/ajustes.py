from configuracion.models import Ajustes


def ajustes() -> Ajustes:
    return Ajustes.actuales()


def mesas_habilitadas() -> bool:
    return Ajustes.objects.filter(pk=1, mesas_habilitadas=True).exists()

import re
from pathlib import Path

from django.conf import settings

EXTENSIONES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_SEGMENTO = re.compile(r"[^A-Za-z0-9._-]+")


def carpeta_imagenes():
    destino = Path(settings.RUPIA_IMAGENES_DIR)
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def nombre_seguro(original):
    base = Path(str(original or "")).name
    base = _SEGMENTO.sub("-", base).strip(".-_")
    suffix = Path(base).suffix.lower()
    stem = _SEGMENTO.sub("-", Path(base).stem).strip(".-_") or "imagen"
    if suffix not in EXTENSIONES:
        suffix = ""
    nombre = f"{stem}{suffix}" or "imagen"
    if len(nombre) > 180:
        nombre = f"{stem[: 180 - len(suffix)]}{suffix}"
    return nombre


def _ocupado(nombre, excluir_pk):
    from inventario.models import Item

    consulta = Item.objects.filter(imagen=nombre)
    if excluir_pk:
        consulta = consulta.exclude(pk=excluir_pk)
    return consulta.exists()


def nombre_libre(nombre, excluir_pk=None):
    suffix = Path(nombre).suffix
    stem = Path(nombre).stem
    candidato = nombre
    numero = 2
    while _ocupado(candidato, excluir_pk):
        extra = f"-{numero}"
        limite = 200 - len(suffix) - len(extra)
        candidato = f"{stem[:limite]}{extra}{suffix}"
        numero += 1
    return candidato


def resolver_imagen(nombre):
    if not isinstance(nombre, str) or not nombre or nombre != Path(nombre).name:
        return None
    if nombre in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9._-]+", nombre):
        return None
    raiz = Path(settings.RUPIA_IMAGENES_DIR).resolve()
    destino = (raiz / nombre).resolve()
    if not destino.is_relative_to(raiz) or not destino.is_file():
        return None
    return destino


def guardar_imagen(archivo, excluir_pk=None):
    nombre = nombre_libre(nombre_seguro(archivo.name), excluir_pk)
    destino = carpeta_imagenes() / nombre
    with destino.open("wb") as salida:
        for chunk in archivo.chunks():
            salida.write(chunk)
    return nombre


def liberar_imagen(nombre, excluir_pk=None):
    if not nombre or _ocupado(nombre, excluir_pk):
        return
    destino = resolver_imagen(nombre)
    if destino is not None:
        destino.unlink(missing_ok=True)

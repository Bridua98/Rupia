import re
from pathlib import Path

from django.conf import settings
from django.urls import reverse

from configuracion.models import UsuarioFoto

EXTENSIONES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_NOMBRE = re.compile(r"^usuario-\d+\.(jpg|jpeg|png|webp|gif)$")


def carpeta_fotos():
    destino = Path(settings.RUPIA_IMAGENES_DIR) / "usuarios"
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def resolver_foto(nombre):
    if not isinstance(nombre, str) or not _NOMBRE.fullmatch(nombre):
        return None
    raiz = carpeta_fotos().resolve()
    destino = (raiz / nombre).resolve()
    if not destino.is_relative_to(raiz) or not destino.is_file():
        return None
    return destino


def guardar_foto(usuario, archivo):
    suffix = Path(archivo.name).suffix.lower()
    if suffix not in EXTENSIONES:
        suffix = ".png"
    nombre = f"usuario-{usuario.pk}{suffix}"
    carpeta = carpeta_fotos()
    for viejo in carpeta.glob(f"usuario-{usuario.pk}.*"):
        if viejo.name != nombre:
            viejo.unlink(missing_ok=True)
    destino = carpeta / nombre
    with destino.open("wb") as salida:
        for chunk in archivo.chunks():
            salida.write(chunk)
    return nombre


def liberar_foto(nombre):
    destino = resolver_foto(nombre)
    if destino is not None:
        destino.unlink(missing_ok=True)


def url_foto(user):
    if not user or not getattr(user, "is_authenticated", False) or not user.pk:
        return ""
    foto = UsuarioFoto.objects.filter(usuario_id=user.pk).exclude(imagen="").first()
    if not foto:
        return ""
    return reverse("usuario_imagen", args=[foto.imagen])


def aplicar_foto(user, archivo=None, quitar=False):
    foto, _ = UsuarioFoto.objects.get_or_create(usuario=user)
    anterior = foto.imagen
    if archivo:
        foto.imagen = guardar_foto(user, archivo)
        foto.save(update_fields=["imagen"])
        if anterior and anterior != foto.imagen:
            liberar_foto(anterior)
        return foto
    if quitar:
        foto.imagen = ""
        foto.save(update_fields=["imagen"])
        if anterior:
            liberar_foto(anterior)
    return foto

from configuracion.fotos import url_foto
from configuracion.permisos import etiqueta_sesion
from core.menus import main_menu


def menu(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    return {
        "menu": main_menu(request),
        "session_role": etiqueta_sesion(user),
        "session_foto_url": url_foto(user),
    }

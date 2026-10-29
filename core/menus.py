from django.urls import reverse


def main_menu(request):
    """Entradas del menú lateral de la app autenticada."""
    current = request.path.rstrip("/") or "/"

    def item(label, url_name=None, href=None, *, staff_only=False, disabled=False):
        if staff_only and not request.user.is_staff:
            return None
        if url_name:
            href = reverse(url_name)
        path = href.split("?", 1)[0].rstrip("/") or "/"
        active = path == current
        return {
            "label": label,
            "href": href,
            "active": active,
            "disabled": disabled,
        }

    entries = [
        item("Inicio", url_name="home"),
        item("Personas", href="#", disabled=True),
        item("Inventario", href="#", disabled=True),
        item("Administración", url_name="admin:index", staff_only=True),
    ]
    return [e for e in entries if e is not None]

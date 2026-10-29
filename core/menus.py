from django.urls import reverse


def main_menu(request):
    """Entradas del menú lateral de la app autenticada."""
    current = request.path.rstrip("/") or "/"

    def is_active(href):
        path = href.split("?", 1)[0].rstrip("/") or "/"
        if path == "/":
            return current == "/"
        return current == path or current.startswith(f"{path}/")

    def item(label, url_name=None, href=None, *, staff_only=False, disabled=False):
        if staff_only and not request.user.is_staff:
            return None
        if url_name:
            href = reverse(url_name)
        return {
            "label": label,
            "href": href,
            "active": is_active(href),
            "disabled": disabled,
        }

    def group(label, children):
        kids = [child for child in children if child is not None]
        if not kids:
            return None
        return {"label": label, "children": kids}

    entries = [
        item("Inicio", url_name="home"),
        item("Personas", href="#", disabled=True),
        group("Inventario", [item("Marcas", url_name="marca_list")]),
        item("Administración", url_name="admin:index", staff_only=True),
    ]
    return [e for e in entries if e is not None]

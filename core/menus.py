from django.urls import reverse


def main_menu(request):
    """Entradas del menú lateral de la app autenticada."""
    current = request.path.rstrip("/") or "/"

    def is_active(href):
        path = href.split("?", 1)[0].rstrip("/") or "/"
        if path == "/":
            return current == "/"
        return current == path or current.startswith(f"{path}/")

    def item(label, url_name=None, href=None, *, icon="", staff_only=False, disabled=False):
        if staff_only and not request.user.is_staff:
            return None
        if url_name:
            href = reverse(url_name)
        return {
            "label": label,
            "href": href,
            "icon": icon,
            "active": is_active(href),
            "disabled": disabled,
        }

    def group(label, children, *, icon=""):
        kids = [child for child in children if child is not None]
        if not kids:
            return None
        return {
            "label": label,
            "icon": icon,
            "children": kids,
            "expanded": any(child.get("active") for child in kids),
        }

    entries = [
        item("Inicio", url_name="home", icon="home"),
        item("Personas", href="#", icon="users", disabled=True),
        group(
            "Inventario",
            [item("Marcas", url_name="marca_list", icon="tag")],
            icon="box",
        ),
        item("Administración", url_name="admin:index", icon="settings", staff_only=True),
    ]
    return [e for e in entries if e is not None]

from django.urls import reverse

from configuracion.permisos import tiene_permiso


def main_menu(request):
    """Entradas del menú lateral de la app autenticada."""
    current = request.path.rstrip("/") or "/"

    def is_active(href):
        path = href.split("?", 1)[0].rstrip("/") or "/"
        if path == "/":
            return current == "/"
        return current == path or current.startswith(f"{path}/")

    def item(
        label,
        url_name=None,
        href=None,
        *,
        icon="",
        staff_only=False,
        disabled=False,
        formulario=None,
    ):
        if staff_only and not request.user.is_staff:
            return None
        if formulario and not tiene_permiso(request.user, formulario, "ver"):
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
        item(
            "Punto de venta",
            url_name="punto_de_venta",
            icon="wallet",
            formulario="punto_de_venta",
        ),
        item("Personas", url_name="persona_list", icon="users", formulario="personas"),
        group(
            "Caja",
            [
                item("Cuentas", url_name="cuenta_list", icon="wallet", formulario="cuentas"),
                item("Timbrados", url_name="timbrado_list", icon="file", formulario="timbrados"),
            ],
            icon="wallet",
        ),
        group(
            "Inventario",
            [
                item("Marcas", url_name="marca_list", icon="tag", formulario="marcas"),
                item("Categorías", url_name="categoria_list", icon="tag", formulario="categorias"),
                item(
                    "Unidades de medida",
                    url_name="unidad_list",
                    icon="tag",
                    formulario="unidades",
                ),
                item(
                    "Unidades de negocio",
                    url_name="unidad_negocio_list",
                    icon="tag",
                    formulario="unidades_negocio",
                ),
                item("Ítems", url_name="item_list", icon="box", formulario="items"),
                item("Precios", url_name="precio_list", icon="tag", formulario="precios"),
                item(
                    "Reporte de productos",
                    url_name="reporte_productos",
                    icon="file",
                    formulario="reporte_productos",
                ),
                item("Stock", url_name="reporte_stock", icon="file", formulario="reporte_stock"),
            ],
            icon="box",
        ),
        group(
            "Configuración",
            [
                item("Usuarios", url_name="usuario_list", icon="users", formulario="usuarios"),
                item("Perfiles", url_name="perfil_list", icon="tag", formulario="perfiles"),
                item("Contraseña", url_name="cambiar_contrasena", icon="key"),
                item(
                    "Administración",
                    url_name="admin:index",
                    icon="settings",
                    staff_only=True,
                ),
            ],
            icon="settings",
        ),
    ]
    return [e for e in entries if e is not None]

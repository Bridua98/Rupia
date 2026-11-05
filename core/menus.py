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
        current = any(child.get("active") for child in kids)
        return {
            "label": label,
            "icon": icon,
            "children": kids,
            "expanded": current,
            "active": current,
        }

    entries = [
        item("Inicio", url_name="home", icon="home"),
        item(
            "Punto de venta",
            url_name="punto_de_venta",
            icon="bag",
            formulario="punto_de_venta",
        ),
        item("Ventas", url_name="venta_list", icon="receipt", formulario="ventas"),
        item("Compras", url_name="compra_list", icon="wallet", formulario="compras"),
        item("Personas", url_name="persona_list", icon="users", formulario="personas"),
        group(
            "Gestión",
            [
                item("Timbrados", url_name="timbrado_list", icon="receipt", formulario="timbrados"),
                item("Cuentas", url_name="cuenta_list", icon="bank", formulario="cuentas"),
                item(
                    "Transferencias",
                    url_name="transferencia_list",
                    icon="cash",
                    formulario="transferencias",
                ),
                item(
                    "Disponibilidad",
                    url_name="reporte_disponibilidad",
                    icon="chart",
                    formulario="reporte_disponibilidad",
                ),
                item(
                    "Unidades de negocio",
                    url_name="unidad_negocio_list",
                    icon="building",
                    formulario="unidades_negocio",
                ),
            ],
            icon="cash",
        ),
        group(
            "Inventario",
            [
                item("Marcas", url_name="marca_list", icon="tag", formulario="marcas"),
                item(
                    "Categorías",
                    url_name="categoria_list",
                    icon="folder",
                    formulario="categorias",
                ),
                item(
                    "Unidades de medida",
                    url_name="unidad_list",
                    icon="scale",
                    formulario="unidades",
                ),
                item("Ítems", url_name="item_list", icon="box", formulario="items"),
                item("Precios", url_name="precio_list", icon="percent", formulario="precios"),
                item(
                    "Reporte de productos",
                    url_name="reporte_productos",
                    icon="chart",
                    formulario="reporte_productos",
                ),
                item("Stock", url_name="reporte_stock", icon="layers", formulario="reporte_stock"),
                item(
                    "Ajustes de stock",
                    url_name="ajuste_stock_list",
                    icon="check",
                    formulario="ajustes_stock",
                ),
            ],
            icon="box",
        ),
        group(
            "Configuración",
            [
                item("Usuarios", url_name="usuario_list", icon="user", formulario="usuarios"),
                item("Perfiles", url_name="perfil_list", icon="shield", formulario="perfiles"),
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

import django_tables2 as tables
from django.contrib.auth import get_user_model

from configuracion.models import Perfil
from configuracion.permisos import tiene_permiso
from core.tables import ActionMenuColumn, mantenimiento_row_actions
from core.vista import html_bool

User = get_user_model()


def usuario_row_actions(record, table=None):
    actions = mantenimiento_row_actions(record, table)
    if table is None:
        return actions
    request = getattr(table, "request", None)
    user = getattr(request, "user", None)
    list_query = getattr(table, "list_query", None)
    selection_param = getattr(table, "selection_param", None)
    if not user or not list_query or not selection_param:
        return actions
    if tiene_permiso(user, "usuarios", "clave"):
        actions.append(
            {
                "label": "Cambiar contraseña",
                "icon": "key",
                "href": list_query(**{selection_param: record.pk, "clave": 1}),
            }
        )
    return actions


class PerfilTable(tables.Table):
    descripcion = tables.Column(verbose_name="Descripción")
    activo = tables.Column(verbose_name="Activo")
    usuarios = tables.Column(verbose_name="Usuarios", empty_values=())
    acciones = ActionMenuColumn()

    class Meta:
        model = Perfil
        fields = ("descripcion", "activo", "usuarios", "acciones")
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay perfiles."
        attrs = {"class": "sheet"}

    def render_activo(self, value):
        return html_bool(value)

    def render_usuarios(self, record):
        return record.usuarios.count()


class UsuarioTable(tables.Table):
    username = tables.Column(verbose_name="Usuario")
    nombre = tables.Column(verbose_name="Nombre", empty_values=(), orderable=False)
    email = tables.Column(verbose_name="Correo")
    perfiles = tables.Column(verbose_name="Perfiles", empty_values=(), orderable=False)
    is_active = tables.Column(verbose_name="Activo")
    acciones = ActionMenuColumn(get_actions=usuario_row_actions)

    class Meta:
        model = User
        fields = ("username", "nombre", "email", "perfiles", "is_active", "acciones")
        orderable = False
        template_name = "django_tables2/rupia.html"
        empty_text = "Todavía no hay usuarios."
        attrs = {"class": "sheet"}

    def render_nombre(self, record):
        nombre = record.get_full_name().strip()
        return nombre or "—"

    def render_perfiles(self, record):
        nombres = [perfil.descripcion for perfil in record.perfiles.all()]
        return ", ".join(nombres) if nombres else "—"

    def render_is_active(self, value):
        return html_bool(value)

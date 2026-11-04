from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied

from configuracion.catalogo import accion_permitida
from configuracion.models import PerfilPermiso


def tiene_permiso(user, formulario, accion) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if not user.is_active:
        return False
    if user.is_superuser:
        return True
    if not accion_permitida(formulario, accion):
        return False
    return PerfilPermiso.objects.filter(
        perfil__usuarios=user,
        perfil__activo=True,
        formulario=formulario,
        accion=accion,
    ).exists()


def exigir_permiso(user, formulario, accion):
    if not tiene_permiso(user, formulario, accion):
        raise PermissionDenied("No tenés permiso para esta acción.")


def etiqueta_sesion(user) -> str:
    if user is None or not user.is_authenticated:
        return ""
    if user.is_superuser:
        return "Superusuario"
    nombres = list(
        user.perfiles.filter(activo=True).order_by("descripcion").values_list(
            "descripcion", flat=True
        )[:2]
    )
    if not nombres:
        return "Usuario"
    return ", ".join(nombres)


class PermisoRequeridoMixin(AccessMixin):
    permiso_formulario = ""
    permiso_accion = "ver"

    def get_permiso_formulario(self):
        return self.permiso_formulario

    def get_permiso_accion(self):
        return self.permiso_accion

    def dispatch(self, request, *args, **kwargs):
        formulario = self.get_permiso_formulario()
        if formulario:
            exigir_permiso(request.user, formulario, self.get_permiso_accion())
        return super().dispatch(request, *args, **kwargs)

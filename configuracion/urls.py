from django.urls import path

from configuracion.views import (
    AjustesView,
    CambiarContrasenaView,
    CopiaDescargaView,
    CopiaListView,
    PerfilCreateView,
    PerfilDeleteView,
    PerfilListView,
    PerfilUpdateView,
    UsuarioCreateView,
    UsuarioDeleteView,
    UsuarioImagenView,
    UsuarioListView,
    UsuarioPasswordView,
    UsuarioUpdateView,
)
from core.mantenimiento import mantenimiento_salida

urlpatterns = [
    path("usuarios/", UsuarioListView.as_view(), name="usuario_list"),
    path(
        "usuarios/imprimir/",
        mantenimiento_salida(UsuarioListView, "print").as_view(),
        name="usuario_print",
    ),
    path(
        "usuarios/exportar.xlsx",
        mantenimiento_salida(UsuarioListView, "xlsx").as_view(),
        name="usuario_export_xlsx",
    ),
    path(
        "usuarios/exportar.pdf",
        mantenimiento_salida(UsuarioListView, "pdf").as_view(),
        name="usuario_export_pdf",
    ),
    path("usuarios/nueva/", UsuarioCreateView.as_view(), name="usuario_create"),
    path("usuarios/<int:pk>/", UsuarioUpdateView.as_view(), name="usuario_update"),
    path("usuarios/<int:pk>/eliminar/", UsuarioDeleteView.as_view(), name="usuario_delete"),
    path(
        "usuarios/<int:pk>/contrasena/",
        UsuarioPasswordView.as_view(),
        name="usuario_password",
    ),
    path("perfiles/", PerfilListView.as_view(), name="perfil_list"),
    path(
        "perfiles/imprimir/",
        mantenimiento_salida(PerfilListView, "print").as_view(),
        name="perfil_print",
    ),
    path(
        "perfiles/exportar.xlsx",
        mantenimiento_salida(PerfilListView, "xlsx").as_view(),
        name="perfil_export_xlsx",
    ),
    path(
        "perfiles/exportar.pdf",
        mantenimiento_salida(PerfilListView, "pdf").as_view(),
        name="perfil_export_pdf",
    ),
    path("perfiles/nueva/", PerfilCreateView.as_view(), name="perfil_create"),
    path("perfiles/<int:pk>/", PerfilUpdateView.as_view(), name="perfil_update"),
    path("perfiles/<int:pk>/eliminar/", PerfilDeleteView.as_view(), name="perfil_delete"),
    path("ajustes/", AjustesView.as_view(), name="ajustes"),
    path("contrasena/", CambiarContrasenaView.as_view(), name="cambiar_contrasena"),
    path("copias/", CopiaListView.as_view(), name="copia_list"),
    path("copias/<str:nombre>/", CopiaDescargaView.as_view(), name="copia_descargar"),
    path("usuarios/imagen/<str:nombre>/", UsuarioImagenView.as_view(), name="usuario_imagen"),
]

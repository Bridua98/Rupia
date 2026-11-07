from configuracion.catalogo import pares_permiso
from configuracion.models import Perfil, PerfilPermiso

CLAVE_PRUEBA = "Clave-inicial-Rupia-2026"
PERFIL_ACCESO_TOTAL = "Acceso total"


def perfil_completo(descripcion=PERFIL_ACCESO_TOTAL):
    perfil, _ = Perfil.objects.get_or_create(
        descripcion=descripcion,
        defaults={"activo": True},
    )
    if not perfil.activo:
        perfil.activo = True
        perfil.save(update_fields=["activo"])
    existentes = set(perfil.permisos.values_list("formulario", "accion"))
    faltantes = [
        PerfilPermiso(perfil=perfil, formulario=formulario, accion=accion)
        for formulario, accion in pares_permiso()
        if (formulario, accion) not in existentes
    ]
    if faltantes:
        PerfilPermiso.objects.bulk_create(faltantes)
    return perfil


def crear_usuario_con_acceso(
    user_model,
    username="ada",
    email="ada@rupia.local",
    password=CLAVE_PRUEBA,
    **kwargs,
):
    user = user_model.objects.create_user(username, email, password, **kwargs)
    perfil_completo().usuarios.add(user)
    return user


def crear_usuario_con_permisos(
    user_model,
    *pares,
    username="cajero",
    email=None,
    password=CLAVE_PRUEBA,
    descripcion=None,
    **kwargs,
):
    user = user_model.objects.create_user(
        username, email or f"{username}@rupia.local", password, **kwargs
    )
    perfil = Perfil.objects.create(descripcion=descripcion or f"Perfil {username}")
    PerfilPermiso.objects.bulk_create(
        [
            PerfilPermiso(perfil=perfil, formulario=formulario, accion=accion)
            for formulario, accion in pares
        ]
    )
    perfil.usuarios.add(user)
    return user

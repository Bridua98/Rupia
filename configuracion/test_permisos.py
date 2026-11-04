import pytest
from django.contrib.auth.hashers import check_password

from configuracion.catalogo import FORMULARIOS, pares_permiso
from configuracion.models import Perfil, PerfilPermiso
from configuracion.permisos import tiene_permiso
from configuracion.testing import CLAVE_PRUEBA, crear_usuario_con_acceso, perfil_completo


@pytest.mark.django_db
def test_superusuario_tiene_todo(django_user_model):
    admin = django_user_model.objects.create_superuser(
        "admin", "admin@rupia.local", CLAVE_PRUEBA
    )
    assert tiene_permiso(admin, "personas", "eliminar")
    assert tiene_permiso(admin, "punto_de_venta", "cobrar")


@pytest.mark.django_db
def test_sin_perfil_no_entra_a_personas(client, django_user_model):
    user = django_user_model.objects.create_user("cajero", "cajero@rupia.local", CLAVE_PRUEBA)
    client.force_login(user)

    response = client.get("/personas/")

    assert response.status_code == 403
    assert "No tenés permiso" in response.content.decode()


@pytest.mark.django_db
def test_perfiles_se_unen(django_user_model):
    user = django_user_model.objects.create_user("cajero", "cajero@rupia.local", CLAVE_PRUEBA)
    pos = Perfil.objects.create(descripcion="Cajero")
    PerfilPermiso.objects.create(perfil=pos, formulario="punto_de_venta", accion="ver")
    personas = Perfil.objects.create(descripcion="Personas")
    PerfilPermiso.objects.create(perfil=personas, formulario="personas", accion="ver")
    pos.usuarios.add(user)
    personas.usuarios.add(user)

    assert tiene_permiso(user, "punto_de_venta", "ver")
    assert tiene_permiso(user, "personas", "ver")
    assert not tiene_permiso(user, "personas", "alta")


@pytest.mark.django_db
def test_perfil_inactivo_no_suma(django_user_model):
    user = django_user_model.objects.create_user("cajero", "cajero@rupia.local", CLAVE_PRUEBA)
    perfil = Perfil.objects.create(descripcion="Cajero", activo=False)
    PerfilPermiso.objects.create(perfil=perfil, formulario="punto_de_venta", accion="ver")
    perfil.usuarios.add(user)

    assert not tiene_permiso(user, "punto_de_venta", "ver")


@pytest.mark.django_db
def test_menu_filtra_por_ver(client, django_user_model):
    user = django_user_model.objects.create_user("cajero", "cajero@rupia.local", CLAVE_PRUEBA)
    perfil = Perfil.objects.create(descripcion="Cajero")
    PerfilPermiso.objects.create(perfil=perfil, formulario="punto_de_venta", accion="ver")
    perfil.usuarios.add(user)
    client.force_login(user)

    response = client.get("/")
    content = response.content.decode()

    assert "Punto de venta" in content
    assert 'href="/personas/"' not in content
    assert "Contraseña" in content
    assert "Cajero" in content


@pytest.mark.django_db
def test_alta_de_usuario_y_perfil(ingresada):
    response = ingresada.post(
        "/configuracion/perfiles/nueva/",
        {
            "descripcion": "Cajero",
            "activo": "on",
            "perm_punto_de_venta_ver": "on",
            "perm_punto_de_venta_cobrar": "on",
            "desde": "listado",
        },
    )
    assert response.status_code == 302
    perfil = Perfil.objects.get(descripcion="Cajero")
    acciones = set(perfil.permisos.values_list("formulario", "accion"))
    assert acciones == {("punto_de_venta", "ver"), ("punto_de_venta", "cobrar")}

    alta = ingresada.post(
        "/configuracion/usuarios/nueva/",
        {
            "username": "cajero",
            "first_name": "Ana",
            "email": "cajero@rupia.local",
            "is_active": "on",
            "password1": CLAVE_PRUEBA,
            "password2": CLAVE_PRUEBA,
            "perfiles": [str(perfil.pk)],
            "desde": "listado",
        },
    )
    assert alta.status_code == 302
    from django.contrib.auth import get_user_model

    creado = get_user_model().objects.get(username="cajero")
    assert creado.check_password(CLAVE_PRUEBA)
    assert list(creado.perfiles.all()) == [perfil]


@pytest.mark.django_db
def test_no_se_autoelimina(ingresada, usuario):
    response = ingresada.post(f"/configuracion/usuarios/{usuario.pk}/eliminar/")
    assert response.status_code == 302
    usuario.refresh_from_db()
    assert usuario.pk


@pytest.mark.django_db
def test_cambio_propio_y_reset(ingresada, usuario, django_user_model):
    propio = ingresada.post(
        "/configuracion/contrasena/",
        {
            "old_password": CLAVE_PRUEBA,
            "new_password1": "Otra-clave-Rupia-2026",
            "new_password2": "Otra-clave-Rupia-2026",
        },
    )
    assert propio.status_code == 302
    usuario.refresh_from_db()
    assert usuario.check_password("Otra-clave-Rupia-2026")

    otro = crear_usuario_con_acceso(
        django_user_model, username="otro", email="otro@rupia.local"
    )
    reset = ingresada.post(
        f"/configuracion/usuarios/{otro.pk}/contrasena/",
        {
            "password1": "Clave-nueva-Rupia-2026",
            "password2": "Clave-nueva-Rupia-2026",
        },
    )
    assert reset.status_code == 302
    otro.refresh_from_db()
    assert check_password("Clave-nueva-Rupia-2026", otro.password)


@pytest.mark.django_db
def test_cajero_no_exporta_ni_crea(client, django_user_model):
    user = django_user_model.objects.create_user("cajero", "cajero@rupia.local", CLAVE_PRUEBA)
    perfil = Perfil.objects.create(descripcion="Consulta")
    PerfilPermiso.objects.create(perfil=perfil, formulario="personas", accion="ver")
    perfil.usuarios.add(user)
    client.force_login(user)

    lista = client.get("/personas/")
    content = lista.content.decode()
    assert lista.status_code == 200
    assert "Nueva persona" not in content
    assert "exportar.xlsx" not in content

    alta = client.post("/personas/nueva/", {"razon_social": "X", "desde": "listado"})
    assert alta.status_code == 403

    exportar = client.get("/personas/exportar.xlsx")
    assert exportar.status_code == 403


@pytest.mark.django_db
def test_perfil_completo_cubre_el_catalogo():
    perfil = perfil_completo()
    otorgados = set(perfil.permisos.values_list("formulario", "accion"))
    assert otorgados == set(pares_permiso())
    assert len(FORMULARIOS) >= 10

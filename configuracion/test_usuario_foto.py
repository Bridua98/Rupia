import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from configuracion.fotos import resolver_foto
from configuracion.models import UsuarioFoto
from configuracion.testing import CLAVE_PRUEBA, crear_usuario_con_acceso


def _png(nombre="ada.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), (10, 80, 40)).save(buffer, format="PNG")
    return SimpleUploadedFile(nombre, buffer.getvalue(), content_type="image/png")


@pytest.fixture
def carpeta_fotos(tmp_path, settings):
    settings.RUPIA_IMAGENES_DIR = tmp_path
    return tmp_path


@pytest.mark.django_db
def test_el_inicio_muestra_software_paraguayo(client):
    content = client.get("/login/").content.decode()

    assert "Software 100% paraguayo" in content
    assert "bandera-py" in content


@pytest.mark.django_db
def test_la_barra_muestra_el_usuario(ingresada, usuario):
    content = ingresada.get("/").content.decode()

    assert 'class="topbar-user"' in content
    assert f'<span class="topbar-user-name">{usuario.username}</span>' in content
    assert 'class="session-avatar' in content


@pytest.mark.django_db
def test_alta_de_usuario_guarda_imagen(ingresada, carpeta_fotos, django_user_model):
    content = ingresada.get("/configuracion/usuarios/?nueva=1").content.decode()
    assert "data-imagen-input" in content
    assert 'enctype="multipart/form-data"' in content

    alta = ingresada.post(
        "/configuracion/usuarios/nueva/",
        {
            "username": "cajero",
            "first_name": "Ana",
            "email": "cajero@rupia.local",
            "is_active": "on",
            "password1": CLAVE_PRUEBA,
            "password2": CLAVE_PRUEBA,
            "imagen_archivo": _png("cajero.png"),
            "desde": "listado",
        },
    )
    assert alta.status_code == 302
    creado = django_user_model.objects.get(username="cajero")
    foto = UsuarioFoto.objects.get(usuario=creado)
    assert foto.imagen == f"usuario-{creado.pk}.png"
    assert (carpeta_fotos / "usuarios" / foto.imagen).is_file()

    ficha = ingresada.get(f"/configuracion/usuarios/?usuario={creado.pk}").content.decode()
    assert f"/configuracion/usuarios/imagen/{foto.imagen}/" in ficha

    imagen = ingresada.get(f"/configuracion/usuarios/imagen/{foto.imagen}/")
    assert imagen.status_code == 200
    assert b"".join(imagen.streaming_content) == (
        carpeta_fotos / "usuarios" / foto.imagen
    ).read_bytes()

    ingresada.force_login(creado)
    con_foto = ingresada.get("/").content.decode()
    assert f"/configuracion/usuarios/imagen/{foto.imagen}/" in con_foto
    assert "has-foto" in con_foto


@pytest.mark.django_db
def test_uno_elige_su_propia_imagen(ingresada, usuario, carpeta_fotos):
    pagina = ingresada.get("/configuracion/contrasena/")
    assert pagina.status_code == 200
    assert "Tu cuenta" in pagina.content.decode()
    assert "data-imagen-input" in pagina.content.decode()

    guardado = ingresada.post(
        "/configuracion/contrasena/",
        {"accion": "foto", "imagen_archivo": _png("yo.png")},
    )
    assert guardado.status_code == 302
    foto = UsuarioFoto.objects.get(usuario=usuario)
    assert foto.imagen == f"usuario-{usuario.pk}.png"
    assert (carpeta_fotos / "usuarios" / foto.imagen).is_file()


@pytest.mark.django_db
def test_quitar_imagen_borra_el_archivo(ingresada, usuario, carpeta_fotos):
    ingresada.post(
        "/configuracion/contrasena/",
        {"accion": "foto", "imagen_archivo": _png("yo.png")},
    )
    foto = UsuarioFoto.objects.get(usuario=usuario)
    destino = carpeta_fotos / "usuarios" / foto.imagen
    assert destino.is_file()

    quitar = ingresada.post(
        "/configuracion/contrasena/",
        {"accion": "foto", "quitar_imagen": "on"},
    )
    assert quitar.status_code == 302
    foto.refresh_from_db()
    assert foto.imagen == ""
    assert not destino.exists()


@pytest.mark.django_db
def test_la_foto_pide_ingreso(client, carpeta_fotos):
    response = client.get("/configuracion/usuarios/imagen/usuario-1.png/")
    assert response.status_code == 302
    assert response.url.startswith("/login/")


@pytest.mark.django_db
def test_no_sirve_una_ruta_fuera(ingresada, carpeta_fotos):
    assert resolver_foto("../secreto.png") is None
    assert resolver_foto("usuario-1.bmp") is None
    faltante = ingresada.get("/configuracion/usuarios/imagen/usuario-99.png/")
    assert faltante.status_code == 404


@pytest.mark.django_db
def test_otro_usuario_no_rompe_el_cambio_de_clave(ingresada, usuario, django_user_model):
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
    assert otro.check_password("Clave-nueva-Rupia-2026")

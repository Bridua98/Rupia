from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from core.management.commands.ensure_superuser import (
    DEFAULT_DEV_PASSWORD,
    DEFAULT_EMAIL,
    DEFAULT_USERNAME,
)


@pytest.fixture
def superuser_env(monkeypatch, settings):
    settings.DEBUG = True
    monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", DEFAULT_USERNAME)
    monkeypatch.setenv("DJANGO_SUPERUSER_EMAIL", DEFAULT_EMAIL)
    monkeypatch.delenv("DJANGO_SUPERUSER_PASSWORD", raising=False)


def test_la_documentacion_incluye_el_acceso_inicial():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text()
    example = (root / ".env.example").read_text()

    assert DEFAULT_USERNAME in readme
    assert DEFAULT_EMAIL in readme
    assert DEFAULT_DEV_PASSWORD in readme
    assert f"DJANGO_SUPERUSER_USERNAME={DEFAULT_USERNAME}" in example
    assert f"DJANGO_SUPERUSER_PASSWORD={DEFAULT_DEV_PASSWORD}" in example


@pytest.mark.django_db
def test_crea_el_superusuario_de_desarrollo(superuser_env):
    call_command("ensure_superuser")

    from django.contrib.auth import get_user_model

    user = get_user_model().objects.get(username=DEFAULT_USERNAME)
    assert user.is_superuser is True
    assert user.is_staff is True
    assert user.email == DEFAULT_EMAIL
    assert user.check_password(DEFAULT_DEV_PASSWORD)


@pytest.mark.django_db
def test_no_pisa_un_superusuario_existente(superuser_env):
    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    user_model.objects.create_superuser(DEFAULT_USERNAME, DEFAULT_EMAIL, "Otra-clave-segura-99")

    call_command("ensure_superuser")

    user = user_model.objects.get(username=DEFAULT_USERNAME)
    assert user.check_password("Otra-clave-segura-99")
    assert user_model.objects.count() == 1


@pytest.mark.django_db
def test_no_promueve_un_usuario_comun(superuser_env):
    from django.contrib.auth import get_user_model

    get_user_model().objects.create_user(DEFAULT_USERNAME, DEFAULT_EMAIL, DEFAULT_DEV_PASSWORD)

    with pytest.raises(CommandError, match="no es superusuario"):
        call_command("ensure_superuser")


@pytest.mark.django_db
def test_usa_la_contrasena_del_entorno(monkeypatch):
    monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", "root")
    monkeypatch.setenv("DJANGO_SUPERUSER_EMAIL", "root@rupia.local")
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "Otra-clave-distinta-88")

    call_command("ensure_superuser")

    from django.contrib.auth import get_user_model

    user = get_user_model().objects.get(username="root")
    assert user.check_password("Otra-clave-distinta-88")
    assert user.is_superuser is True


@pytest.mark.django_db
def test_fuera_de_desarrollo_la_contrasena_es_obligatoria(settings, monkeypatch):
    settings.DEBUG = False
    monkeypatch.delenv("DJANGO_SUPERUSER_PASSWORD", raising=False)

    with pytest.raises(CommandError, match="DJANGO_SUPERUSER_PASSWORD"):
        call_command("ensure_superuser")


@pytest.mark.django_db
def test_rechaza_una_contrasena_debil(monkeypatch):
    monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", DEFAULT_USERNAME)
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "123")

    with pytest.raises(CommandError, match="No se pudo crear"):
        call_command("ensure_superuser")

    from django.contrib.auth import get_user_model

    assert get_user_model().objects.filter(username=DEFAULT_USERNAME).exists() is False

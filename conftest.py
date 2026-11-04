import pytest

from configuracion.testing import crear_usuario_con_acceso


@pytest.fixture
def usuario(django_user_model):
    return crear_usuario_con_acceso(django_user_model)


@pytest.fixture
def ingresada(client, usuario):
    client.force_login(usuario)
    return client

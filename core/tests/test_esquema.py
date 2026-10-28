from importlib import import_module

import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import connection

TABLAS = {
    "auth_group": {"id", "name"},
    "auth_group_permissions": {"id", "group_id", "permission_id"},
    "auth_permission": {"id", "name", "content_type_id", "codename"},
    "auth_user": {
        "id",
        "password",
        "last_login",
        "is_superuser",
        "username",
        "first_name",
        "last_name",
        "email",
        "is_staff",
        "is_active",
        "date_joined",
    },
    "auth_user_groups": {"id", "user_id", "group_id"},
    "auth_user_user_permissions": {"id", "user_id", "permission_id"},
    "django_admin_log": {
        "id",
        "action_time",
        "object_id",
        "object_repr",
        "action_flag",
        "change_message",
        "content_type_id",
        "user_id",
    },
    "django_content_type": {"id", "app_label", "model"},
    "django_session": {"session_key", "session_data", "expire_date"},
}


def columnas(tabla):
    with connection.cursor() as cursor:
        descripcion = connection.introspection.get_table_description(cursor, tabla)
    return {columna.name for columna in descripcion}


def test_la_migracion_inicial_exige_el_esquema_de_django():
    migracion = import_module("core.migrations.0001_initial").Migration

    assert migracion.initial is True
    assert migracion.operations == []
    assert set(migracion.dependencies) == {
        ("admin", "0003_logentry_add_action_flag_choices"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("sessions", "0001_initial"),
    }


@pytest.mark.django_db
def test_migrate_crea_las_tablas_que_django_impacta():
    tablas = set(connection.introspection.table_names())

    for tabla, esperadas in TABLAS.items():
        assert tabla in tablas
        assert esperadas <= columnas(tabla)

    content_type = columnas("django_content_type")
    assert "name" not in content_type

    modelos = {
        ("admin", "logentry"),
        ("auth", "group"),
        ("auth", "permission"),
        ("auth", "user"),
        ("contenttypes", "contenttype"),
        ("sessions", "session"),
    }
    for app_label, model in modelos:
        tipo = ContentType.objects.get(app_label=app_label, model=model)
        for accion in ("add", "change", "delete", "view"):
            permiso = Permission.objects.filter(content_type=tipo, codename=f"{accion}_{model}")
            assert permiso.exists()

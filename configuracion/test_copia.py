import sqlite3
from datetime import datetime

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from configuracion.copia import (
    CopiaNoEncontrada,
    crear_copia,
    resolver_copia,
    respaldar_mysql,
)
from configuracion.testing import crear_usuario_con_permisos


class _Cursor:
    def __init__(self):
        self.sql = []
        self.modo = ""
        self._filas = [(1, "caja")]

    def execute(self, sql):
        self.sql.append(sql)
        if sql.startswith("SHOW FULL TABLES"):
            self.modo = "tablas"
        elif sql.startswith("SHOW CREATE TABLE"):
            self.modo = "crear"
        elif sql.startswith("SELECT"):
            self.modo = "filas"
        else:
            self.modo = ""

    def fetchall(self):
        if self.modo == "tablas":
            return [("caja", "BASE TABLE")]
        return []

    def fetchone(self):
        if self.modo == "crear":
            return ("caja", "CREATE TABLE `caja` (`id` int, `nombre` varchar(10))")
        return None

    def fetchmany(self, _tamano):
        if self.modo == "filas" and self._filas:
            filas = self._filas
            self._filas = []
            return filas
        return []

    @property
    def description(self):
        return [("id",), ("nombre",)]

    def close(self):
        return None


class _Crudo:
    def __init__(self):
        self._cursor = _Cursor()

    def cursor(self):
        return self._cursor

    def literal(self, valor):
        if isinstance(valor, str):
            return f"'{valor}'"
        return str(valor)


class _Conexion:
    vendor = "mysql"

    def __init__(self):
        self.connection = _Crudo()

    def ensure_connection(self):
        return None


@pytest.mark.django_db
def test_copia_sqlite_se_almacena_y_abre(settings, tmp_path):
    settings.RUPIA_COPIAS_DIR = tmp_path
    User.objects.create_user("copia", "copia@rupia.local", "Clave-inicial-Rupia-2026")

    copia = crear_copia(momento=timezone.make_aware(datetime(2026, 11, 9, 21, 51, 0)))

    destino = tmp_path / copia.nombre
    assert destino.is_file()
    assert copia.motor == "SQLite"
    assert copia.nombre == "rupia-20261109-215100.sqlite.sql"
    with sqlite3.connect(":memory:") as conexion:
        conexion.executescript(destino.read_text(encoding="utf-8"))
        existe = conexion.execute(
            "SELECT 1 FROM auth_user WHERE username = 'copia'"
        ).fetchone()
    assert existe == (1,)
    assert resolver_copia(copia.nombre) == destino.resolve()


@pytest.mark.django_db
def test_segunda_copia_en_el_mismo_segundo_no_pisa_la_primera(settings, tmp_path):
    settings.RUPIA_COPIAS_DIR = tmp_path
    momento = timezone.make_aware(datetime(2026, 11, 9, 21, 51, 0))

    primera = crear_copia(momento=momento)
    segunda = crear_copia(momento=momento)

    assert primera.nombre != segunda.nombre
    assert (tmp_path / primera.nombre).is_file()
    assert (tmp_path / segunda.nombre).is_file()


def test_volcado_mysql_incluye_estructura_y_datos(tmp_path):
    destino = tmp_path / "rupia.sql"

    respaldar_mysql(destino, _Conexion())

    texto = destino.read_text(encoding="utf-8")
    assert "SET FOREIGN_KEY_CHECKS=0;" in texto
    assert "DROP TABLE IF EXISTS `caja`;" in texto
    assert "CREATE TABLE `caja`" in texto
    assert "INSERT INTO `caja` (`id`, `nombre`) VALUES\n(1, 'caja');" in texto
    assert texto.rstrip().endswith("SET FOREIGN_KEY_CHECKS=1;")


def test_nombre_fuera_de_la_carpeta_no_se_resuelve():
    with pytest.raises(CopiaNoEncontrada):
        resolver_copia("../db.sqlite3")
    with pytest.raises(CopiaNoEncontrada):
        resolver_copia("rupia-20261109-215100.sqlite3")


@pytest.mark.django_db
def test_pantalla_crea_descarga_y_elimina(settings, tmp_path, ingresada):
    settings.RUPIA_COPIAS_DIR = tmp_path

    pagina = ingresada.get("/configuracion/copias/")
    assert pagina.status_code == 200
    assert "Crear copia" in pagina.content.decode()

    creada = ingresada.post("/configuracion/copias/")
    assert creada.status_code == 302
    archivo = next(tmp_path.iterdir())

    descarga = ingresada.get(f"/configuracion/copias/{archivo.name}/")
    assert descarga.status_code == 200
    assert archivo.name in descarga["Content-Disposition"]
    assert b"CREATE TABLE" in descarga.getvalue()

    eliminada = ingresada.post(
        "/configuracion/copias/",
        {"accion": "eliminar", "nombre": archivo.name},
    )
    assert eliminada.status_code == 302
    assert not archivo.exists()


@pytest.mark.django_db
def test_sin_permiso_no_entra(client, django_user_model):
    usuario = django_user_model.objects.create_user(
        "cajero", "cajero@rupia.local", "Clave-inicial-Rupia-2026"
    )
    client.force_login(usuario)

    assert client.get("/configuracion/copias/").status_code == 403


@pytest.mark.django_db
def test_ver_no_alcanza_para_crear(settings, tmp_path, client, django_user_model):
    settings.RUPIA_COPIAS_DIR = tmp_path
    usuario = crear_usuario_con_permisos(
        django_user_model,
        ("copias", "ver"),
        username="lector",
    )
    client.force_login(usuario)

    respuesta = client.post("/configuracion/copias/")

    assert respuesta.status_code == 403
    assert list(tmp_path.iterdir()) == []


@pytest.mark.django_db
def test_menu_muestra_la_copia(ingresada):
    menu = ingresada.get("/").context["menu"]
    configuracion = next(entrada for entrada in menu if entrada["label"] == "Configuración")
    etiquetas = [hijo["label"] for hijo in configuracion["children"]]

    assert "Copia de seguridad" in etiquetas

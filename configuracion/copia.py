import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.utils import timezone

logger = logging.getLogger(__name__)

PATRON_COPIA = re.compile(r"^rupia-(\d{8})-(\d{6})(?:-(\d+))?\.(sqlite|mysql)\.sql$")
MOTORES = {"sqlite": "SQLite", "mysql": "MySQL"}
EXTENSIONES = {"sqlite": "sqlite.sql", "mysql": "mysql.sql"}
ENCABEZADO_MYSQL = (
    "-- Copia de seguridad Rupia (MySQL)\n"
    "SET NAMES utf8mb4;\n"
    "SET FOREIGN_KEY_CHECKS=0;\n"
    "SET UNIQUE_CHECKS=0;\n"
    "SET SQL_MODE='NO_AUTO_VALUE_ON_ZERO';\n"
)
PIE_MYSQL = "SET UNIQUE_CHECKS=1;\nSET FOREIGN_KEY_CHECKS=1;\n"


class CopiaError(Exception):
    pass


class CopiaNoEncontrada(CopiaError):
    pass


@dataclass(frozen=True)
class Copia:
    nombre: str
    momento: datetime
    indice: int
    motor: str
    tamano: int
    tamano_texto: str

    @property
    def fecha(self) -> str:
        return self.momento.strftime("%d/%m/%Y %H:%M:%S")


def carpeta_copias() -> Path:
    return Path(settings.RUPIA_COPIAS_DIR)


def listar_copias() -> list[Copia]:
    carpeta = carpeta_copias()
    if not carpeta.is_dir():
        return []
    copias = []
    for path in carpeta.iterdir():
        copia = describir_copia(path)
        if copia is not None:
            copias.append(copia)
    copias.sort(key=lambda copia: (copia.momento, copia.indice), reverse=True)
    return copias


def describir_copia(path: Path) -> Copia | None:
    coincidencia = PATRON_COPIA.fullmatch(path.name)
    if coincidencia is None or not path.is_file():
        return None
    momento = datetime.strptime(coincidencia.group(1) + coincidencia.group(2), "%Y%m%d%H%M%S")
    tamano = path.stat().st_size
    return Copia(
        nombre=path.name,
        momento=momento,
        indice=int(coincidencia.group(3) or 1),
        motor=MOTORES[coincidencia.group(4)],
        tamano=tamano,
        tamano_texto=tamano_legible(tamano),
    )


def resolver_copia(nombre: str) -> Path:
    if PATRON_COPIA.fullmatch(nombre) is None or nombre != Path(nombre).name:
        raise CopiaNoEncontrada(nombre)
    carpeta = carpeta_copias().resolve()
    destino = (carpeta / nombre).resolve()
    if destino.parent != carpeta or not destino.is_file():
        raise CopiaNoEncontrada(nombre)
    return destino


def eliminar_copia(nombre: str) -> None:
    resolver_copia(nombre).unlink()


def crear_copia(*, momento: datetime | None = None) -> Copia:
    motor = connection.vendor
    extension = EXTENSIONES.get(motor)
    if extension is None:
        raise CopiaError("No hay copia de seguridad para este motor de base de datos.")
    carpeta = carpeta_copias()
    carpeta.mkdir(parents=True, exist_ok=True)
    cuando = timezone.localtime(momento or timezone.now())
    nombre = _nombre_libre(carpeta, cuando, extension)
    destino = carpeta / nombre
    temporal = carpeta / f"{nombre}.parcial"
    try:
        if motor == "sqlite":
            respaldar_sqlite(temporal, connection)
        else:
            respaldar_mysql(temporal, connection)
        temporal.replace(destino)
    except CopiaError:
        temporal.unlink(missing_ok=True)
        raise
    except Exception as exc:
        temporal.unlink(missing_ok=True)
        logger.exception("No se pudo crear la copia de seguridad")
        raise CopiaError("No se pudo crear la copia de seguridad.") from exc
    copia = describir_copia(destino)
    if copia is None:
        raise CopiaError("No se pudo crear la copia de seguridad.")
    return copia


def respaldar_sqlite(destino: Path, conexion) -> None:
    conexion.ensure_connection()
    origen = conexion.connection
    with destino.open("w", encoding="utf-8", newline="\n") as archivo:
        archivo.write("-- Copia de seguridad Rupia (SQLite)\n")
        for linea in origen.iterdump():
            archivo.write(f"{linea}\n")


def respaldar_mysql(destino: Path, conexion) -> None:
    conexion.ensure_connection()
    crudo = conexion.connection
    if not hasattr(crudo, "literal") or not hasattr(crudo, "cursor"):
        raise CopiaError("No se pudo preparar la copia de MySQL.")
    cursor = crudo.cursor()
    try:
        _instantanea(cursor)
        cursor.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
        tablas = [fila[0] for fila in cursor.fetchall()]
        with destino.open("w", encoding="utf-8", newline="\n") as archivo:
            archivo.write(ENCABEZADO_MYSQL)
            for tabla in tablas:
                _volcar_tabla(archivo, cursor, crudo, _texto(tabla))
            archivo.write(PIE_MYSQL)
    finally:
        try:
            cursor.execute("ROLLBACK")
        except Exception:
            logger.warning("No se pudo cerrar la transacción de la copia MySQL", exc_info=True)
        cursor.close()


def tamano_legible(nbytes: int) -> str:
    valor = float(nbytes)
    for unidad in ("B", "KB", "MB", "GB"):
        if valor < 1024 or unidad == "GB":
            if unidad == "B":
                return f"{int(valor)} B"
            return f"{valor:.1f}".replace(".", ",") + f" {unidad}"
        valor /= 1024
    return f"{int(nbytes)} B"


def _nombre_libre(carpeta: Path, momento: datetime, extension: str) -> str:
    base = f"rupia-{momento:%Y%m%d-%H%M%S}"
    candidato = f"{base}.{extension}"
    indice = 2
    while (carpeta / candidato).exists() or (carpeta / f"{candidato}.parcial").exists():
        candidato = f"{base}-{indice}.{extension}"
        indice += 1
    return candidato


def _instantanea(cursor) -> None:
    try:
        cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        cursor.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT")
    except Exception:
        logger.warning("La copia de MySQL sigue sin instantánea consistente", exc_info=True)
        try:
            cursor.execute("ROLLBACK")
        except Exception:
            logger.warning("No se pudo descartar la transacción de la copia", exc_info=True)


def _volcar_tabla(archivo, cursor, crudo, tabla: str) -> None:
    citada = _citar(tabla)
    cursor.execute(f"SHOW CREATE TABLE {citada}")
    fila = cursor.fetchone()
    if not fila or len(fila) < 2:
        raise CopiaError(f"No se pudo leer la estructura de {tabla}.")
    creacion = _texto(fila[1]).rstrip().rstrip(";")
    archivo.write(f"DROP TABLE IF EXISTS {citada};\n{creacion};\n\n")
    cursor.execute(f"SELECT * FROM {citada}")
    columnas = [_texto(item[0]) for item in cursor.description]
    while True:
        filas = cursor.fetchmany(200)
        if not filas:
            break
        _insertar(archivo, citada, columnas, filas, crudo)


def _insertar(archivo, tabla_citada: str, columnas: list[str], filas, crudo) -> None:
    columnas_sql = ", ".join(_citar(columna) for columna in columnas)
    for inicio in range(0, len(filas), 100):
        grupo = filas[inicio : inicio + 100]
        valores = []
        for fila in grupo:
            celdas = ", ".join(_literal(crudo, valor) for valor in fila)
            valores.append(f"({celdas})")
        archivo.write(
            f"INSERT INTO {tabla_citada} ({columnas_sql}) VALUES\n" + ",\n".join(valores) + ";\n"
        )
    archivo.write("\n")


def _literal(crudo, valor) -> str:
    if valor is None:
        return "NULL"
    texto = crudo.literal(valor)
    if isinstance(texto, bytes):
        return texto.decode("utf-8")
    return str(texto)


def _citar(nombre: str) -> str:
    return "`" + nombre.replace("`", "``") + "`"


def _texto(valor) -> str:
    if isinstance(valor, bytes):
        return valor.decode("utf-8")
    return str(valor)

from dataclasses import dataclass


@dataclass(frozen=True)
class Accion:
    clave: str
    etiqueta: str


@dataclass(frozen=True)
class Formulario:
    clave: str
    etiqueta: str
    acciones: tuple[Accion, ...]


ACCION_VER = Accion("ver", "Ver")
ACCION_ALTA = Accion("alta", "Alta")
ACCION_MODIFICAR = Accion("modificar", "Modificar")
ACCION_ELIMINAR = Accion("eliminar", "Eliminar")
ACCION_EXPORTAR = Accion("exportar", "Exportar")
ACCION_COBRAR = Accion("cobrar", "Cobrar")
ACCION_CANCELAR = Accion("cancelar", "Cancelar")
ACCION_ANULAR = Accion("anular", "Anular")
ACCION_CLAVE = Accion("clave", "Cambiar contraseña")

ACCIONES_MANTENIMIENTO = (
    ACCION_VER,
    ACCION_ALTA,
    ACCION_MODIFICAR,
    ACCION_ELIMINAR,
    ACCION_EXPORTAR,
)


FORMULARIOS = (
    Formulario(
        "punto_de_venta",
        "Punto de venta",
        (ACCION_VER, ACCION_COBRAR, ACCION_CANCELAR),
    ),
    Formulario(
        "ventas",
        "Ventas",
        (ACCION_VER, ACCION_ANULAR, ACCION_EXPORTAR),
    ),
    Formulario(
        "compras",
        "Compras",
        (ACCION_VER, ACCION_ALTA, ACCION_CANCELAR, ACCION_ANULAR, ACCION_EXPORTAR),
    ),
    Formulario("personas", "Personas", ACCIONES_MANTENIMIENTO),
    Formulario("cuentas", "Cuentas", ACCIONES_MANTENIMIENTO),
    Formulario(
        "transferencias",
        "Transferencias",
        (ACCION_VER, ACCION_ALTA, ACCION_ANULAR, ACCION_EXPORTAR),
    ),
    Formulario(
        "reporte_disponibilidad",
        "Disponibilidad",
        (ACCION_VER, ACCION_EXPORTAR),
    ),
    Formulario(
        "reporte_gastos",
        "Informe de gastos",
        (ACCION_VER, ACCION_EXPORTAR),
    ),
    Formulario(
        "pagos_proveedor",
        "Pagos a proveedor",
        (ACCION_VER, ACCION_ALTA, ACCION_ANULAR, ACCION_EXPORTAR),
    ),
    Formulario(
        "reporte_cuentas_pagar",
        "Cuentas a pagar",
        (ACCION_VER, ACCION_EXPORTAR),
    ),
    Formulario(
        "comandas",
        "Comandas",
        (ACCION_VER, ACCION_ALTA, ACCION_ANULAR),
    ),
    Formulario("mesas", "Mesas", ACCIONES_MANTENIMIENTO),
    Formulario("sectores", "Sectores de preparación", ACCIONES_MANTENIMIENTO),
    Formulario("timbrados", "Timbrados", ACCIONES_MANTENIMIENTO),
    Formulario("maquinas", "Máquinas", ACCIONES_MANTENIMIENTO),
    Formulario("marcas", "Marcas", ACCIONES_MANTENIMIENTO),
    Formulario("categorias", "Categorías", ACCIONES_MANTENIMIENTO),
    Formulario("unidades", "Unidades de medida", ACCIONES_MANTENIMIENTO),
    Formulario("unidades_negocio", "Unidades de negocio", ACCIONES_MANTENIMIENTO),
    Formulario("items", "Ítems", ACCIONES_MANTENIMIENTO),
    Formulario("ajustes_stock", "Ajustes de stock", ACCIONES_MANTENIMIENTO),
    Formulario(
        "precios",
        "Precios",
        (ACCION_VER, ACCION_MODIFICAR, ACCION_EXPORTAR),
    ),
    Formulario(
        "reporte_productos",
        "Reporte de productos",
        (ACCION_VER, ACCION_EXPORTAR),
    ),
    Formulario("reporte_stock", "Stock", (ACCION_VER, ACCION_EXPORTAR)),
    Formulario(
        "usuarios",
        "Usuarios",
        ACCIONES_MANTENIMIENTO + (ACCION_CLAVE,),
    ),
    Formulario("perfiles", "Perfiles", ACCIONES_MANTENIMIENTO),
    Formulario("ajustes", "Ajustes generales", (ACCION_VER, ACCION_MODIFICAR)),
    Formulario(
        "copias",
        "Copia de seguridad",
        (ACCION_VER, ACCION_ALTA, ACCION_ELIMINAR),
    ),
)

FORMULARIOS_POR_CLAVE = {formulario.clave: formulario for formulario in FORMULARIOS}


def campo_permiso(formulario: str, accion: str) -> str:
    return f"perm_{formulario}_{accion}"


def pares_permiso():
    for formulario in FORMULARIOS:
        for accion in formulario.acciones:
            yield formulario.clave, accion.clave


COLUMNAS_MATRIZ = (
    ACCION_VER,
    ACCION_ALTA,
    ACCION_MODIFICAR,
    ACCION_ELIMINAR,
    ACCION_EXPORTAR,
    ACCION_COBRAR,
    ACCION_CANCELAR,
    ACCION_ANULAR,
    ACCION_CLAVE,
)


def accion_permitida(formulario: str, accion: str) -> bool:
    spec = FORMULARIOS_POR_CLAVE.get(formulario)
    if spec is None:
        return False
    return any(item.clave == accion for item in spec.acciones)


def matriz_permisos(form):
    filas = []
    for formulario in FORMULARIOS:
        disponibles = {accion.clave for accion in formulario.acciones}
        celdas = []
        for columna in COLUMNAS_MATRIZ:
            if columna.clave in disponibles:
                celdas.append(form[campo_permiso(formulario.clave, columna.clave)])
            else:
                celdas.append(None)
        filas.append({"etiqueta": formulario.etiqueta, "celdas": celdas})
    return COLUMNAS_MATRIZ, filas

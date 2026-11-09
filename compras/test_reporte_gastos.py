from datetime import timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from django.utils import timezone
from openpyxl import load_workbook

from compras.models import Compra, CompraDetalle, EstadoCompra, TipoCompra
from cuentas.models import Cuenta
from inventario.models import (
    Item,
    ItemCategoria,
    Marca,
    TasaIva,
    TipoItem,
    UnidadMedida,
)
from negocio.models import UnidadNegocio
from personas.models import Genero, Persona, TipoDocumento


def _hoy():
    return timezone.localdate()


def _cuenta(nombre="Caja gastos", corto="GASTOS"):
    return Cuenta.objects.create(descripcion=nombre, nombre_corto=corto)


def _proveedor(nombre="Proveedor SA", documento="80001111-2"):
    return Persona.objects.create(
        tipo_documento=TipoDocumento.RUC,
        documento=documento,
        razon_social=nombre,
        genero=Genero.SIN_DEFINIR,
        direccion="Centro",
        es_proveedor=True,
    )


def _negocio(abreviado="DEP", descripcion="Depósito"):
    unidad, _ = UnidadNegocio.objects.get_or_create(
        abreviado=abreviado,
        defaults={"descripcion": descripcion},
    )
    return unidad


def _unidad():
    unidad, _ = UnidadMedida.objects.get_or_create(
        descripcion="Unidad",
        defaults={"simbolo": "Un"},
    )
    return unidad


def _item(descripcion, tipo, negocio=None):
    marca, _ = Marca.objects.get_or_create(descripcion="Genérica")
    categoria, _ = ItemCategoria.objects.get_or_create(descripcion="General")
    datos = {
        "marca": marca,
        "categoria": categoria,
        "unidad_medida": _unidad(),
        "descripcion": descripcion,
        "tipo": tipo,
        "activo": True,
        "tasa_iva": TasaIva.DIEZ,
        "precio": Decimal("1000"),
    }
    if tipo == TipoItem.PRODUCTO:
        datos["unidad_negocio"] = negocio or _negocio()
    return Item.objects.create(**datos)


def _compra(usuario, cuenta, proveedor, *, estado, tipo, numero, fecha, pk=None):
    datos = {
        "fecha": fecha,
        "estado": estado,
        "tipo": tipo,
        "proveedor": proveedor,
        "cuenta": cuenta,
        "usuario": usuario,
        "timbrado": "12345678" if numero else "",
        "establecimiento": "001" if numero else "",
        "punto_codigo": "001" if numero else "",
        "secuencial": 1 if numero else None,
        "numero_completo": numero,
    }
    if pk is not None:
        datos["id"] = pk
    return Compra.objects.create(**datos)


def _linea(compra, item, negocio, *, cantidad="1", costo="11000", subtotal="11000"):
    return CompraDetalle.objects.create(
        compra=compra,
        item=item,
        unidad_medida=item.unidad_medida,
        unidad_negocio=negocio,
        cantidad=Decimal(cantidad),
        costo=Decimal(costo),
        tasa_iva=TasaIva.DIEZ,
        subtotal=Decimal(subtotal),
    )


@pytest.mark.django_db
def test_informe_pide_ingreso(client):
    response = client.get("/compras/reportes/gastos/")

    assert response.status_code == 302
    assert response.url.startswith("/login/")


@pytest.mark.django_db
def test_menu_muestra_informe(ingresada):
    content = ingresada.get("/").content.decode()

    assert 'href="/compras/reportes/gastos/"' in content
    assert "Informe de gastos" in content


@pytest.mark.django_db
def test_incluye_gastos_y_mercaderia_confirmados(ingresada, usuario):
    cuenta = _cuenta()
    proveedor = _proveedor()
    deposito = _negocio()
    mercaderia = _item("Arroz", TipoItem.PRODUCTO, deposito)
    gasto = _item("Flete", TipoItem.GASTO)
    confirmada = _compra(
        usuario,
        cuenta,
        proveedor,
        estado=EstadoCompra.CONFIRMADA,
        tipo=TipoCompra.FACTURA_CONTADO,
        numero="001-001-0000001",
        fecha=_hoy(),
    )
    anulada = _compra(
        usuario,
        cuenta,
        proveedor,
        estado=EstadoCompra.ANULADA,
        tipo=TipoCompra.FACTURA_CONTADO,
        numero="001-001-0000002",
        fecha=_hoy(),
    )
    borrador = _compra(
        usuario,
        cuenta,
        proveedor,
        estado=EstadoCompra.EN_CURSO,
        tipo=TipoCompra.EGRESO,
        numero=None,
        fecha=_hoy(),
    )
    _linea(confirmada, mercaderia, deposito)
    _linea(confirmada, gasto, deposito, costo="5500", subtotal="5500")
    _linea(anulada, gasto, deposito)
    _linea(borrador, mercaderia, deposito)

    response = ingresada.get("/compras/reportes/gastos/")

    content = response.content.decode()
    cuerpo = content.split("<tbody>")[1].split("</tbody>")[0]
    assert response.status_code == 200
    assert "Arroz" in cuerpo
    assert "Flete" in cuerpo
    assert "Mercadería" in cuerpo
    assert "Gasto" in cuerpo
    assert "001-001-0000001" in cuerpo
    assert "Factura contado" in cuerpo
    assert "Caja gastos" in cuerpo
    assert "Depósito" in cuerpo
    assert "001-001-0000002" not in content
    assert "2 líneas" in content
    assert "sheet-total" in content


@pytest.mark.django_db
def test_filtra_por_cuenta_y_clase(ingresada, usuario):
    caja = _cuenta("Caja chica", "CHICA")
    banco = _cuenta("Banco", "BANCO")
    proveedor = _proveedor()
    deposito = _negocio()
    mercaderia = _item("Aceite", TipoItem.PRODUCTO, deposito)
    gasto = _item("Luz", TipoItem.GASTO)
    compra_caja = _compra(
        usuario,
        caja,
        proveedor,
        estado=EstadoCompra.CONFIRMADA,
        tipo=TipoCompra.EGRESO,
        numero=None,
        fecha=_hoy(),
    )
    compra_banco = _compra(
        usuario,
        banco,
        proveedor,
        estado=EstadoCompra.CONFIRMADA,
        tipo=TipoCompra.FACTURA_CREDITO,
        numero="001-001-0000099",
        fecha=_hoy(),
    )
    _linea(compra_caja, gasto, deposito)
    _linea(compra_banco, mercaderia, deposito)

    response = ingresada.get(
        f"/compras/reportes/gastos/?compra__cuenta={caja.pk}&item__tipo={TipoItem.GASTO}"
    )

    cuerpo = response.content.decode().split("<tbody>")[1].split("</tbody>")[0]
    assert "Luz" in cuerpo
    assert "Aceite" not in cuerpo
    assert "Egreso" in cuerpo
    assert "Cuenta: Caja chica" in response.content.decode()


@pytest.mark.django_db
def test_agrupa_por_unidad_cuenta_y_producto(ingresada, usuario):
    cuenta = _cuenta()
    otra = _cuenta("Banco Norte", "NORTE")
    proveedor = _proveedor()
    lacteos = _negocio("LAC", "Lácteos")
    limpieza = _negocio("LIM", "Limpieza")
    leche = _item("Leche", TipoItem.PRODUCTO, lacteos)
    jabon = _item("Jabón", TipoItem.PRODUCTO, limpieza)
    compra = _compra(
        usuario,
        cuenta,
        proveedor,
        estado=EstadoCompra.CONFIRMADA,
        tipo=TipoCompra.FACTURA_CONTADO,
        numero="001-001-0000007",
        fecha=_hoy(),
    )
    otra_compra = _compra(
        usuario,
        otra,
        proveedor,
        estado=EstadoCompra.CONFIRMADA,
        tipo=TipoCompra.FACTURA_CONTADO,
        numero="001-001-0000008",
        fecha=_hoy(),
    )
    _linea(compra, leche, lacteos, cantidad="2", costo="11000", subtotal="22000")
    _linea(compra, jabon, limpieza)
    _linea(otra_compra, jabon, limpieza)

    por_unidad = ingresada.get("/compras/reportes/gastos/?agrupar=unidad")
    cuerpo_unidad = por_unidad.content.decode().split("<tbody>")[1].split("</tbody>")[0]
    assert "Por unidad de negocio" in por_unidad.content.decode()
    assert "Lácteos" in cuerpo_unidad
    assert "Limpieza" in cuerpo_unidad
    assert "Leche" not in cuerpo_unidad
    assert "2 filas" in por_unidad.content.decode()

    por_cuenta = ingresada.get("/compras/reportes/gastos/?agrupar=cuenta")
    cuerpo_cuenta = por_cuenta.content.decode().split("<tbody>")[1].split("</tbody>")[0]
    assert "Caja gastos" in cuerpo_cuenta
    assert "Banco Norte" in cuerpo_cuenta
    assert "2 filas" in por_cuenta.content.decode()

    por_producto = ingresada.get("/compras/reportes/gastos/?agrupar=producto")
    cuerpo_producto = por_producto.content.decode().split("<tbody>")[1].split("</tbody>")[0]
    assert "Jabón" in cuerpo_producto
    assert "Leche" in cuerpo_producto
    assert "001-001-0000007" not in cuerpo_producto
    assert "2 filas" in por_producto.content.decode()


@pytest.mark.django_db
def test_comprobante_abre_la_compra(ingresada, usuario):
    cuenta = _cuenta()
    proveedor = _proveedor()
    deposito = _negocio()
    item = _item("Arroz", TipoItem.PRODUCTO, deposito)
    compra = _compra(
        usuario,
        cuenta,
        proveedor,
        estado=EstadoCompra.CONFIRMADA,
        tipo=TipoCompra.FACTURA_CONTADO,
        numero="001-001-0000001",
        fecha=_hoy(),
    )
    _linea(compra, item, deposito)

    content = ingresada.get("/compras/reportes/gastos/").content.decode()
    cuerpo = content.split("<tbody>")[1].split("</tbody>")[0]

    assert f'href="/compras/?compra={compra.pk}&amp;ver=1"' in cuerpo
    assert "sheet-origen" in cuerpo

    agrupado = ingresada.get("/compras/reportes/gastos/?agrupar=producto").content.decode()
    cuerpo_agrupado = agrupado.split("<tbody>")[1].split("</tbody>")[0]
    assert "sheet-origen" not in cuerpo_agrupado
    assert f'href="/compras/?compra={compra.pk}' not in cuerpo_agrupado


@pytest.mark.django_db
def test_excel_separa_gravado_e_iva(ingresada, usuario):
    cuenta = _cuenta()
    proveedor = _proveedor()
    deposito = _negocio()
    item = _item("Azúcar", TipoItem.PRODUCTO, deposito)
    compra = _compra(
        usuario,
        cuenta,
        proveedor,
        estado=EstadoCompra.CONFIRMADA,
        tipo=TipoCompra.FACTURA_CONTADO,
        numero="001-001-0000010",
        fecha=_hoy(),
    )
    _linea(compra, item, deposito, subtotal="11000", costo="11000")

    response = ingresada.get("/compras/reportes/gastos/exportar.xlsx")

    assert response.status_code == 200
    hoja = load_workbook(BytesIO(response.content)).active
    headers = [celda.value for celda in hoja[1]]
    gravado = headers.index("Gravado") + 1
    iva = headers.index("IVA") + 1
    total = headers.index("Total") + 1
    assert hoja.cell(2, gravado).value == "Gs. 10.000"
    assert hoja.cell(2, iva).value == "Gs. 1.000"
    assert hoja.cell(2, total).value == "Gs. 11.000"
    assert hoja.cell(hoja.max_row, 1).value == "Total"
    assert hoja.cell(hoja.max_row, total).value == "Gs. 11.000"


@pytest.mark.django_db
def test_imprimir_incluye_comprobante(ingresada, usuario):
    cuenta = _cuenta()
    proveedor = _proveedor()
    deposito = _negocio()
    item = _item("Flete interno", TipoItem.GASTO)
    compra = _compra(
        usuario,
        cuenta,
        proveedor,
        estado=EstadoCompra.CONFIRMADA,
        tipo=TipoCompra.EGRESO,
        numero=None,
        fecha=_hoy(),
    )
    _linea(compra, item, deposito)

    response = ingresada.get("/compras/reportes/gastos/imprimir/")

    content = response.content.decode()
    assert response.status_code == 200
    assert "Informe de gastos" in content
    assert f"Egreso {compra.pk}" in content
    assert "Flete interno" in content
    assert "Total" in content


@pytest.mark.django_db
def test_por_defecto_filtra_el_mes_en_curso(ingresada, usuario):
    cuenta = _cuenta()
    proveedor = _proveedor()
    deposito = _negocio()
    actual = _item("Gasto del mes", TipoItem.GASTO)
    anterior = _item("Gasto anterior", TipoItem.GASTO)
    hoy = _hoy()
    mes_anterior = hoy.replace(day=1) - timedelta(days=1)
    compra_mes = _compra(
        usuario,
        cuenta,
        proveedor,
        estado=EstadoCompra.CONFIRMADA,
        tipo=TipoCompra.EGRESO,
        numero=None,
        fecha=hoy,
        pk=21,
    )
    compra_antes = _compra(
        usuario,
        cuenta,
        proveedor,
        estado=EstadoCompra.CONFIRMADA,
        tipo=TipoCompra.EGRESO,
        numero=None,
        fecha=mes_anterior,
        pk=22,
    )
    _linea(compra_mes, actual, deposito)
    _linea(compra_antes, anterior, deposito)

    content = ingresada.get("/compras/reportes/gastos/").content.decode()
    cuerpo = content.split("<tbody>")[1].split("</tbody>")[0]
    assert "Gasto del mes" in cuerpo
    assert "Gasto anterior" not in cuerpo
    assert f'value="{hoy.replace(day=1).isoformat()}"' in content
    assert f'value="{hoy.isoformat()}"' in content

    amplio = ingresada.get(
        f"/compras/reportes/gastos/?fecha_desde={mes_anterior.isoformat()}"
        f"&fecha_hasta={hoy.isoformat()}"
    ).content.decode()
    assert "Gasto del mes" in amplio
    assert "Gasto anterior" in amplio

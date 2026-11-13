from datetime import timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from django.utils import timezone
from openpyxl import load_workbook

from cuentas.models import Cuenta
from inventario.models import Item, ItemCategoria, Marca, TasaIva, TipoItem, UnidadMedida
from negocio.models import UnidadNegocio
from personas.models import Genero, Persona, TipoDocumento
from ventas.cobro import agregar_producto
from ventas.models import EstadoVenta, MedioPago, TipoComprobante, Venta


def _hoy():
    return timezone.localdate()


def _marca(descripcion="Genérica"):
    marca, _ = Marca.objects.get_or_create(descripcion=descripcion)
    return marca


def _categoria(descripcion="Alimentos"):
    categoria, _ = ItemCategoria.objects.get_or_create(descripcion=descripcion)
    return categoria


def _unidad():
    unidad, _ = UnidadMedida.objects.get_or_create(descripcion="Unidad", defaults={"simbolo": "Un"})
    return unidad


def _negocio(abreviado="DEP", descripcion="Depósito"):
    negocio, _ = UnidadNegocio.objects.get_or_create(
        abreviado=abreviado,
        defaults={"descripcion": descripcion},
    )
    return negocio


def _cuenta(nombre="Caja ventas", corto="VENTAS"):
    return Cuenta.objects.create(descripcion=nombre, nombre_corto=corto)


def _item(**extra):
    datos = {
        "marca": extra.pop("marca", None) or _marca(),
        "categoria": extra.pop("categoria", None) or _categoria(),
        "unidad_medida": extra.pop("unidad_medida", None) or _unidad(),
        "codigo_barra": extra.pop("codigo_barra", "PROD-001"),
        "descripcion": extra.pop("descripcion", "Bombón de helado"),
        "tipo": TipoItem.PRODUCTO,
        "activo": True,
        "precio": extra.pop("precio", Decimal("11000")),
        "tasa_iva": extra.pop("tasa_iva", TasaIva.DIEZ),
        "ultimo_costo": Decimal("8000"),
    }
    if "unidad_negocio" not in extra:
        datos["unidad_negocio"] = _negocio()
    datos.update(extra)
    return Item.objects.create(**datos)


def _cliente(nombre="Cliente SA", documento="80009735-8"):
    return Persona.objects.create(
        tipo_documento=TipoDocumento.RUC,
        documento=documento,
        razon_social=nombre,
        genero=Genero.SIN_DEFINIR,
        direccion="Centro",
        es_cliente=True,
    )


def _cobrar(
    usuario,
    *items,
    fecha=None,
    descuento=Decimal("0"),
    cliente=None,
    medio=None,
    caja=None,
):
    venta = Venta.objects.create(
        fecha=fecha or _hoy(),
        usuario=usuario,
        descuento=descuento,
        tipo_comprobante=TipoComprobante.TICKET,
        cliente=cliente,
        medio=medio or MedioPago.EFECTIVO,
        caja=caja,
    )
    for item in items:
        agregar_producto(venta, item=item)
    venta.estado = EstadoVenta.COBRADA
    venta.numero_completo = f"001-001-{venta.pk:07d}"
    venta.save(update_fields=["estado", "numero_completo"])
    return venta


def _cuerpo(content):
    return content.split("<tbody>")[1].split("</tbody>")[0]


@pytest.mark.django_db
def test_informe_pide_ingreso(client):
    response = client.get("/ventas/reportes/ventas/")

    assert response.status_code == 302
    assert response.url.startswith("/login/")


@pytest.mark.django_db
def test_menu_muestra_informe(ingresada):
    content = ingresada.get("/").content.decode()

    assert 'href="/ventas/reportes/ventas/"' in content
    assert "Informe de ventas" in content


@pytest.mark.django_db
def test_solo_incluye_ventas_cobradas(ingresada, usuario):
    item = _item()
    cobrada = _cobrar(usuario, item, cliente=_cliente())
    anulada = _cobrar(usuario, item)
    anulada.estado = EstadoVenta.ANULADA
    anulada.save(update_fields=["estado"])
    en_curso = Venta.objects.create(
        fecha=_hoy(),
        usuario=usuario,
        tipo_comprobante=TipoComprobante.TICKET,
    )
    agregar_producto(en_curso, item=item)

    response = ingresada.get("/ventas/reportes/ventas/")
    cuerpo = _cuerpo(response.content.decode())

    assert response.status_code == 200
    assert cobrada.numero_completo in cuerpo
    assert anulada.numero_completo not in cuerpo
    assert "En curso" not in cuerpo


@pytest.mark.django_db
def test_descuento_de_cabecera_se_prorratea_aunque_se_filtre_un_producto(ingresada, usuario):
    diez = _item(descripcion="Diez", codigo_barra="T10", precio=Decimal("11000"))
    cinco = _item(descripcion="Cinco", codigo_barra="T5", precio=Decimal("21000"))
    _cobrar(usuario, diez, cinco, descuento=Decimal("3200"), cliente=_cliente())

    completo = ingresada.get("/ventas/reportes/ventas/").content.decode()
    filtrado = ingresada.get(f"/ventas/reportes/ventas/?item={diez.pk}").content.decode()
    cuerpo_filtrado = _cuerpo(filtrado)

    assert "Gs. 28.800" in completo
    assert ">9.900<" in _cuerpo(completo)
    assert ">18.900<" in _cuerpo(completo)
    assert "Gs. 9.900" in filtrado
    assert ">18.900<" not in cuerpo_filtrado
    assert "Cinco" not in cuerpo_filtrado


@pytest.mark.django_db
def test_filtros_y_agrupacion(ingresada, usuario):
    caja = _cuenta()
    otra = _cuenta("Caja chica", "CHICA")
    cliente = _cliente()
    lacteos = _categoria("Lácteos")
    item = _item(
        descripcion="Leche",
        codigo_barra="LEC",
        categoria=lacteos,
        marca=_marca("Marca A"),
        unidad_negocio=_negocio("LAC", "Lácteos"),
    )
    otro = _item(descripcion="Agua", codigo_barra="AGU")
    _cobrar(usuario, item, cliente=cliente, medio=MedioPago.TRANSFERENCIA, caja=caja)
    _cobrar(usuario, otro, medio=MedioPago.EFECTIVO, caja=otra)

    por_medio = ingresada.get(
        f"/ventas/reportes/ventas/?venta__medio={MedioPago.TRANSFERENCIA}"
    )
    cuerpo_medio = _cuerpo(por_medio.content.decode())
    assert "Leche" in cuerpo_medio
    assert "Agua" not in cuerpo_medio
    assert "Medio de pago: Transferencia" in por_medio.content.decode()

    por_producto = ingresada.get("/ventas/reportes/ventas/?agrupar=producto")
    contenido = por_producto.content.decode()
    cuerpo = _cuerpo(contenido)
    assert "Por producto" in contenido
    assert "Leche" in cuerpo
    assert "Agua" in cuerpo
    assert "Lácteos" in cuerpo
    assert "Resultados (2 filas)" in contenido
    assert 'href="/ventas/?venta=' not in cuerpo


@pytest.mark.django_db
def test_el_periodo_limita_las_ventas(ingresada, usuario):
    item = _item()
    hoy = _hoy()
    ayer = hoy - timedelta(days=1)
    _cobrar(usuario, item, fecha=hoy)
    _cobrar(usuario, _item(descripcion="Ayer", codigo_barra="AYE"), fecha=ayer)

    content = ingresada.get(
        f"/ventas/reportes/ventas/?fecha_desde={hoy.isoformat()}&fecha_hasta={hoy.isoformat()}"
    ).content.decode()
    cuerpo = _cuerpo(content)

    assert item.descripcion in cuerpo
    assert "Ayer" not in cuerpo


@pytest.mark.django_db
def test_panel_resume_el_periodo_y_lo_compara(ingresada, usuario):
    item = _item(precio=Decimal("11000"))
    hoy = _hoy()
    ayer = hoy - timedelta(days=1)
    _cobrar(usuario, item, fecha=hoy)
    _cobrar(usuario, item, fecha=hoy)
    _cobrar(usuario, item, fecha=ayer)

    content = ingresada.get(
        f"/ventas/reportes/ventas/?fecha_desde={hoy.isoformat()}&fecha_hasta={hoy.isoformat()}"
    ).content.decode()

    assert "Total ventas" in content
    assert "Gs. 22.000" in content
    assert "Gravado" in content
    assert "IVA" in content
    assert "Comprobantes" in content
    assert "Ventas por medio de pago" in content
    assert "Efectivo" in content
    assert "Evolución de ventas" in content
    assert "Filtros de búsqueda" in content
    assert "Resultados (2 líneas)" in content
    assert "+100%" in content
    assert "Periodo anterior" in content
    assert "dash-chart-data" in content


@pytest.mark.django_db
def test_excel_separa_gravado_e_iva(ingresada, usuario):
    item = _item(descripcion="Azúcar", precio=Decimal("11000"))
    _cobrar(usuario, item)

    response = ingresada.get("/ventas/reportes/ventas/exportar.xlsx")

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
    item = _item(descripcion="Yerba")
    venta = _cobrar(usuario, item)

    content = ingresada.get("/ventas/reportes/ventas/imprimir/").content.decode()

    assert "Informe de ventas" in content
    assert venta.numero_completo in content
    assert "Yerba" in content

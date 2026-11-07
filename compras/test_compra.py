from decimal import Decimal

import pytest

from compras.models import Compra, CompraDetalle, EstadoCompra, TipoCompra
from cuentas.models import Cuenta
from inventario.defecto import asegurar_referenciales_defecto
from inventario.models import (
    Item,
    ItemCategoria,
    ItemMovimiento,
    ItemPrecioHistorial,
    ItemUnidad,
    Marca,
    OrigenPrecio,
    RelacionUnidad,
    TasaIva,
    TipoItem,
    TipoMovimiento,
    UnidadMedida,
)
from negocio.models import UnidadNegocio
from personas.models import Genero, Persona, TipoDocumento


def _cuenta():
    return Cuenta.objects.create(descripcion="Caja compras", nombre_corto="COMPRA")


def _proveedor():
    return Persona.objects.create(
        tipo_documento=TipoDocumento.RUC,
        documento="80001111-2",
        razon_social="Proveedor SA",
        genero=Genero.SIN_DEFINIR,
        direccion="Centro",
        es_proveedor=True,
    )


def _negocio():
    return UnidadNegocio.objects.get_or_create(
        abreviado="DEP",
        defaults={"descripcion": "Depósito"},
    )[0]


def _item(**extra):
    marca, _ = Marca.objects.get_or_create(descripcion="Genérica")
    categoria, _ = ItemCategoria.objects.get_or_create(descripcion="Alimentos")
    unidad, _ = UnidadMedida.objects.get_or_create(descripcion="Unidad", defaults={"simbolo": "Un"})
    datos = {
        "marca": marca,
        "categoria": categoria,
        "unidad_medida": unidad,
        "unidad_negocio": extra.pop("unidad_negocio", _negocio()),
        "codigo_barra": extra.pop("codigo_barra", "PROD-001"),
        "descripcion": extra.pop("descripcion", "Azúcar 1 kg"),
        "tipo": TipoItem.PRODUCTO,
        "activo": True,
        "precio": Decimal("12000"),
        "tasa_iva": TasaIva.DIEZ,
        "ultimo_costo": Decimal("8000"),
        "precio_segun_costo": False,
    }
    datos.update(extra)
    return Item.objects.create(**datos)


def _gasto(**extra):
    refs = asegurar_referenciales_defecto()
    datos = {
        "marca": refs["marca"],
        "categoria": refs["categoria"],
        "unidad_medida": refs["unidad_medida"],
        "descripcion": extra.pop("descripcion", "Flete"),
        "tipo": TipoItem.GASTO,
        "activo": True,
        "tasa_iva": TasaIva.DIEZ,
    }
    datos.update(extra)
    return Item.objects.create(**datos)


def _preparar():
    cuenta = _cuenta()
    proveedor = _proveedor()
    item = _item()
    return cuenta, proveedor, item


def _cuota_total(ingresada, total, *, cuenta, proveedor, vencimiento="2026-12-31"):
    ingresada.post(
        "/compras/nueva/",
        _cabecera(cuenta, proveedor, tipo=TipoCompra.FACTURA_CREDITO),
    )
    return ingresada.post(
        "/compras/nueva/cuotas/",
        {
            "accion": "agregar",
            "vencimiento": vencimiento,
            "importe": str(int(total)),
        },
    )


def _cabecera(cuenta, proveedor, **extra):
    datos = {
        "cuenta": str(cuenta.pk),
        "tipo": TipoCompra.FACTURA_CONTADO,
        "proveedor": str(proveedor.pk),
        "timbrado": "12345678",
        "numero_establecimiento": "001",
        "numero_punto": "001",
        "numero_secuencial": "1",
    }
    datos.update(extra)
    return datos


@pytest.mark.django_db
def test_compra_pide_ingreso(client):
    response = client.get("/compras/nueva/")
    assert response.status_code == 302
    assert response.url.startswith("/login/")


@pytest.mark.django_db
def test_menu_muestra_compras(ingresada):
    content = ingresada.get("/").content.decode()
    assert 'href="/compras/"' in content
    assert "Compras" in content


@pytest.mark.django_db
def test_formulario_muestra_cuenta_y_tipos(ingresada):
    _cuenta()
    pagina = ingresada.get("/compras/nueva/")
    assert pagina.status_code == 200
    content = pagina.content.decode()
    assert "Nueva compra" in content
    assert "Cuenta" in content
    assert 'value="FAC_CON"' in content
    assert 'value="FAC_CRE"' in content
    assert 'value="EGRESO"' in content
    assert "data-compra-guardar" in content
    assert "data-compra-confirmar" in content


@pytest.mark.django_db
def test_producto_infla_stock_y_actualiza_ultimo_costo(ingresada):
    cuenta, proveedor, item = _preparar()
    ingresada.post("/compras/nueva/agregar/", {"q": "PROD-001"})
    detalle = Compra.objects.get(estado=EstadoCompra.EN_CURSO).detalles.get()
    ingresada.post(
        f"/compras/nueva/lineas/{detalle.pk}/",
        {"accion": "costo", "costo": "9.000"},
    )
    response = ingresada.post(
        "/compras/nueva/confirmar/",
        _cabecera(cuenta, proveedor),
    )
    compra = Compra.objects.get(estado=EstadoCompra.CONFIRMADA)
    assert response.status_code == 302
    assert response.url == "/compras/"
    item.refresh_from_db()
    movimiento = ItemMovimiento.objects.get(tipo=TipoMovimiento.COMPRA, es_vigente=True)
    assert movimiento.item_id == item.pk
    assert movimiento.cantidad == Decimal("1")
    assert item.ultimo_costo == Decimal("9000")
    assert compra.tipo == TipoCompra.FACTURA_CONTADO
    assert compra.numero_completo == "001-001-0000001"
    assert compra.cuenta_id == cuenta.pk


@pytest.mark.django_db
def test_gasto_exige_unidad_de_negocio_y_no_mueve_stock(ingresada):
    cuenta, proveedor, _item_prod = _preparar()
    gasto = _gasto()
    ingresada.post("/compras/nueva/agregar/", {"item": str(gasto.pk)})
    detalle = CompraDetalle.objects.get(item=gasto)
    content = ingresada.get("/compras/nueva/").content.decode()
    assert "Flete" in content
    assert "Unidad de negocio" in content
    assert "IVA" in content

    ingresada.post(
        f"/compras/nueva/lineas/{detalle.pk}/",
        {"accion": "costo", "costo": "50.000"},
    )
    fallida = ingresada.post(
        "/compras/nueva/confirmar/",
        _cabecera(cuenta, proveedor),
    )
    assert Compra.objects.filter(estado=EstadoCompra.CONFIRMADA).count() == 0
    assert fallida.status_code == 302

    ingresada.post(
        f"/compras/nueva/lineas/{detalle.pk}/",
        {"accion": "negocio", "unidad_negocio": str(_negocio().pk)},
    )
    ingresada.post(
        f"/compras/nueva/lineas/{detalle.pk}/",
        {"accion": "tasa", "tasa": "5"},
    )
    ingresada.post("/compras/nueva/confirmar/", _cabecera(cuenta, proveedor))
    compra = Compra.objects.get(estado=EstadoCompra.CONFIRMADA)
    detalle.refresh_from_db()
    assert detalle.unidad_negocio_id == _negocio().pk
    assert detalle.tasa_iva == 5
    assert not ItemMovimiento.objects.filter(item=gasto).exists()
    assert compra.detalles.get().item_id == gasto.pk


@pytest.mark.django_db
def test_producto_usa_tasa_y_unidad_de_negocio_de_la_ficha(ingresada):
    cuenta, proveedor, item = _preparar()
    ingresada.post("/compras/nueva/agregar/", {"q": "PROD-001"})
    detalle = CompraDetalle.objects.get()
    assert detalle.tasa_iva == item.tasa_iva
    assert detalle.unidad_negocio_id == item.unidad_negocio_id
    ingresada.post(
        f"/compras/nueva/lineas/{detalle.pk}/",
        {"accion": "costo", "costo": "8.000"},
    )
    ingresada.post("/compras/nueva/confirmar/", _cabecera(cuenta, proveedor))
    detalle.refresh_from_db()
    assert detalle.tasa_iva == TasaIva.DIEZ
    assert detalle.unidad_negocio_id == item.unidad_negocio_id


@pytest.mark.django_db
def test_egreso_no_pide_timbrado(ingresada):
    cuenta, proveedor, item = _preparar()
    ingresada.post("/compras/nueva/agregar/", {"q": "PROD-001"})
    detalle = CompraDetalle.objects.get()
    ingresada.post(
        f"/compras/nueva/lineas/{detalle.pk}/",
        {"accion": "costo", "costo": "8.000"},
    )
    ingresada.post(
        "/compras/nueva/confirmar/",
        _cabecera(cuenta, proveedor, tipo=TipoCompra.EGRESO, timbrado="", numero_secuencial=""),
    )
    compra = Compra.objects.get(estado=EstadoCompra.CONFIRMADA)
    assert compra.tipo == TipoCompra.EGRESO
    assert compra.timbrado == ""
    assert compra.numero_completo is None
    assert ItemMovimiento.objects.filter(tipo=TipoMovimiento.COMPRA).exists()


@pytest.mark.django_db
def test_factura_credito_y_duplicado(ingresada):
    cuenta, proveedor, item = _preparar()
    ingresada.post("/compras/nueva/agregar/", {"q": "PROD-001"})
    detalle = CompraDetalle.objects.get()
    ingresada.post(
        f"/compras/nueva/lineas/{detalle.pk}/",
        {"accion": "costo", "costo": "8.000"},
    )
    _cuota_total(ingresada, Decimal("8000"), cuenta=cuenta, proveedor=proveedor)
    ingresada.post(
        "/compras/nueva/confirmar/",
        _cabecera(cuenta, proveedor, tipo=TipoCompra.FACTURA_CREDITO),
    )
    assert Compra.objects.get(estado=EstadoCompra.CONFIRMADA).tipo == TipoCompra.FACTURA_CREDITO

    otro = _item(descripcion="Harina", codigo_barra="PROD-002")
    ingresada.post("/compras/nueva/agregar/", {"q": "PROD-002"})
    detalle = CompraDetalle.objects.get(item=otro)
    ingresada.post(
        f"/compras/nueva/lineas/{detalle.pk}/",
        {"accion": "costo", "costo": "4.000"},
    )
    _cuota_total(ingresada, Decimal("4000"), cuenta=cuenta, proveedor=proveedor)
    ingresada.post(
        "/compras/nueva/confirmar/",
        _cabecera(cuenta, proveedor, tipo=TipoCompra.FACTURA_CREDITO),
    )
    assert Compra.objects.filter(estado=EstadoCompra.CONFIRMADA).count() == 1
    assert Compra.objects.filter(estado=EstadoCompra.EN_CURSO).exists()


@pytest.mark.django_db
def test_confirma_pide_cuenta(ingresada):
    _proveedor()
    item = _item()
    ingresada.post("/compras/nueva/agregar/", {"q": item.codigo_barra})
    response = ingresada.post(
        "/compras/nueva/confirmar/",
        {
            "tipo": TipoCompra.EGRESO,
            "proveedor": str(Persona.objects.get().pk),
        },
    )
    assert response.status_code == 302
    assert Compra.objects.filter(estado=EstadoCompra.CONFIRMADA).count() == 0


@pytest.mark.django_db
def test_afecta_precios_segun_costo(ingresada):
    cuenta, proveedor, item = _preparar()
    item.precio_segun_costo = True
    item.save(update_fields=["precio_segun_costo"])
    ingresada.post("/compras/nueva/agregar/", {"q": "PROD-001"})
    detalle = CompraDetalle.objects.get()
    ingresada.post(
        f"/compras/nueva/lineas/{detalle.pk}/",
        {"accion": "costo", "costo": "10.000"},
    )
    pagina = ingresada.get("/compras/nueva/")
    assert 'data-compra-precios="1"' in pagina.content.decode()
    assert "Precios según costo" in pagina.content.decode()

    ingresada.post(
        "/compras/nueva/confirmar/",
        {**_cabecera(cuenta, proveedor), "afectar_precios": "1"},
    )
    item.refresh_from_db()
    assert item.ultimo_costo == Decimal("10000")
    assert item.precio == Decimal("15000")
    historial = ItemPrecioHistorial.objects.get()
    assert historial.origen == OrigenPrecio.COMPRA
    assert historial.precio_nuevo == Decimal("15000")


@pytest.mark.django_db
def test_no_afecta_precios_si_dice_que_no(ingresada):
    cuenta, proveedor, item = _preparar()
    item.precio_segun_costo = True
    item.save(update_fields=["precio_segun_costo"])
    ingresada.post("/compras/nueva/agregar/", {"q": "PROD-001"})
    detalle = CompraDetalle.objects.get()
    ingresada.post(
        f"/compras/nueva/lineas/{detalle.pk}/",
        {"accion": "costo", "costo": "10.000"},
    )
    ingresada.post(
        "/compras/nueva/confirmar/",
        {**_cabecera(cuenta, proveedor), "afectar_precios": "0"},
    )
    item.refresh_from_db()
    assert item.ultimo_costo == Decimal("10000")
    assert item.precio == Decimal("12000")
    assert ItemPrecioHistorial.objects.count() == 0


@pytest.mark.django_db
def test_cantidad_acepta_coma_y_tres_decimales(ingresada):
    _preparar()
    ingresada.post("/compras/nueva/agregar/", {"q": "PROD-001"})
    detalle = CompraDetalle.objects.get()
    pagina = ingresada.get("/compras/nueva/")
    content = pagina.content.decode()
    assert 'name="cantidad"' in content
    assert 'data-cantidad="py"' in content
    assert 'src="/static/js/rupia-cantidad.js"' in content

    ingresada.post(
        f"/compras/nueva/lineas/{detalle.pk}/",
        {"cantidad": "1,250"},
    )
    detalle.refresh_from_db()
    assert detalle.cantidad == Decimal("1.250")


@pytest.mark.django_db
def test_solo_unidades_vinculadas(ingresada):
    _preparar()
    item = Item.objects.get(codigo_barra="PROD-001")
    caja, _ = UnidadMedida.objects.get_or_create(
        descripcion="Caja", defaults={"simbolo": "Cj"}
    )
    suelta, _ = UnidadMedida.objects.get_or_create(
        descripcion="Suelta", defaults={"simbolo": "Su"}
    )
    ItemUnidad.objects.create(
        item=item,
        unidad_medida=caja,
        relacion=RelacionUnidad.MAYOR,
        valor=Decimal("12"),
    )
    ingresada.post("/compras/nueva/agregar/", {"q": "PROD-001"})
    detalle = CompraDetalle.objects.get()
    content = ingresada.get("/compras/nueva/").content.decode()
    assert f'value="{item.unidad_medida_id}"' in content
    assert f'value="{caja.pk}"' in content
    assert f'value="{suelta.pk}"' not in content

    rechazada = ingresada.post(
        f"/compras/nueva/lineas/{detalle.pk}/",
        {"accion": "unidad", "unidad": str(suelta.pk)},
    )
    assert rechazada.status_code == 302
    detalle.refresh_from_db()
    assert detalle.unidad_medida_id == item.unidad_medida_id

    ingresada.post(
        f"/compras/nueva/lineas/{detalle.pk}/",
        {"accion": "unidad", "unidad": str(caja.pk)},
    )
    detalle.refresh_from_db()
    assert detalle.unidad_medida_id == caja.pk


@pytest.mark.django_db
def test_buscador_ofrece_nueva_persona(ingresada):
    content = ingresada.get("/compras/nueva/").content.decode()
    assert 'data-persona-nueva="/personas/?nueva=1&amp;proveedor=1"' in content


@pytest.mark.django_db
def test_timbrado_de_ocho_digitos_y_factura_de_siete(ingresada):
    cuenta, proveedor, _item = _preparar()
    ingresada.post("/compras/nueva/agregar/", {"q": "PROD-001"})
    detalle = CompraDetalle.objects.get()
    ingresada.post(
        f"/compras/nueva/lineas/{detalle.pk}/",
        {"accion": "costo", "costo": "8.000"},
    )
    pagina = ingresada.get("/compras/nueva/").content.decode()
    assert 'name="timbrado"' in pagina
    assert 'maxlength="8"' in pagina
    assert 'name="numero_secuencial"' in pagina
    assert 'maxlength="7"' in pagina

    corta = ingresada.post(
        "/compras/nueva/confirmar/",
        _cabecera(cuenta, proveedor, timbrado="1234567"),
    )
    assert Compra.objects.filter(estado=EstadoCompra.CONFIRMADA).count() == 0
    assert corta.status_code == 302

    ingresada.post(
        "/compras/nueva/confirmar/",
        _cabecera(
            cuenta,
            proveedor,
            timbrado="12345678",
            numero_secuencial="1234567",
        ),
    )
    compra = Compra.objects.get(estado=EstadoCompra.CONFIRMADA)
    assert compra.timbrado == "12345678"
    assert compra.numero_completo == "001-001-1234567"

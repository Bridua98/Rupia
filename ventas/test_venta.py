from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from cuentas.models import Cuenta
from inventario.models import (
    Item,
    ItemCategoria,
    ItemMovimiento,
    ItemUnidad,
    Marca,
    RelacionUnidad,
    TasaIva,
    TipoItem,
    TipoMovimiento,
    UnidadMedida,
)
from negocio.models import UnidadNegocio
from personas.models import Genero, Persona, TipoDocumento
from ventas.cobro import agregar_producto, cambiar_cantidad, liquidar_iva
from ventas.models import EstadoVenta, MedioPago, PuntoExpedicion, TipoComprobante, Venta


@pytest.fixture
def usuario(django_user_model):
    return django_user_model.objects.create_user(
        "ada",
        "ada@rupia.local",
        "Clave-inicial-Rupia-2026",
    )


@pytest.fixture
def ingresada(client, usuario):
    client.force_login(usuario)
    return client


def _hoy():
    return timezone.localdate()


def _punto(tipo, **extra):
    hoy = _hoy()
    datos = {
        "tipo": tipo,
        "establecimiento": "001",
        "codigo": "001" if tipo == TipoComprobante.TICKET else "002",
        "timbrado": "12345678" if tipo == TipoComprobante.TICKET else "87654321",
        "vigencia_desde": hoy - timedelta(days=10),
        "vigencia_hasta": hoy + timedelta(days=300),
        "numero_desde": 1,
        "numero_hasta": 1000,
        "numero_proximo": 124,
        "emisor_razon_social": "Rupia SA",
        "emisor_ruc": "80000001-0",
        "emisor_direccion": "Asunción",
        "emisor_telefono": "021000000",
        "emisor_actividad": "Comercio",
    }
    datos.update(extra)
    return PuntoExpedicion.objects.create(**datos)


def _caja():
    return Cuenta.objects.create(descripcion="Caja 01", nombre_corto="CAJA01")


def _tarjeta():
    return Cuenta.objects.create(
        descripcion="Tarjeta",
        nombre_corto="TARJ",
        es_banco=True,
        es_tarjeta=True,
        numero="999",
    )


def _cliente():
    return Persona.objects.create(
        tipo_documento=TipoDocumento.RUC,
        documento="80009735-8",
        razon_social="Cliente SA",
        genero=Genero.SIN_DEFINIR,
        direccion="Centro",
        es_cliente=True,
    )


def _item(**extra):
    marca, _ = Marca.objects.get_or_create(descripcion="Genérica")
    categoria, _ = ItemCategoria.objects.get_or_create(descripcion="Alimentos")
    unidad, _ = UnidadMedida.objects.get_or_create(descripcion="Unidad", defaults={"simbolo": "Un"})
    negocio, _ = UnidadNegocio.objects.get_or_create(
        abreviado="DEP",
        defaults={"descripcion": "Depósito"},
    )
    datos = {
        "marca": marca,
        "categoria": categoria,
        "unidad_medida": unidad,
        "unidad_negocio": negocio,
        "codigo_barra": extra.pop("codigo_barra", "PROD-001"),
        "descripcion": extra.pop("descripcion", "Bombón de helado sabor frutillas"),
        "tipo": TipoItem.PRODUCTO,
        "activo": True,
        "precio": Decimal("12000"),
        "tasa_iva": TasaIva.DIEZ,
        "ultimo_costo": Decimal("8000"),
    }
    datos.update(extra)
    return Item.objects.create(**datos)


def _stock(item, cantidad="20", unidad=None):
    pk = (ItemMovimiento.objects.order_by("-id").values_list("id", flat=True).first() or 0) + 1
    return ItemMovimiento.objects.create(
        id=pk,
        item=item,
        unidad_medida=unidad or item.unidad_medida,
        tipo=TipoMovimiento.COMPRA,
        fecha_movimiento=date(2026, 10, 1),
        cantidad=Decimal(cantidad),
        precio=item.precio or Decimal("0"),
        costo=item.ultimo_costo or Decimal("0"),
        subtotal=item.precio or Decimal("0"),
        es_vigente=True,
    )


def _preparar(*, factura=False):
    _punto(TipoComprobante.TICKET)
    _punto(TipoComprobante.FACTURA)
    caja = _caja()
    item = _item()
    _stock(item)
    return caja, item


@pytest.mark.django_db
def test_punto_de_venta_pide_ingreso(client):
    response = client.get("/ventas/punto-de-venta/")
    assert response.status_code == 302
    assert response.url.startswith("/login/")


@pytest.mark.django_db
def test_menu_muestra_punto_de_venta(ingresada):
    content = ingresada.get("/").content.decode()
    assert 'href="/ventas/punto-de-venta/"' in content
    assert "Punto de venta" in content


@pytest.mark.django_db
def test_agregar_por_descripcion_y_codigo(ingresada):
    _preparar()
    otro = _item(descripcion="Leche descremada", codigo_barra="PROD-002", precio=Decimal("8500"))
    _stock(otro)

    pagina = ingresada.get("/ventas/punto-de-venta/")
    assert pagina.status_code == 200
    assert "Nueva venta" in pagina.content.decode()

    ingresada.post("/ventas/punto-de-venta/agregar/", {"q": "Bombón"})
    ingresada.post("/ventas/punto-de-venta/agregar/", {"q": "PROD-002"})
    content = ingresada.get("/ventas/punto-de-venta/").content.decode()
    assert "Bombón de helado sabor frutillas" in content
    assert "Leche descremada" in content
    assert "Gs. 20.500" in content


@pytest.mark.django_db
def test_cambiar_cantidad_y_unidad(ingresada):
    _preparar()
    item = Item.objects.get(codigo_barra="PROD-001")
    mayor = UnidadMedida.objects.create(descripcion="Caja", simbolo="Cj")
    ItemUnidad.objects.create(
        item=item,
        unidad_medida=mayor,
        relacion=RelacionUnidad.MAYOR,
        valor=Decimal("10"),
    )
    ingresada.post("/ventas/punto-de-venta/agregar/", {"q": "PROD-001"})
    detalle = Venta.objects.get(estado=EstadoVenta.EN_CURSO).detalles.get()
    ingresada.post(f"/ventas/punto-de-venta/lineas/{detalle.pk}/", {"accion": "mas"})
    detalle.refresh_from_db()
    assert detalle.cantidad == Decimal("2.000")
    assert detalle.subtotal == Decimal("24000")
    ingresada.post(
        f"/ventas/punto-de-venta/lineas/{detalle.pk}/",
        {"accion": "unidad", "unidad": mayor.pk},
    )
    detalle.refresh_from_db()
    assert detalle.unidad_medida_id == mayor.pk
    assert detalle.precio == Decimal("120000")


@pytest.mark.django_db
def test_descuento_y_vuelto_efectivo(ingresada):
    _preparar()
    ingresada.post("/ventas/punto-de-venta/agregar/", {"q": "PROD-001"})
    ingresada.post(
        "/ventas/punto-de-venta/",
        {
            "medio": MedioPago.EFECTIVO,
            "descuento": "2.000",
            "importe_recibido": "20.000",
        },
    )
    content = ingresada.get("/ventas/punto-de-venta/").content.decode()
    assert "Gs. 10.000" in content
    assert "Gs. 20.000" in content


@pytest.mark.django_db
def test_tarjeta_sin_vuelto(ingresada):
    _preparar()
    tarjeta = _tarjeta()
    ingresada.post("/ventas/punto-de-venta/agregar/", {"q": "PROD-001"})
    ingresada.post(
        "/ventas/punto-de-venta/",
        {"medio": MedioPago.TARJETA, "cuenta_cobro": tarjeta.pk},
    )
    venta = Venta.objects.get(estado=EstadoVenta.EN_CURSO)
    assert venta.importe_recibido == Decimal("12000")
    content = ingresada.get("/ventas/punto-de-venta/").content.decode()
    assert "Gs. 0" in content or "Gs. 0" in content.replace("\xa0", " ")


@pytest.mark.django_db
def test_rechazo_por_stock_y_movimiento_al_confirmar(ingresada):
    _preparar()
    item = Item.objects.get(codigo_barra="PROD-001")
    ingresada.post("/ventas/punto-de-venta/agregar/", {"q": "PROD-001"})
    detalle = Venta.objects.get(estado=EstadoVenta.EN_CURSO).detalles.get()
    cambiar_cantidad(detalle, Decimal("30"))
    response = ingresada.post("/ventas/punto-de-venta/confirmar/")
    assert response.status_code == 302
    assert response.url == "/ventas/punto-de-venta/"
    assert Venta.objects.filter(estado=EstadoVenta.COBRADA).count() == 0
    assert "stock suficiente" in ingresada.get("/ventas/punto-de-venta/").content.decode()
    cambiar_cantidad(detalle, Decimal("2"))
    response = ingresada.post("/ventas/punto-de-venta/confirmar/")
    venta = Venta.objects.get(estado=EstadoVenta.COBRADA)
    assert response.url == f"/ventas/{venta.pk}/ticket/"
    assert venta.numero_completo == "001-001-0000124"
    assert venta.timbrado == "12345678"
    movimiento = ItemMovimiento.objects.get(tipo=TipoMovimiento.VENTA)
    assert movimiento.es_vigente is True
    assert movimiento.secuencia_origen == venta.numero_completo
    assert movimiento.item_id == item.pk
    assert movimiento.cantidad == Decimal("2.000")


@pytest.mark.django_db
def test_ticket_y_factura_avanzan_series_distintas(ingresada):
    _preparar()
    cliente = _cliente()
    item = Item.objects.get(codigo_barra="PROD-001")
    ingresada.post("/ventas/punto-de-venta/agregar/", {"item": item.pk})
    ingresada.post(
        "/ventas/punto-de-venta/confirmar/",
        {"tipo_comprobante": TipoComprobante.TICKET, "consumidor_final": "1"},
    )
    ticket = Venta.objects.get(tipo_comprobante=TipoComprobante.TICKET, estado=EstadoVenta.COBRADA)
    assert ticket.numero_completo == "001-001-0000124"
    ticket_html = ingresada.get(f"/ventas/{ticket.pk}/ticket/").content.decode()
    assert "Timbrado 12345678" in ticket_html
    assert "001-001-0000124" in ticket_html

    ingresada.post("/ventas/punto-de-venta/agregar/", {"item": item.pk})
    response = ingresada.post(
        "/ventas/punto-de-venta/confirmar/", {"tipo_comprobante": TipoComprobante.FACTURA}
    )
    assert response.url == "/ventas/punto-de-venta/"
    ingresada.post(
        "/ventas/punto-de-venta/",
        {"tipo_comprobante": TipoComprobante.FACTURA, "cliente": cliente.pk},
    )
    response = ingresada.post(
        "/ventas/punto-de-venta/confirmar/",
        {"tipo_comprobante": TipoComprobante.FACTURA, "cliente": cliente.pk},
    )
    factura = Venta.objects.get(
        tipo_comprobante=TipoComprobante.FACTURA, estado=EstadoVenta.COBRADA
    )
    assert response.url == f"/ventas/{factura.pk}/factura/"
    assert factura.numero_completo == "001-002-0000124"
    assert PuntoExpedicion.objects.get(tipo=TipoComprobante.TICKET).numero_proximo == 125
    assert PuntoExpedicion.objects.get(tipo=TipoComprobante.FACTURA).numero_proximo == 125
    factura_html = ingresada.get(f"/ventas/{factura.pk}/factura/").content.decode()
    assert "Factura N° 001-002-0000124" in factura_html
    assert "Cliente SA" in factura_html
    assert "IVA 10%" in factura_html


@pytest.mark.django_db
def test_cancelar_no_consume_numero(ingresada):
    _preparar()
    ingresada.post("/ventas/punto-de-venta/agregar/", {"q": "PROD-001"})
    ingresada.post("/ventas/punto-de-venta/cancelar/")
    assert Venta.objects.count() == 0
    assert PuntoExpedicion.objects.get(tipo=TipoComprobante.TICKET).numero_proximo == 124
    ingresada.post("/ventas/punto-de-venta/agregar/", {"q": "PROD-001"})
    ingresada.post("/ventas/punto-de-venta/confirmar/")
    venta = Venta.objects.get(estado=EstadoVenta.COBRADA)
    assert venta.numero_completo == "001-001-0000124"


@pytest.mark.django_db
def test_timbrado_vencido_y_rango_agotado(ingresada):
    hoy = _hoy()
    _punto(
        TipoComprobante.TICKET,
        vigencia_desde=hoy - timedelta(days=400),
        vigencia_hasta=hoy - timedelta(days=1),
    )
    _caja()
    item = _item()
    _stock(item)
    ingresada.post("/ventas/punto-de-venta/agregar/", {"item": item.pk})
    ingresada.post("/ventas/punto-de-venta/confirmar/")
    assert "timbrado no está vigente" in ingresada.get("/ventas/punto-de-venta/").content.decode()
    punto = PuntoExpedicion.objects.get()
    punto.vigencia_hasta = hoy + timedelta(days=10)
    punto.numero_proximo = 1001
    punto.save()
    ingresada.post("/ventas/punto-de-venta/confirmar/")
    assert "rango de números" in ingresada.get("/ventas/punto-de-venta/").content.decode()


@pytest.mark.django_db
def test_timbrado_deshabilitado_no_confirma(ingresada):
    _punto(TipoComprobante.TICKET, habilitado=False)
    _caja()
    item = _item()
    _stock(item)
    ingresada.post("/ventas/punto-de-venta/agregar/", {"item": item.pk})
    content = ingresada.get("/ventas/punto-de-venta/").content.decode()
    assert "El timbrado no está habilitado." in content
    assert "disabled" in content
    response = ingresada.post("/ventas/punto-de-venta/confirmar/")
    assert response.url == "/ventas/punto-de-venta/"
    assert Venta.objects.filter(estado=EstadoVenta.COBRADA).count() == 0
    assert "El timbrado no está habilitado." in ingresada.get(
        "/ventas/punto-de-venta/"
    ).content.decode()


@pytest.mark.django_db
def test_factura_deshabilitada_no_impide_ticket(ingresada):
    _punto(TipoComprobante.TICKET)
    _punto(TipoComprobante.FACTURA, habilitado=False)
    _caja()
    item = _item()
    _stock(item)
    cliente = _cliente()
    content = ingresada.get("/ventas/punto-de-venta/").content.decode()
    assert 'value="TICKET"' in content
    assert 'value="FACTURA"' not in content
    ingresada.post("/ventas/punto-de-venta/agregar/", {"item": item.pk})
    response = ingresada.post("/ventas/punto-de-venta/confirmar/")
    venta = Venta.objects.get(estado=EstadoVenta.COBRADA)
    assert response.url == f"/ventas/{venta.pk}/ticket/"
    ingresada.post("/ventas/punto-de-venta/agregar/", {"item": item.pk})
    ingresada.post(
        "/ventas/punto-de-venta/",
        {"tipo_comprobante": TipoComprobante.FACTURA, "cliente": cliente.pk},
    )
    response = ingresada.post(
        "/ventas/punto-de-venta/confirmar/",
        {"tipo_comprobante": TipoComprobante.FACTURA, "cliente": cliente.pk},
    )
    assert response.url == "/ventas/punto-de-venta/"
    assert (
        Venta.objects.filter(
            tipo_comprobante=TipoComprobante.FACTURA,
            estado=EstadoVenta.COBRADA,
        ).count()
        == 0
    )
    assert "El timbrado no está habilitado." in ingresada.get(
        "/ventas/punto-de-venta/"
    ).content.decode()


@pytest.mark.django_db
def test_sin_timbrado_no_confirma(ingresada):
    _caja()
    item = _item()
    _stock(item)
    ingresada.post("/ventas/punto-de-venta/agregar/", {"item": item.pk})
    response = ingresada.post("/ventas/punto-de-venta/confirmar/")
    assert response.url == "/ventas/punto-de-venta/"
    assert "No hay un timbrado registrado" in ingresada.get(
        "/ventas/punto-de-venta/"
    ).content.decode()


@pytest.mark.django_db
def test_liquidacion_iva_cierra_con_total(usuario):
    _caja()
    venta = Venta.objects.create(
        fecha=_hoy(),
        usuario=usuario,
        descuento=Decimal("3200"),
        tipo_comprobante=TipoComprobante.TICKET,
    )
    diez = _item(
        descripcion="Diez", codigo_barra="T10", precio=Decimal("11000"), tasa_iva=TasaIva.DIEZ
    )
    cinco = _item(
        descripcion="Cinco",
        codigo_barra="T5",
        precio=Decimal("21000"),
        tasa_iva=TasaIva.CINCO,
    )
    agregar_producto(venta, item=diez)
    agregar_producto(venta, item=cinco)
    iva = liquidar_iva(venta)
    assert iva.subtotal == Decimal("32000")
    assert iva.descuento == Decimal("3200")
    assert iva.total == Decimal("28800")
    assert iva.gravadas_10 + iva.iva_10 + iva.gravadas_5 + iva.iva_5 + iva.exentas == iva.total
    assert iva.iva_10 == Decimal("900")
    assert iva.iva_5 == Decimal("900")

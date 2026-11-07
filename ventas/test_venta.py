from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

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
from ventas.cobro import agregar_producto, cambiar_cantidad, liquidar_iva, medios_disponibles
from ventas.models import EstadoVenta, MedioPago, PuntoExpedicion, TipoComprobante, Venta


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
    content = pagina.content.decode()
    assert "Nueva venta" in content
    assert 'value="TICKET"' in content
    assert 'value="FACTURA"' in content
    assert "data-pos-guardar" in content
    assert "data-pos-cobrar" in content

    ingresada.post("/ventas/punto-de-venta/agregar/", {"q": "Bombón"})
    ingresada.post("/ventas/punto-de-venta/agregar/", {"q": "PROD-002"})
    content = ingresada.get("/ventas/punto-de-venta/").content.decode()
    assert "Bombón de helado sabor frutillas" in content
    assert "Leche descremada" in content
    assert "Genérica" in content
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
    assert 'value="20.000"' in content
    assert "Cobrar (F12)" in content
    assert "Guardar / Suspender (F5)" in content


@pytest.mark.django_db
def test_descuento_por_linea(ingresada):
    _preparar()
    ingresada.post("/ventas/punto-de-venta/agregar/", {"q": "PROD-001"})
    detalle = Venta.objects.get(estado=EstadoVenta.EN_CURSO).detalles.get()
    ingresada.post(
        f"/ventas/punto-de-venta/lineas/{detalle.pk}/",
        {"accion": "descuento", "descuento": "10"},
    )
    detalle.refresh_from_db()
    assert detalle.descuento_porcentaje == Decimal("10.00")
    assert detalle.subtotal == Decimal("10800")
    content = ingresada.get("/ventas/punto-de-venta/").content.decode()
    assert "Gs. 10.800" in content


@pytest.mark.django_db
def test_guardar_suspende_y_vuelve_al_inicio(ingresada):
    _preparar()
    ingresada.post("/ventas/punto-de-venta/agregar/", {"q": "PROD-001"})
    response = ingresada.post("/ventas/punto-de-venta/", {"guardar": "1"})
    assert response.status_code == 302
    assert response.url == "/"
    venta = Venta.objects.get(estado=EstadoVenta.EN_CURSO)
    assert venta.detalles.count() == 1


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
    assert "Vuelto" not in content


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
    assert 'data-ticket-formato="80mm"' in ticket_html
    assert "Rupia SA" in ticket_html
    assert "N° venta" in ticket_html
    assert "001-001-0000124" in ticket_html
    assert "Fecha" in ticket_html
    assert "Hora" in ticket_html
    assert "Cant." in ticket_html
    assert "Descripción" in ticket_html
    assert "Monto" in ticket_html
    assert "Total" in ticket_html
    assert "Bombón de helado sabor frutillas" in ticket_html

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
    assert 'value="FACTURA"' in content
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


def _ocasional(**extra):
    datos = {
        "tipo_documento": TipoDocumento.CEDULA,
        "documento": "1111111",
        "razon_social": "Cliente Ocasional",
        "genero": Genero.SIN_DEFINIR,
        "direccion": "Sin dirección",
        "es_cliente": True,
    }
    datos.update(extra)
    return Persona.objects.create(**datos)


FICHA_ANDE = {
    "ruc": "80009735",
    "tipo_documento": TipoDocumento.RUC,
    "documento": "80009735-1",
    "razon_social": "ANDE",
    "fecha_nacimiento": None,
    "label": "ANDE (80009735-1)",
}


@pytest.mark.django_db
def test_borrador_asigna_cliente_ocasional_si_existe(ingresada):
    _preparar()
    _ocasional()
    content = ingresada.get("/ventas/punto-de-venta/").content.decode()
    venta = Venta.objects.get(estado=EstadoVenta.EN_CURSO)
    assert venta.cliente.razon_social == "Cliente Ocasional"
    assert "Cliente (opcional)" in content
    assert "Cobrar (F12)" in content
    assert "Cliente Ocasional" in content
    assert "Opciones adicionales" not in content


@pytest.mark.django_db
def test_borrador_queda_sin_cliente_si_no_hay_ocasional(ingresada):
    _preparar()
    ingresada.get("/ventas/punto-de-venta/")
    venta = Venta.objects.get(estado=EstadoVenta.EN_CURSO)
    assert venta.cliente_id is None


@pytest.mark.django_db
@patch("ventas.cobro.buscar_padron")
def test_buscar_clientes_mezcla_locales_y_padron(buscar_mock, ingresada):
    _preparar()
    local = _cliente()
    buscar_mock.return_value = [FICHA_ANDE]
    data = ingresada.get("/ventas/punto-de-venta/clientes/?q=cliente").json()
    labels = [item["label"] for item in data["resultados"]]
    assert str(local) in labels
    padron = [item for item in data["resultados"] if item["origen"] == "padron"]
    assert any(item["ruc"] == "80009735" for item in padron)


@pytest.mark.django_db
@patch("ventas.cobro.consultar_ruc")
def test_alta_desde_padron_crea_cliente_y_lo_asigna(consultar_mock, ingresada):
    _preparar()
    consultar_mock.return_value = FICHA_ANDE
    ingresada.get("/ventas/punto-de-venta/")
    response = ingresada.post(
        "/ventas/punto-de-venta/clientes/",
        {"ruc": "80009735"},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert response.status_code == 200
    persona = Persona.objects.get(documento="80009735-1")
    assert persona.es_cliente is True
    assert persona.razon_social == "ANDE"
    venta = Venta.objects.get(estado=EstadoVenta.EN_CURSO)
    assert venta.cliente_id == persona.pk
    assert response.json()["id"] == persona.pk


@pytest.mark.django_db
@patch("ventas.cobro.consultar_ruc")
def test_alta_desde_padron_reutiliza_documento_existente(consultar_mock, ingresada):
    _preparar()
    existente = Persona.objects.create(
        tipo_documento=TipoDocumento.RUC,
        documento="80009735-1",
        razon_social="ANDE Vieja",
        genero=Genero.SIN_DEFINIR,
        direccion="Centro",
        es_proveedor=True,
        es_cliente=False,
    )
    consultar_mock.return_value = FICHA_ANDE
    ingresada.get("/ventas/punto-de-venta/")
    ingresada.post("/ventas/punto-de-venta/clientes/", {"ruc": "80009735"})
    existente.refresh_from_db()
    assert Persona.objects.filter(documento="80009735-1").count() == 1
    assert existente.es_cliente is True
    assert Venta.objects.get(estado=EstadoVenta.EN_CURSO).cliente_id == existente.pk


@pytest.mark.django_db
def test_factura_sigue_pidiendo_cliente(ingresada):
    _preparar()
    item = Item.objects.get(codigo_barra="PROD-001")
    ingresada.post("/ventas/punto-de-venta/agregar/", {"item": item.pk})
    response = ingresada.post(
        "/ventas/punto-de-venta/confirmar/",
        {"tipo_comprobante": TipoComprobante.FACTURA, "consumidor_final": "1"},
    )
    assert response.url == "/ventas/punto-de-venta/"
    assert Venta.objects.filter(estado=EstadoVenta.COBRADA).count() == 0
    content = ingresada.get("/ventas/punto-de-venta/").content.decode()
    assert "La factura pide un cliente." in content


@pytest.mark.django_db
def test_factura_se_ofrece_aunque_falte_timbrado(ingresada):
    _punto(TipoComprobante.TICKET)
    _caja()
    content = ingresada.get("/ventas/punto-de-venta/").content.decode()
    assert 'value="TICKET"' in content
    assert 'value="FACTURA"' in content
    ingresada.post(
        "/ventas/punto-de-venta/",
        {"tipo_comprobante": TipoComprobante.FACTURA, "consumidor_final": "1"},
    )
    content = ingresada.get("/ventas/punto-de-venta/").content.decode()
    assert "La factura pide un cliente." in content
    assert "disabled" in content


@pytest.mark.django_db
def test_guardar_factura_sin_cliente_no_sale(ingresada):
    _preparar()
    ingresada.post("/ventas/punto-de-venta/agregar/", {"q": "PROD-001"})
    response = ingresada.post(
        "/ventas/punto-de-venta/",
        {
            "guardar": "1",
            "tipo_comprobante": TipoComprobante.FACTURA,
            "consumidor_final": "1",
        },
    )
    assert response.url == "/ventas/punto-de-venta/"
    assert Venta.objects.filter(estado=EstadoVenta.EN_CURSO).exists()
    content = ingresada.get("/ventas/punto-de-venta/").content.decode()
    assert "La factura pide un cliente." in content


@pytest.mark.django_db
def test_guardar_factura_con_cliente_suspende(ingresada):
    _preparar()
    cliente = _cliente()
    ingresada.post("/ventas/punto-de-venta/agregar/", {"q": "PROD-001"})
    response = ingresada.post(
        "/ventas/punto-de-venta/",
        {
            "guardar": "1",
            "tipo_comprobante": TipoComprobante.FACTURA,
            "cliente": cliente.pk,
        },
    )
    assert response.status_code == 302
    assert response.url == "/"
    venta = Venta.objects.get(estado=EstadoVenta.EN_CURSO)
    assert venta.tipo_comprobante == TipoComprobante.FACTURA
    assert venta.cliente_id == cliente.pk


@pytest.mark.django_db
def test_medios_de_cobro_siguen_a_las_cuentas(ingresada):
    _preparar()
    content = ingresada.get("/ventas/punto-de-venta/").content.decode()
    assert 'value="EFECTIVO"' in content
    assert "Monto recibido" in content
    assert 'value="TARJETA"' not in content
    assert 'value="TRANSFERENCIA"' not in content
    assert "Buscar cliente por nombre, RUC o cédula" in content
    _tarjeta()
    Cuenta.objects.create(
        descripcion="Banco Itau",
        nombre_corto="ITAU",
        es_banco=True,
        es_tarjeta=False,
        numero="001",
    )
    content = ingresada.get("/ventas/punto-de-venta/").content.decode()
    assert 'value="TARJETA"' in content
    assert 'value="TRANSFERENCIA"' in content
    assert medios_disponibles() == [
        (MedioPago.EFECTIVO, "Efectivo"),
        (MedioPago.TARJETA, "Tarjeta"),
        (MedioPago.TRANSFERENCIA, "Transferencia"),
    ]


@pytest.mark.django_db
def test_efectivo_lista_varias_cajas_y_sincroniza_cobro(ingresada):
    _punto(TipoComprobante.TICKET)
    _punto(TipoComprobante.FACTURA)
    caja1 = Cuenta.objects.create(descripcion="Caja mostrador", nombre_corto="MOST")
    caja2 = Cuenta.objects.create(descripcion="Caja depósito", nombre_corto="DEP")
    item = _item()
    _stock(item)
    content = ingresada.get("/ventas/punto-de-venta/").content.decode()
    assert "Caja mostrador" in content
    assert "Caja depósito" in content
    venta = Venta.objects.get(estado=EstadoVenta.EN_CURSO)
    assert venta.caja_id is None
    ingresada.post("/ventas/punto-de-venta/", {"cuenta_cobro": caja2.pk})
    venta.refresh_from_db()
    assert venta.medio == MedioPago.EFECTIVO
    assert venta.caja_id == caja2.pk
    assert venta.cuenta_cobro_id == caja2.pk


@pytest.mark.django_db
def test_medio_con_una_sola_cuenta_la_selecciona(ingresada):
    _preparar()
    tarjeta = _tarjeta()
    ingresada.get("/ventas/punto-de-venta/")
    ingresada.post("/ventas/punto-de-venta/", {"medio": MedioPago.TARJETA})
    venta = Venta.objects.get(estado=EstadoVenta.EN_CURSO)
    assert venta.cuenta_cobro_id == tarjeta.pk


@pytest.mark.django_db
def test_tarjeta_confirma_sin_caja_si_hay_varias(ingresada):
    _punto(TipoComprobante.TICKET)
    _punto(TipoComprobante.FACTURA)
    Cuenta.objects.create(descripcion="Caja 01", nombre_corto="CAJA01")
    Cuenta.objects.create(descripcion="Caja 02", nombre_corto="CAJA02")
    tarjeta = _tarjeta()
    item = _item()
    _stock(item)
    ingresada.post("/ventas/punto-de-venta/agregar/", {"q": "PROD-001"})
    ingresada.post(
        "/ventas/punto-de-venta/",
        {"medio": MedioPago.TARJETA, "cuenta_cobro": tarjeta.pk},
    )
    venta = Venta.objects.get(estado=EstadoVenta.EN_CURSO)
    assert venta.caja_id is None
    assert venta.cuenta_cobro_id == tarjeta.pk
    content = ingresada.get("/ventas/punto-de-venta/").content.decode()
    assert "Tarjeta · 999" in content
    response = ingresada.post("/ventas/punto-de-venta/confirmar/")
    assert response.status_code == 302
    assert Venta.objects.filter(estado=EstadoVenta.COBRADA).count() == 1


@pytest.mark.django_db
def test_cambiar_a_efectivo_usa_la_caja_aunque_venga_otra_cuenta(ingresada):
    caja, _item = _preparar()
    tarjeta = _tarjeta()
    ingresada.get("/ventas/punto-de-venta/")
    ingresada.post(
        "/ventas/punto-de-venta/",
        {"medio": MedioPago.TARJETA, "cuenta_cobro": tarjeta.pk, "caja": caja.pk},
    )
    response = ingresada.post(
        "/ventas/punto-de-venta/",
        {"medio": MedioPago.EFECTIVO, "cuenta_cobro": tarjeta.pk, "caja": caja.pk},
    )
    assert response.status_code == 302
    venta = Venta.objects.get(estado=EstadoVenta.EN_CURSO)
    assert venta.medio == MedioPago.EFECTIVO
    assert venta.cuenta_cobro_id == caja.pk
    content = ingresada.get("/ventas/punto-de-venta/").content.decode()
    assert "Elegí la cuenta de cobro." not in content
    assert "Monto recibido" in content


@pytest.mark.django_db
def test_pos_muestra_buscador_modal_y_atajos(ingresada):
    _preparar()
    content = ingresada.get("/ventas/punto-de-venta/").content.decode()
    assert "data-pos-modal-productos" in content
    assert "Agregar por código" in content
    assert "Atajos" in content
    assert "data-pos-modal-codigo" in content
    assert "Monto recibido" in content
    data = ingresada.get("/ventas/punto-de-venta/buscar/?q=").json()
    descripciones = [item["descripcion"] for item in data["resultados"]]
    assert "Bombón de helado sabor frutillas" in descripciones
    assert data["resultados"][0]["marca"] == "Genérica"
    assert data["hay_mas"] is False
    assert "Buscar por nombre, marca" in content


@pytest.mark.django_db
def test_buscar_productos_por_marca_y_pagina(ingresada):
    _preparar()
    por_marca = ingresada.get("/ventas/punto-de-venta/buscar/?q=Genérica").json()
    assert por_marca["resultados"]
    assert all(item["marca"] == "Genérica" for item in por_marca["resultados"])
    for indice in range(21):
        _item(
            descripcion=f"Producto extra {indice:02d}",
            codigo_barra=f"EXTRA-{indice:02d}",
            precio=Decimal("1000"),
        )
    primera = ingresada.get("/ventas/punto-de-venta/buscar/?q=&limite=20&offset=0").json()
    assert len(primera["resultados"]) == 20
    assert primera["hay_mas"] is True
    segunda = ingresada.get(
        f"/ventas/punto-de-venta/buscar/?q=&limite=20&offset={primera['siguiente']}"
    ).json()
    assert segunda["resultados"]
    ids = {item["id"] for item in primera["resultados"]}
    assert ids.isdisjoint({item["id"] for item in segunda["resultados"]})


@pytest.mark.django_db
def test_pos_muestra_numero_segun_comprobante(ingresada):
    _preparar()
    ticket = ingresada.get("/ventas/punto-de-venta/").content.decode()
    start = ticket.find("data-pos-proximo")
    assert start != -1, ticket[ticket.find("Nueva venta"): ticket.find("Nueva venta") + 400]
    assert "001-001-0000124" in ticket[start:start + 80]
    assert "Caja abierta" not in ticket
    assert "Descuento" not in ticket
    cliente = _cliente()
    ingresada.post(
        "/ventas/punto-de-venta/",
        {"tipo_comprobante": TipoComprobante.FACTURA, "cliente": cliente.pk},
    )
    factura = ingresada.get("/ventas/punto-de-venta/").content.decode()
    start = factura.find("data-pos-proximo")
    assert start != -1
    assert "001-002-0000124" in factura[start : start + 80]


@pytest.mark.django_db
def test_factura_muestra_numeracion_y_permite_elegirla(ingresada):
    _preparar()
    cliente = _cliente()
    item = Item.objects.get(codigo_barra="PROD-001")
    ingresada.post("/ventas/punto-de-venta/agregar/", {"item": item.pk})
    ingresada.post(
        "/ventas/punto-de-venta/",
        {"tipo_comprobante": TipoComprobante.FACTURA, "cliente": cliente.pk},
    )
    content = ingresada.get("/ventas/punto-de-venta/").content.decode()
    assert "Numeración de factura" in content
    assert 'value="0000124"' in content
    assert "Timbrado 87654321" in content
    response = ingresada.post(
        "/ventas/punto-de-venta/confirmar/",
        {
            "tipo_comprobante": TipoComprobante.FACTURA,
            "cliente": cliente.pk,
            "numero_establecimiento": "001",
            "numero_punto": "002",
            "numero_secuencial": "130",
        },
    )
    factura = Venta.objects.get(
        tipo_comprobante=TipoComprobante.FACTURA, estado=EstadoVenta.COBRADA
    )
    assert response.url == f"/ventas/{factura.pk}/factura/"
    assert factura.numero_completo == "001-002-0000130"
    assert factura.timbrado == "87654321"
    assert PuntoExpedicion.objects.get(tipo=TipoComprobante.FACTURA).numero_proximo == 131


@pytest.mark.django_db
def test_no_repite_timbrado_con_numero_completo(ingresada):
    _preparar()
    cliente = _cliente()
    item = Item.objects.get(codigo_barra="PROD-001")
    ingresada.post("/ventas/punto-de-venta/agregar/", {"item": item.pk})
    ingresada.post(
        "/ventas/punto-de-venta/confirmar/",
        {
            "tipo_comprobante": TipoComprobante.FACTURA,
            "cliente": cliente.pk,
            "numero_secuencial": "124",
        },
    )
    assert Venta.objects.filter(estado=EstadoVenta.COBRADA).count() == 1
    _stock(item, "20")
    ingresada.post("/ventas/punto-de-venta/agregar/", {"item": item.pk})
    response = ingresada.post(
        "/ventas/punto-de-venta/confirmar/",
        {
            "tipo_comprobante": TipoComprobante.FACTURA,
            "cliente": cliente.pk,
            "numero_establecimiento": "001",
            "numero_punto": "002",
            "numero_secuencial": "124",
        },
    )
    assert response.url == "/ventas/punto-de-venta/"
    assert Venta.objects.filter(estado=EstadoVenta.COBRADA).count() == 1
    content = ingresada.get("/ventas/punto-de-venta/").content.decode()
    assert "Ya hay un comprobante con ese timbrado y número." in content
    consulta = ingresada.get(
        "/ventas/punto-de-venta/numero/?establecimiento=001&punto=002&secuencial=124"
    ).json()
    assert consulta["ok"] is False
    assert "timbrado y número" in consulta["error"]

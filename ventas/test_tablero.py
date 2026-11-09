from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from compras.models import Compra, CompraDetalle, EstadoCompra, TipoCompra
from configuracion.testing import crear_usuario_con_permisos
from cuentas.models import Cuenta
from inventario.models import Item, ItemCategoria, Marca, TasaIva, TipoItem, UnidadMedida
from negocio.models import UnidadNegocio
from personas.models import Genero, Persona, TipoDocumento
from ventas.cobro import agregar_producto, cambiar_cantidad
from ventas.models import EstadoVenta, MedioPago, TipoComprobante, Venta
from ventas.tablero import tablero_inicio


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


def _item(**extra):
    datos = {
        "marca": extra.pop("marca", None) or _marca(),
        "categoria": extra.pop("categoria", None) or _categoria(),
        "unidad_medida": extra.pop("unidad_medida", None) or _unidad(),
        "codigo_barra": extra.pop("codigo_barra", "PROD-001"),
        "descripcion": extra.pop("descripcion", "Bombón de helado"),
        "tipo": TipoItem.PRODUCTO,
        "activo": True,
        "precio": extra.pop("precio", Decimal("12000")),
        "tasa_iva": TasaIva.DIEZ,
        "ultimo_costo": Decimal("8000"),
    }
    if "unidad_negocio" not in extra:
        datos["unidad_negocio"] = _negocio()
    datos.update(extra)
    return Item.objects.create(**datos)


def _cliente():
    return Persona.objects.create(
        tipo_documento=TipoDocumento.RUC,
        documento="80009735-8",
        razon_social="Cliente SA",
        genero=Genero.SIN_DEFINIR,
        direccion="Centro",
        es_cliente=True,
    )


def _cobrar(usuario, *items, fecha=None, descuento=Decimal("0"), cliente=None, cantidades=None):
    venta = Venta.objects.create(
        fecha=fecha or _hoy(),
        usuario=usuario,
        descuento=descuento,
        tipo_comprobante=TipoComprobante.TICKET,
        cliente=cliente,
    )
    for indice, item in enumerate(items):
        linea = agregar_producto(venta, item=item)
        if cantidades:
            cambiar_cantidad(linea, cantidades[indice])
    venta.estado = EstadoVenta.COBRADA
    venta.numero_completo = f"001-001-{venta.pk:07d}"
    venta.save(update_fields=["estado", "numero_completo"])
    return venta


@pytest.mark.django_db
def test_tablero_vacio():
    tablero = tablero_inicio()

    assert tablero.ventas_dia_cantidad == 0
    assert tablero.ventas_dia_importe == Decimal("0")
    assert tablero.ultima is None
    assert tablero.producto is None
    assert tablero.categorias == []
    assert tablero.marcas == []
    assert tablero.unidades == []


@pytest.mark.django_db
def test_en_curso_y_ayer_no_suman_el_dia(usuario):
    hoy = _hoy()
    ayer = hoy - timedelta(days=1)
    item = _item()
    _cobrar(usuario, item, fecha=ayer)
    Venta.objects.create(fecha=hoy, usuario=usuario, tipo_comprobante=TipoComprobante.TICKET)
    agregar_producto(Venta.objects.get(estado=EstadoVenta.EN_CURSO), item=item)

    tablero = tablero_inicio(hoy)

    assert tablero.ventas_dia_cantidad == 0
    assert tablero.ventas_dia_importe == Decimal("0")
    assert tablero.ultima is not None
    assert tablero.ultima.fecha == ayer
    assert tablero.ultima.cliente == "Sin cliente"
    assert tablero.ultima.importe == Decimal("12000")
    assert tablero.producto is None


@pytest.mark.django_db
def test_descuento_de_cabecera_se_prorratea(usuario):
    diez = _item(
        descripcion="Diez",
        codigo_barra="T10",
        precio=Decimal("11000"),
        categoria=_categoria("Lácteos"),
        marca=_marca("Marca A"),
        unidad_negocio=_negocio("LAC", "Lácteos"),
    )
    cinco = _item(
        descripcion="Cinco",
        codigo_barra="T5",
        precio=Decimal("21000"),
        categoria=_categoria("Bebidas"),
        marca=_marca("Marca B"),
        unidad_negocio=None,
    )
    venta = _cobrar(usuario, diez, cinco, descuento=Decimal("3200"), cliente=_cliente())

    tablero = tablero_inicio()

    assert tablero.ventas_dia_cantidad == 1
    assert tablero.ventas_dia_importe == Decimal("28800")
    assert tablero.ventas_dia_importe_txt == "Gs. 28.800"
    assert tablero.ultima.numero == venta.numero_completo
    assert tablero.ultima.cliente == "Cliente SA"
    assert [corte.nombre for corte in tablero.categorias] == ["Bebidas", "Lácteos"]
    assert [corte.importe for corte in tablero.categorias] == [Decimal("18900"), Decimal("9900")]
    assert [corte.nombre for corte in tablero.marcas] == ["Marca B", "Marca A"]
    assert [corte.nombre for corte in tablero.unidades] == ["Sin unidad", "Lácteos"]
    assert [corte.importe for corte in tablero.unidades] == [Decimal("18900"), Decimal("9900")]


@pytest.mark.django_db
def test_producto_mas_vendido_gana_por_cantidad(usuario):
    poco = _item(descripcion="Poco", codigo_barra="POCO", precio=Decimal("50000"))
    mucho = _item(descripcion="Mucho", codigo_barra="MUCHO", precio=Decimal("1000"))
    _cobrar(usuario, poco, mucho, cantidades=[Decimal("1"), Decimal("3")])

    tablero = tablero_inicio()

    assert tablero.producto.descripcion == "Mucho"
    assert tablero.producto.cantidad == Decimal("3")
    assert tablero.producto.importe == Decimal("3000")


@pytest.mark.django_db
def test_empate_de_cantidad_gana_el_de_mayor_importe(usuario):
    barato = _item(descripcion="Barato", codigo_barra="BAR", precio=Decimal("1000"))
    caro = _item(descripcion="Caro", codigo_barra="CAR", precio=Decimal("8000"))
    _cobrar(usuario, barato, caro, cantidades=[Decimal("2"), Decimal("2")])

    tablero = tablero_inicio()

    assert tablero.producto.descripcion == "Caro"
    assert tablero.producto.importe == Decimal("16000")


@pytest.mark.django_db
@pytest.mark.django_db
def test_graficos_cubren_periodos_ranking_y_actividades(usuario):
    venta = _cobrar(usuario, _item(), fecha=_hoy())
    venta.medio = MedioPago.TARJETA
    venta.save(update_fields=["medio"])
    tablero = tablero_inicio(_hoy())

    assert [len(tablero.graficos["lineas"][clave]) for clave in ("7", "30", "12")] == [7, 30, 12]
    assert tablero.graficos["lineas"]["7"][-1]["v"] == 12000
    assert tablero.graficos["lineas"]["7"][-1]["e"] == _hoy().strftime("%d/%m")
    assert len(tablero.graficos["flujo"]) == 3
    assert tablero.ranking[0].descripcion == "Bombón de helado"
    assert tablero.ranking[0].porcentaje == 100
    assert [(p.nombre, p.porcentaje) for p in tablero.distribucion] == [
        ("Contado", 0),
        ("Crédito", 0),
        ("Otros", 100),
    ]
    assert tablero.actividades[0].titulo == "Nueva venta registrada"
    assert tablero.actividades[0].detalle == "Gs. 12.000"
    assert tablero.periodo_txt.startswith("Este mes (")


@pytest.mark.django_db
def test_inicio_muestra_el_tablero(client, usuario):
    client.force_login(usuario)

    vacio = client.get("/").content.decode()
    assert "Hola, ada." in vacio
    assert "Ventas del día" in vacio
    assert "Sin ventas cobradas hoy" in vacio
    assert "Disponibilidad" in vacio
    assert "Liquidez" in vacio
    assert "Informes de gestión" in vacio
    assert "Venta vs compras · hoy" in vacio
    assert "Por categoría" in vacio
    assert "Por marca" in vacio
    assert "Por unidad de negocio" in vacio

    _cobrar(usuario, _item())
    con_venta = client.get("/").content.decode()
    assert "Gs. 12.000" in con_venta
    assert "1 comprobante" in con_venta
    assert "Bombón de helado" in con_venta
    assert "Alimentos" in con_venta
    assert "Depósito" in con_venta


def _cuenta():
    return Cuenta.objects.create(descripcion="Caja tablero", nombre_corto="TABLERO")


def _cobrar_en_caja(usuario, item, cuenta, *, fecha=None):
    venta = _cobrar(usuario, item, fecha=fecha)
    venta.caja = cuenta
    venta.cuenta_cobro = cuenta
    venta.medio = MedioPago.EFECTIVO
    venta.save(update_fields=["caja", "cuenta_cobro", "medio"])
    return venta


def _compra_confirmada(
    usuario,
    item,
    cuenta,
    *,
    importe,
    tipo=TipoCompra.FACTURA_CONTADO,
    numero="001-001-0000007",
):
    compra = Compra.objects.create(
        fecha=_hoy(),
        estado=EstadoCompra.CONFIRMADA,
        tipo=tipo,
        cuenta=cuenta if tipo != TipoCompra.FACTURA_CREDITO else None,
        usuario=usuario,
        numero_completo=numero,
        timbrado="12345678",
    )
    CompraDetalle.objects.create(
        compra=compra,
        item=item,
        unidad_medida=item.unidad_medida,
        cantidad=Decimal("1"),
        costo=importe,
        tasa_iva=TasaIva.DIEZ,
        subtotal=importe,
    )
    if tipo == TipoCompra.FACTURA_CREDITO:
        from compras.models import CompraCuota

        CompraCuota.objects.create(
            compra=compra,
            numero=1,
            vencimiento=_hoy(),
            importe=importe,
        )
    return compra


@pytest.mark.django_db
def test_tablero_muestra_disponibilidad_compras_y_liquidez(usuario):
    cuenta = _cuenta()
    item = _item(ultimo_costo=Decimal("5000"))
    _cobrar_en_caja(usuario, item, cuenta)
    _compra_confirmada(usuario, item, cuenta, importe=Decimal("4000"))
    _compra_confirmada(
        usuario,
        item,
        cuenta,
        importe=Decimal("2000"),
        tipo=TipoCompra.FACTURA_CREDITO,
        numero="001-001-0000008",
    )

    tablero = tablero_inicio()

    assert tablero.ventas_dia_importe == Decimal("12000")
    assert tablero.compras_hoy.valor == Decimal("6000")
    assert tablero.disponibilidad.valor == Decimal("8000")
    assert tablero.cuentas[0].nombre == "Caja tablero"
    assert tablero.comparacion_dia.diferencia == Decimal("6000")
    assert tablero.comparacion_mes.compras == Decimal("6000")
    assert tablero.por_pagar.valor == Decimal("2000")
    assert tablero.liquidez.valor == Decimal("8000")
    assert tablero.resultado_mes.valor == Decimal("6000")
    assert tablero.margen.valor == Decimal("7000")
    assert tablero.flujo_mes.valor == Decimal("8000")


def _html_inicio(client, user):
    client.force_login(user)
    return client.get("/").content.decode()


@pytest.mark.django_db
def test_inicio_cajero_ve_ventas_y_no_gestion(client, django_user_model, usuario):
    cajero = crear_usuario_con_permisos(
        django_user_model, ("punto_de_venta", "ver"), username="cajero"
    )
    _cobrar(usuario, _item())

    html = _html_inicio(client, cajero)

    assert "Ventas del día" in html
    assert "Por categoría" in html
    assert "Bombón de helado" in html
    assert "Compras del día" not in html
    assert "Disponibilidad" not in html
    assert "Liquidez" not in html
    assert "Ver mayor" not in html
    assert "Venta vs compras · hoy" not in html
    assert "Cuentas a pagar" not in html


@pytest.mark.django_db
def test_inicio_compras_no_muestra_ventas_ni_caja(client, django_user_model, usuario):
    comprador = crear_usuario_con_permisos(
        django_user_model, ("compras", "ver"), username="compras"
    )
    cuenta = _cuenta()
    item = _item()
    _cobrar_en_caja(usuario, item, cuenta)
    _compra_confirmada(usuario, item, cuenta, importe=Decimal("4000"))

    html = _html_inicio(client, comprador)

    assert "Compras del día" in html
    assert "Egresos del mes" in html
    assert "Ventas del día" not in html
    assert "Por categoría" not in html
    assert "Disponibilidad" not in html
    assert "Liquidez" not in html
    assert "Ver mayor" not in html
    assert "Venta vs compras · hoy" not in html
    assert "Caja tablero" not in html


@pytest.mark.django_db
def test_inicio_acceso_total_no_recorta_el_tablero(client, usuario):
    html = _html_inicio(client, usuario)

    assert "Ventas del día" in html
    assert "Compras del día" in html
    assert "Disponibilidad" in html
    assert "Liquidez" in html
    assert "Informes de gestión" in html
    assert "Venta vs compras · hoy" in html
    assert "Ver mayor" in html
    assert "Por categoría" in html
    assert "No hay indicadores para tu perfil" not in html

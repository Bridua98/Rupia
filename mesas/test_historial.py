import pytest

from mesas import cobro, comandas
from mesas.historial import origen_impreso, relato_cuenta, relato_venta
from mesas.models import Mesa
from mesas.test_cobro import _mesa_servida
from mesas.test_comandas import _habilitar, carta  # noqa: F401
from personas.models import Genero, Persona, TipoDocumento
from ventas.cobro import agregar_producto, anular, confirmar
from ventas.models import TipoAnulacion, TipoComprobante, Venta
from ventas.test_venta import _caja, _punto


@pytest.fixture
def caja(db):
    _punto(TipoComprobante.TICKET)
    _punto(TipoComprobante.FACTURA)
    return _caja()


def _cliente():
    return Persona.objects.create(
        tipo_documento=TipoDocumento.RUC,
        documento="80009735-8",
        razon_social="Cliente SA",
        genero=Genero.SIN_DEFINIR,
        direccion="Centro",
        es_cliente=True,
    )


@pytest.mark.django_db
def test_el_relato_separa_las_rondas(usuario, carta, caja):  # noqa: F811
    comanda = comandas.abrir(usuario=usuario, mesa=carta["mesa"])
    comanda.personas = 3
    comanda.save(update_fields=["personas"])
    comandas.agregar(comanda, carta["cerveza"], usuario=usuario, cantidad="2", nota="sin hielo")
    comandas.agregar(comanda, carta["milanesa"], usuario=usuario)
    comandas.enviar(comanda, usuario=usuario)
    comandas.agregar(comanda, carta["cerveza"], usuario=usuario)
    comandas.enviar(comanda, usuario=usuario)
    venta = cobro.pasar_a_venta(comanda, usuario=usuario)
    confirmar(venta)

    cuenta = relato_venta(venta)["cuentas"][0]

    assert cuenta["origen"] == "Mesa 1"
    assert cuenta["mozo"] == "ada"
    assert cuenta["personas"] == "3"
    assert [ronda["titulo"] for ronda in cuenta["rondas"]] == ["Ronda 1", "Ronda 2"]
    assert cuenta["rondas"][0]["quien"] == "ada"
    primera = {
        (linea["item"], linea["cantidad"], linea["nota"], linea["sector"])
        for linea in cuenta["rondas"][0]["lineas"]
    }
    assert primera == {
        ("Cerveza", "2", "sin hielo", "Barra"),
        ("Milanesa", "1", "", "Cocina"),
    }
    assert cuenta["rondas"][1]["lineas"][0]["item"] == "Cerveza"
    assert cuenta["rondas"][1]["lineas"][0]["cantidad"] == "1"
    assert origen_impreso(venta) == "Mesa 1"


@pytest.mark.django_db
def test_el_pedido_sin_mesa_usa_el_nombre(usuario, carta, caja):  # noqa: F811
    comanda = comandas.abrir(usuario=usuario, nombre="Oficina")
    comandas.agregar(comanda, carta["cerveza"], usuario=usuario)
    comandas.enviar(comanda, usuario=usuario)
    venta = confirmar(cobro.pasar_a_venta(comanda, usuario=usuario))

    assert relato_venta(venta)["cuentas"][0]["origen"] == "Oficina"
    assert origen_impreso(venta) == "Oficina"


@pytest.mark.django_db
def test_el_mostrador_no_imprime_servicio(usuario, carta, caja):  # noqa: F811
    from ventas.cobro import borrador

    venta = borrador(usuario)
    agregar_producto(venta, item=carta["helado"])
    confirmar(venta)

    relato = relato_venta(venta)
    assert relato["solo_mostrador"] is True
    assert relato["cuentas"] == []
    assert origen_impreso(venta) == ""


@pytest.mark.django_db
def test_lo_anulado_queda_aparte_del_cobro(usuario, carta, caja):  # noqa: F811
    comanda = comandas.abrir(usuario=usuario, mesa=carta["mesa"])
    comandas.agregar(comanda, carta["cerveza"], usuario=usuario, cantidad="2")
    comandas.agregar(comanda, carta["milanesa"], usuario=usuario)
    comandas.enviar(comanda, usuario=usuario)
    milanesa = comanda.detalles.get(item=carta["milanesa"])
    cerveza = comanda.detalles.get(item=carta["cerveza"])
    comandas.anular_linea(milanesa, usuario=usuario, motivo="No quiso")
    comandas.anular_linea(cerveza, usuario=usuario, motivo="Se cayó", cantidad="1")
    venta = confirmar(cobro.pasar_a_venta(comanda, usuario=usuario))

    cuenta = relato_venta(venta)["cuentas"][0]
    assert [(linea["item"], linea["cantidad"]) for linea in cuenta["rondas"][0]["lineas"]] == [
        ("Cerveza", "1")
    ]
    assert cuenta["anulaciones"][0]["motivo"] == "Se cayó"
    servicio = relato_cuenta(comanda)["cuentas"][0]
    anuladas = [linea for linea in servicio["rondas"][0]["lineas"] if linea["anulado"]]
    assert anuladas[0]["item"] == "Milanesa"
    assert any(fila["motivo"] == "No quiso" for fila in servicio["anulaciones"])


@pytest.mark.django_db
def test_una_cuenta_cobrada_en_dos_ventas_conserva_los_comprobantes(usuario, carta, caja):  # noqa: F811
    comanda = _mesa_servida(usuario, carta)
    venta = cobro.pasar_a_venta(comanda, usuario=usuario)
    comandas.agregar(comanda, carta["helado"], usuario=usuario)
    comandas.enviar(comanda, usuario=usuario)
    primera = confirmar(venta)
    segunda = confirmar(cobro.pasar_a_venta(comanda, usuario=usuario))

    items = {
        linea["item"]
        for ronda in relato_venta(primera)["cuentas"][0]["rondas"]
        for linea in ronda["lineas"]
    }
    assert "Helado" not in items
    assert relato_venta(segunda)["cuentas"][0]["rondas"][0]["lineas"][0]["item"] == "Helado"
    textos = [comp["texto"] for comp in relato_cuenta(comanda)["comprobantes"]]
    assert len(textos) == 2
    assert any(primera.numero_completo in texto for texto in textos)
    assert any(segunda.numero_completo in texto for texto in textos)


@pytest.mark.django_db
def test_anular_la_venta_no_borra_el_servicio(usuario, carta, caja):  # noqa: F811
    comanda = _mesa_servida(usuario, carta)
    venta = confirmar(cobro.pasar_a_venta(comanda, usuario=usuario))

    anular(venta, TipoAnulacion.FISICA, usuario=usuario)
    venta.refresh_from_db()

    relato = relato_venta(venta)
    assert relato["aviso"] == "La venta está anulada. La cuenta no se vuelve a abrir."
    assert relato["cuentas"][0]["origen"] == "Mesa 1"


@pytest.mark.django_db
def test_la_venta_el_ticket_y_la_factura_muestran_el_origen(ingresada, usuario, carta, caja):  # noqa: F811
    comanda = _mesa_servida(usuario, carta)
    venta = cobro.pasar_a_venta(comanda, usuario=usuario)
    venta.tipo_comprobante = TipoComprobante.FACTURA
    venta.cliente = _cliente()
    venta.save(update_fields=["tipo_comprobante", "cliente"])
    confirmar(venta)

    panel = ingresada.get(f"/ventas/?venta={venta.pk}&ver=1").content.decode()
    factura = ingresada.get(f"/ventas/{venta.pk}/factura/").content.decode()

    assert "Mesa 1" in panel
    assert "Ronda 1" in panel
    assert "Ronda 2" in panel
    assert "Ver el historial del servicio" in panel
    assert "Servicio Mesa 1" in factura


@pytest.mark.django_db
def test_el_ticket_de_mostrador_no_nombra_un_servicio(ingresada, usuario, carta, caja):  # noqa: F811
    from ventas.cobro import borrador

    venta = borrador(usuario)
    agregar_producto(venta, item=carta["helado"])
    confirmar(venta)

    ticket = ingresada.get(f"/ventas/{venta.pk}/ticket/").content.decode()

    assert "Servicio" not in ticket


@pytest.mark.django_db
def test_el_historial_muestra_lo_cerrado_y_su_comprobante(ingresada, usuario, carta, caja):  # noqa: F811
    _habilitar()
    comanda = _mesa_servida(usuario, carta)
    venta = confirmar(cobro.pasar_a_venta(comanda, usuario=usuario))
    comandas.abrir(usuario=usuario, mesa=Mesa.objects.create(nombre="2", zona="Salón"))
    comandas.abrir(usuario=usuario, nombre="Mesa de paso")
    comandas.anular_comanda(
        comandas.abrir(usuario=usuario, nombre="Se fueron"),
        usuario=usuario,
        motivo="Se fueron sin pedir",
    )

    listado = ingresada.get("/mesas/historial/").content.decode()
    detalle = ingresada.get(f"/mesas/historial/?servicio={comanda.pk}&ver=1").content.decode()
    ticket = ingresada.get(f"/ventas/{venta.pk}/ticket/").content.decode()

    assert "<span>Servicio</span><span>Mesa 1</span>" in ticket
    assert "Mesa 1" in listado
    assert "Mesa 2" not in listado
    assert "Mesa de paso" not in listado
    assert "Se fueron" in listado
    assert venta.numero_completo in listado
    assert "Ronda 1" in detalle
    assert "Comprobantes" in detalle
    assert venta.numero_completo in detalle
    assert f"venta={venta.pk}" in detalle
    assert "ver=1" in detalle


@pytest.mark.django_db
def test_el_informe_filtra_y_agrupa_por_origen(ingresada, usuario, carta, caja):  # noqa: F811
    from ventas.cobro import borrador

    comanda = _mesa_servida(usuario, carta)
    confirmar(cobro.pasar_a_venta(comanda, usuario=usuario))
    mostrador = borrador(usuario)
    agregar_producto(mostrador, item=carta["helado"])
    confirmar(mostrador)

    informe = ingresada.get("/ventas/reportes/ventas/").content.decode()
    solo_mesa = ingresada.get(f"/ventas/reportes/ventas/?mesa={carta['mesa'].pk}").content.decode()
    agrupado = ingresada.get("/ventas/reportes/ventas/?agrupar=origen").content.decode()
    otra = Mesa.objects.create(nombre="9")
    vacio = ingresada.get(f"/ventas/reportes/ventas/?mesa={otra.pk}").content.decode()

    assert "Mesa 1" in informe
    assert "Mostrador" in informe
    assert "Cerveza" in solo_mesa
    assert "Helado" not in solo_mesa.split("<tbody>")[1].split("</tbody>")[0]
    assert "Agrupación" in agrupado
    assert "Mesa 1" in agrupado
    assert "Mostrador" in agrupado
    assert "No hay ventas para los filtros elegidos." in vacio
    assert Venta.objects.filter(estado="COBRADA").count() == 2

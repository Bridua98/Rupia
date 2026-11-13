from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from configuracion.testing import crear_usuario_con_permisos
from inventario.models import Item
from mesas import cobro, comandas
from mesas.models import ComandaDetalle, EstadoComanda
from mesas.test_comandas import _habilitar, carta  # noqa: F401
from personas.models import Genero, Persona, TipoDocumento
from ventas.cobro import (
    agregar_producto,
    cambiar_cantidad,
    cambiar_descuento,
    cancelar,
    confirmar,
    quitar_linea,
)
from ventas.models import EstadoVenta, TipoComprobante, Venta
from ventas.test_venta import _caja, _punto


@pytest.fixture
def caja(db):
    _punto(TipoComprobante.TICKET)
    _punto(TipoComprobante.FACTURA)
    return _caja()


def _mesa_servida(usuario, carta):  # noqa: F811
    """Mesa 1: dos rondas de cerveza y una milanesa, todo enviado."""
    comanda = comandas.abrir(usuario=usuario, mesa=carta["mesa"])
    comandas.agregar(comanda, carta["cerveza"], usuario=usuario, cantidad="2")
    comandas.agregar(comanda, carta["milanesa"], usuario=usuario)
    comandas.enviar(comanda, usuario=usuario)
    comandas.agregar(comanda, carta["cerveza"], usuario=usuario)
    comandas.enviar(comanda, usuario=usuario)
    return comanda


def _lineas(venta):
    return sorted(
        (d.item.descripcion, d.cantidad, d.precio, d.subtotal) for d in venta.detalles.all()
    )


# --- Pasar a la venta ----------------------------------------------------------


@pytest.mark.django_db
def test_pasar_a_venta_agrupa_y_respeta_el_precio_cargado(usuario, carta, caja):  # noqa: F811
    comanda = _mesa_servida(usuario, carta)
    Item.objects.filter(pk=carta["cerveza"].pk).update(precio=Decimal("20000"))

    venta = cobro.pasar_a_venta(comanda, usuario=usuario)

    assert venta.estado == EstadoVenta.EN_CURSO
    assert venta.usuario == usuario
    assert _lineas(venta) == [
        ("Cerveza", Decimal("3"), Decimal("15000"), Decimal("45000")),
        ("Milanesa", Decimal("1"), Decimal("45000"), Decimal("45000")),
    ]
    assert not comanda.detalles.filter(venta_detalle__isnull=True).exists()
    assert cobro.venta_en_caja(comanda) == venta


@pytest.mark.django_db
def test_la_cuenta_con_cliente_lo_precarga(usuario, carta, caja):  # noqa: F811
    cliente = Persona.objects.create(
        tipo_documento=TipoDocumento.RUC,
        documento="80009735-8",
        razon_social="Cliente SA",
        genero=Genero.SIN_DEFINIR,
        direccion="Centro",
        es_cliente=True,
    )
    comanda = comandas.abrir(usuario=usuario, nombre="Oficina", cliente=cliente)
    comandas.agregar(comanda, carta["cerveza"], usuario=usuario)
    comandas.enviar(comanda, usuario=usuario)

    venta = cobro.pasar_a_venta(comanda, usuario=usuario)

    assert venta.cliente == cliente


@pytest.mark.django_db
def test_no_se_cobra_con_cosas_sin_enviar_ni_vacia(usuario, carta, caja):  # noqa: F811
    comanda = comandas.abrir(usuario=usuario, mesa=carta["mesa"])
    with pytest.raises(ValidationError, match="nada para cobrar"):
        cobro.pasar_a_venta(comanda, usuario=usuario)

    comandas.agregar(comanda, carta["cerveza"], usuario=usuario)
    with pytest.raises(ValidationError, match="sin enviar"):
        cobro.pasar_a_venta(comanda, usuario=usuario)


@pytest.mark.django_db
def test_con_una_venta_empezada_no_se_mezcla(usuario, carta, caja):  # noqa: F811
    comanda = _mesa_servida(usuario, carta)
    from ventas.cobro import borrador

    agregar_producto(borrador(usuario), item=carta["helado"])

    with pytest.raises(ValidationError, match="Terminala o cancelala"):
        cobro.pasar_a_venta(comanda, usuario=usuario)
    assert not comanda.detalles.filter(venta_detalle__isnull=False).exists()


@pytest.mark.django_db
def test_cobrar_dos_veces_no_duplica(usuario, carta, caja):  # noqa: F811
    comanda = _mesa_servida(usuario, carta)

    primera = cobro.pasar_a_venta(comanda, usuario=usuario)
    segunda = cobro.pasar_a_venta(comanda, usuario=usuario)

    assert primera == segunda
    assert primera.detalles.count() == 2


@pytest.mark.django_db
def test_no_se_cobra_en_dos_cajas(usuario, django_user_model, carta, caja):  # noqa: F811
    comanda = _mesa_servida(usuario, carta)
    cobro.pasar_a_venta(comanda, usuario=usuario)
    otro = django_user_model.objects.create_user("beto", "beto@rupia.local", "x")

    with pytest.raises(ValidationError, match="caja de ada"):
        cobro.pasar_a_venta(comanda, usuario=otro)


# --- En el punto de venta ------------------------------------------------------


@pytest.mark.django_db
def test_en_el_pos_la_linea_de_mesa_no_cambia_ni_se_mezcla(usuario, carta, caja):  # noqa: F811
    comanda = _mesa_servida(usuario, carta)
    venta = cobro.pasar_a_venta(comanda, usuario=usuario)
    cerveza = venta.detalles.get(item=carta["cerveza"])
    Item.objects.filter(pk=carta["cerveza"].pk).update(precio=Decimal("20000"))

    with pytest.raises(ValidationError, match="viene de una mesa"):
        cambiar_cantidad(cerveza, 5)
    nueva = agregar_producto(venta, item=Item.objects.get(pk=carta["cerveza"].pk))
    cambiar_descuento(cerveza, "10")

    cerveza.refresh_from_db()
    assert nueva.pk != cerveza.pk
    assert nueva.precio == Decimal("20000")
    assert cerveza.cantidad == Decimal("3")
    assert cerveza.precio == Decimal("15000")
    assert cerveza.subtotal == Decimal("40500")


@pytest.mark.django_db
def test_quitar_la_linea_la_devuelve_a_la_mesa(usuario, carta, caja):  # noqa: F811
    comanda = _mesa_servida(usuario, carta)
    venta = cobro.pasar_a_venta(comanda, usuario=usuario)

    quitar_linea(venta.detalles.get(item=carta["milanesa"]))

    milanesa = comanda.detalles.get(item=carta["milanesa"])
    assert milanesa.venta_detalle is None
    assert comanda.detalles.filter(venta_detalle__isnull=False).count() == 2


@pytest.mark.django_db
def test_cancelar_la_venta_devuelve_todo_a_la_mesa(usuario, carta, caja):  # noqa: F811
    comanda = _mesa_servida(usuario, carta)
    venta = cobro.pasar_a_venta(comanda, usuario=usuario)

    cancelar(venta)

    assert not ComandaDetalle.objects.filter(venta_detalle__isnull=False).exists()
    assert cobro.venta_en_caja(comanda) is None
    comanda.refresh_from_db()
    assert comanda.activa


@pytest.mark.django_db
def test_lo_que_esta_en_caja_no_se_anula(usuario, carta, caja):  # noqa: F811
    comanda = _mesa_servida(usuario, carta)
    cobro.pasar_a_venta(comanda, usuario=usuario)
    detalle = comanda.detalles.filter(item=carta["milanesa"]).get()

    with pytest.raises(ValidationError, match="ya está en la caja"):
        comandas.anular_linea(detalle, usuario=usuario, motivo="No quiso")
    with pytest.raises(ValidationError, match="ya está en la caja"):
        comandas.anular_comanda(comanda, usuario=usuario, motivo="Se fueron")


# --- Confirmar -----------------------------------------------------------------


@pytest.mark.django_db
def test_confirmar_la_venta_cierra_la_mesa(usuario, carta, caja):  # noqa: F811
    comanda = _mesa_servida(usuario, carta)
    venta = cobro.pasar_a_venta(comanda, usuario=usuario)

    confirmar(venta)

    comanda.refresh_from_db()
    assert comanda.estado == EstadoComanda.CERRADA
    assert comanda.cerrada_en is not None
    assert comandas.comanda_de_mesa(carta["mesa"]) is None
    # La mesa queda libre para la próxima.
    assert comandas.abrir(usuario=usuario, mesa=carta["mesa"]).activa


@pytest.mark.django_db
def test_lo_pedido_mientras_se_cobra_queda_abierto(usuario, carta, caja):  # noqa: F811
    comanda = _mesa_servida(usuario, carta)
    venta = cobro.pasar_a_venta(comanda, usuario=usuario)
    comandas.agregar(comanda, carta["helado"], usuario=usuario)
    comandas.enviar(comanda, usuario=usuario)

    confirmar(venta)

    comanda.refresh_from_db()
    assert comanda.estado == EstadoComanda.ABIERTA
    siguiente = cobro.pasar_a_venta(comanda, usuario=usuario)
    assert _lineas(siguiente) == [("Helado", Decimal("1"), Decimal("12000"), Decimal("12000"))]
    confirmar(siguiente)
    comanda.refresh_from_db()
    assert comanda.estado == EstadoComanda.CERRADA


@pytest.mark.django_db
def test_si_la_venta_falla_la_mesa_sigue_abierta(usuario, carta, caja):  # noqa: F811
    comanda = _mesa_servida(usuario, carta)
    venta = cobro.pasar_a_venta(comanda, usuario=usuario)
    venta.cuenta_cobro = None
    venta.save(update_fields=["cuenta_cobro"])

    with pytest.raises(ValidationError):
        confirmar(venta)

    comanda.refresh_from_db()
    assert comanda.estado == EstadoComanda.ABIERTA


# --- Pantallas -----------------------------------------------------------------


@pytest.mark.django_db
def test_recorrido_de_cobro_por_pantalla(ingresada, usuario, carta, caja):  # noqa: F811
    _habilitar()
    comanda = _mesa_servida(usuario, carta)

    pagina = ingresada.get(f"/mesas/comandas/{comanda.pk}/").content.decode()
    assert "Cobrar" in pagina

    response = ingresada.post(f"/mesas/comandas/{comanda.pk}/cobrar/")
    assert response.url == "/ventas/punto-de-venta/"

    pos = ingresada.get("/ventas/punto-de-venta/").content.decode()
    assert '<span class="pos-origen-mesa">Mesa 1</span>' in pos
    assert "Devolver a Mesa 1" in pos

    tablero = ingresada.get("/mesas/tablero/").content.decode()
    assert "En caja" in tablero
    pagina = ingresada.get(f"/mesas/comandas/{comanda.pk}/").content.decode()
    assert "se está cobrando en la caja de ada" in pagina
    assert "Ir a la caja" in pagina

    confirmada = ingresada.post("/ventas/punto-de-venta/confirmar/")
    venta = Venta.objects.get(estado=EstadoVenta.COBRADA)
    assert confirmada.url == f"/ventas/{venta.pk}/ticket/"
    assert venta.detalles.count() == 2
    comanda.refresh_from_db()
    assert comanda.estado == EstadoComanda.CERRADA
    assert "Ocupada" not in ingresada.get("/mesas/tablero/").content.decode()


@pytest.mark.django_db
def test_cobrar_pide_el_permiso(client, django_user_model, usuario, carta, caja):  # noqa: F811
    _habilitar()
    mozo = crear_usuario_con_permisos(
        django_user_model,
        ("comandas", "ver"),
        ("comandas", "alta"),
        ("punto_de_venta", "ver"),
        username="mozo",
    )
    client.force_login(mozo)
    comanda = _mesa_servida(usuario, carta)

    pagina = client.get(f"/mesas/comandas/{comanda.pk}/").content.decode()
    response = client.post(f"/mesas/comandas/{comanda.pk}/cobrar/")

    assert "comanda-cobrar" not in pagina
    assert response.status_code == 403


@pytest.mark.django_db
def test_cobrar_sin_punto_de_venta_avisa(client, django_user_model, usuario, carta, caja):  # noqa: F811
    _habilitar()
    cajero = crear_usuario_con_permisos(
        django_user_model, ("comandas", "ver"), ("comandas", "cobrar"), username="caja2"
    )
    client.force_login(cajero)
    comanda = _mesa_servida(usuario, carta)

    response = client.post(f"/mesas/comandas/{comanda.pk}/cobrar/", follow=True)

    assert "necesitás acceso al punto de venta" in response.content.decode()
    assert cobro.venta_en_caja(comanda) is None

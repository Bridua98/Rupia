from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from configuracion.models import Ajustes
from configuracion.testing import crear_usuario_con_permisos
from inventario.models import (
    Item,
    ItemCategoria,
    ItemMovimiento,
    Marca,
    TasaIva,
    TipoItem,
    TipoMovimiento,
    UnidadMedida,
)
from mesas import comandas as servicio
from mesas.models import (
    Comanda,
    ComandaAnulacion,
    EnvioSector,
    EstadoComanda,
    Mesa,
    Sector,
    SectorCategoria,
    TipoEnvio,
)
from negocio.models import UnidadNegocio

# --- Datos ---------------------------------------------------------------------


def _habilitar():
    ajustes = Ajustes.actuales()
    ajustes.mesas_habilitadas = True
    ajustes.save()


def _categoria(descripcion):
    return ItemCategoria.objects.get_or_create(descripcion=descripcion)[0]


def _item(descripcion, categoria, *, precio="15000", codigo=None, stock="50"):
    marca, _ = Marca.objects.get_or_create(descripcion="Genérica")
    unidad, _ = UnidadMedida.objects.get_or_create(descripcion="Unidad", defaults={"simbolo": "Un"})
    negocio, _ = UnidadNegocio.objects.get_or_create(
        abreviado="DEP", defaults={"descripcion": "Depósito"}
    )
    item = Item.objects.create(
        marca=marca,
        categoria=_categoria(categoria),
        unidad_medida=unidad,
        unidad_negocio=negocio,
        codigo_barra=codigo or descripcion.upper()[:20],
        descripcion=descripcion,
        tipo=TipoItem.PRODUCTO,
        activo=True,
        precio=Decimal(precio),
        tasa_iva=TasaIva.DIEZ,
        ultimo_costo=Decimal("5000"),
    )
    if stock:
        pk = (ItemMovimiento.objects.order_by("-id").values_list("id", flat=True).first() or 0) + 1
        ItemMovimiento.objects.create(
            id=pk,
            item=item,
            unidad_medida=unidad,
            tipo=TipoMovimiento.COMPRA,
            fecha_movimiento=date(2026, 10, 1),
            cantidad=Decimal(stock),
            precio=item.precio,
            costo=item.ultimo_costo,
            subtotal=item.precio,
            es_vigente=True,
        )
    return item


@pytest.fixture
def carta(db):
    """Barra recibe bebidas, cocina recibe platos; los postres no van a ningún lado."""
    barra = Sector.objects.create(nombre="Barra")
    cocina = Sector.objects.create(nombre="Cocina")
    SectorCategoria.objects.create(sector=barra, categoria=_categoria("Bebidas"))
    SectorCategoria.objects.create(sector=cocina, categoria=_categoria("Platos"))
    return {
        "barra": barra,
        "cocina": cocina,
        "cerveza": _item("Cerveza", "Bebidas", precio="15000"),
        "milanesa": _item("Milanesa", "Platos", precio="45000"),
        "helado": _item("Helado", "Postres", precio="12000"),
        "mesa": Mesa.objects.create(nombre="1", zona="Salón", capacidad=4),
    }


# --- Abrir ---------------------------------------------------------------------


@pytest.mark.django_db
def test_abrir_una_mesa_y_no_dos_veces(usuario, carta):
    comanda = servicio.abrir(usuario=usuario, mesa=carta["mesa"])

    assert comanda.estado == EstadoComanda.ABIERTA
    assert comanda.titulo == "Mesa 1"
    with pytest.raises(ValidationError, match="ya está ocupada"):
        servicio.abrir(usuario=usuario, mesa=carta["mesa"])


@pytest.mark.django_db
def test_mesa_inactiva_no_se_abre(usuario):
    mesa = Mesa.objects.create(nombre="9", activa=False)

    with pytest.raises(ValidationError, match="no está activa"):
        servicio.abrir(usuario=usuario, mesa=mesa)


@pytest.mark.django_db
def test_cuenta_a_nombre_pide_nombre_o_cliente(usuario):
    with pytest.raises(ValidationError, match="Elegí una mesa"):
        servicio.abrir(usuario=usuario, nombre="   ")

    comanda = servicio.abrir(usuario=usuario, nombre=" Juan barra ")
    assert comanda.titulo == "Juan barra"
    assert comanda.mesa is None


@pytest.mark.django_db
def test_al_cerrar_la_mesa_se_puede_volver_a_abrir(usuario, carta):
    primera = servicio.abrir(usuario=usuario, mesa=carta["mesa"])
    servicio.descartar(primera)

    segunda = servicio.abrir(usuario=usuario, mesa=carta["mesa"])

    assert segunda.pk != primera.pk


# --- Cargar --------------------------------------------------------------------


@pytest.mark.django_db
def test_cargar_suma_lo_mismo_sin_enviar_y_fija_el_precio(usuario, carta):
    comanda = servicio.abrir(usuario=usuario, mesa=carta["mesa"])
    servicio.agregar(comanda, carta["cerveza"], usuario=usuario)
    servicio.agregar(comanda, carta["cerveza"], usuario=usuario)
    servicio.agregar(comanda, carta["cerveza"], usuario=usuario, nota="sin hielo")

    Item.objects.filter(pk=carta["cerveza"].pk).update(precio=Decimal("20000"))
    servicio.agregar(comanda, carta["milanesa"], usuario=usuario)

    lineas = list(comanda.detalles.order_by("id"))
    assert [(d.item.descripcion, d.cantidad, d.nota) for d in lineas] == [
        ("Cerveza", Decimal("2"), ""),
        ("Cerveza", Decimal("1"), "sin hielo"),
        ("Milanesa", Decimal("1"), ""),
    ]
    assert lineas[0].precio == Decimal("15000")
    assert servicio.total(comanda) == Decimal("90000")


@pytest.mark.django_db
def test_lo_enviado_no_se_suma_con_lo_nuevo(usuario, carta):
    comanda = servicio.abrir(usuario=usuario, mesa=carta["mesa"])
    servicio.agregar(comanda, carta["cerveza"], usuario=usuario)
    servicio.enviar(comanda, usuario=usuario)

    servicio.agregar(comanda, carta["cerveza"], usuario=usuario)

    assert comanda.detalles.count() == 2


@pytest.mark.django_db
def test_sin_stock_avisa_pero_carga(usuario, carta):
    agua = _item("Agua", "Bebidas", precio="8000", stock="1")
    comanda = servicio.abrir(usuario=usuario, mesa=carta["mesa"])

    primera = servicio.agregar(comanda, agua, usuario=usuario)
    segunda = servicio.agregar(comanda, agua, usuario=usuario)

    assert primera.aviso == ""
    assert "no hay stock suficiente de Agua" in segunda.aviso
    assert comanda.detalles.get().cantidad == Decimal("2")


@pytest.mark.django_db
def test_no_se_carga_un_producto_sin_precio_o_inactivo(usuario, carta):
    comanda = servicio.abrir(usuario=usuario, mesa=carta["mesa"])
    inactivo = _item("Viejo", "Platos")
    inactivo.activo = False
    inactivo.save()

    with pytest.raises(ValidationError, match="no está a la venta"):
        servicio.agregar(comanda, inactivo, usuario=usuario)


@pytest.mark.django_db
def test_lo_enviado_no_se_corrige_sin_anular(usuario, carta):
    comanda = servicio.abrir(usuario=usuario, mesa=carta["mesa"])
    carga = servicio.agregar(comanda, carta["cerveza"], usuario=usuario)
    servicio.enviar(comanda, usuario=usuario)
    carga.detalle.refresh_from_db()

    with pytest.raises(ValidationError, match="anularlo con un motivo"):
        servicio.cambiar_pendiente(carga.detalle, cantidad=3)
    with pytest.raises(ValidationError, match="anularlo con un motivo"):
        servicio.quitar_pendiente(carga.detalle)


@pytest.mark.django_db
def test_cantidad_cero_saca_la_linea_pendiente(usuario, carta):
    comanda = servicio.abrir(usuario=usuario, mesa=carta["mesa"])
    carga = servicio.agregar(comanda, carta["cerveza"], usuario=usuario)

    assert servicio.cambiar_pendiente(carga.detalle, cantidad="0") is None
    assert not comanda.detalles.exists()


# --- Enviar --------------------------------------------------------------------


@pytest.mark.django_db
def test_enviar_reparte_por_sector(usuario, carta):
    comanda = servicio.abrir(usuario=usuario, mesa=carta["mesa"])
    servicio.agregar(comanda, carta["cerveza"], usuario=usuario, cantidad="2")
    servicio.agregar(comanda, carta["milanesa"], usuario=usuario, nota="bien cocida")
    servicio.agregar(comanda, carta["helado"], usuario=usuario)

    ronda = servicio.enviar(comanda, usuario=usuario)

    assert ronda.numero == 1
    envios = {envio.sector.nombre: envio for envio in ronda.envios.all()}
    assert set(envios) == {"Barra", "Cocina"}
    barra = list(envios["Barra"].lineas.values_list("descripcion", "cantidad"))
    assert barra == [("Cerveza", Decimal("2"))]
    cocina = envios["Cocina"].lineas.get()
    assert (cocina.descripcion, cocina.nota) == ("Milanesa", "bien cocida")
    helado = comanda.detalles.get(item=carta["helado"])
    assert helado.ronda == ronda
    assert helado.sector is None


@pytest.mark.django_db
def test_las_rondas_se_numeran_y_no_se_envia_vacio(usuario, carta):
    comanda = servicio.abrir(usuario=usuario, mesa=carta["mesa"])
    servicio.agregar(comanda, carta["cerveza"], usuario=usuario)
    servicio.enviar(comanda, usuario=usuario)

    with pytest.raises(ValidationError, match="nada nuevo"):
        servicio.enviar(comanda, usuario=usuario)

    servicio.agregar(comanda, carta["milanesa"], usuario=usuario)
    assert servicio.enviar(comanda, usuario=usuario).numero == 2


# --- Anular --------------------------------------------------------------------


@pytest.mark.django_db
def test_anular_parte_de_lo_enviado_avisa_al_sector(usuario, carta):
    comanda = servicio.abrir(usuario=usuario, mesa=carta["mesa"])
    carga = servicio.agregar(comanda, carta["cerveza"], usuario=usuario, cantidad="3")
    servicio.enviar(comanda, usuario=usuario)

    with pytest.raises(ValidationError, match="motivo"):
        servicio.anular_linea(carga.detalle, usuario=usuario, motivo="  ")
    detalle = servicio.anular_linea(
        carga.detalle, usuario=usuario, motivo="Se equivocó", cantidad="1"
    )

    assert detalle.cantidad == Decimal("2")
    assert detalle.anulado is False
    anulacion = ComandaAnulacion.objects.get()
    assert (anulacion.cantidad, anulacion.motivo) == (Decimal("1"), "Se equivocó")
    aviso = EnvioSector.objects.get(tipo=TipoEnvio.ANULACION)
    assert aviso.sector == carta["barra"]
    assert aviso.lineas.get().cantidad == Decimal("1")
    assert servicio.total(comanda) == Decimal("30000")


@pytest.mark.django_db
def test_anular_todo_deja_la_linea_anulada(usuario, carta):
    comanda = servicio.abrir(usuario=usuario, mesa=carta["mesa"])
    carga = servicio.agregar(comanda, carta["helado"], usuario=usuario, cantidad="2")
    servicio.enviar(comanda, usuario=usuario)

    detalle = servicio.anular_linea(carga.detalle, usuario=usuario, motivo="No quiso")

    assert detalle.anulado is True
    assert servicio.total(comanda) == Decimal("0")
    # El helado no tiene sector: queda registrado pero no se avisa a nadie.
    assert not EnvioSector.objects.filter(tipo=TipoEnvio.ANULACION).exists()
    with pytest.raises(ValidationError, match="ya está anulada"):
        servicio.anular_linea(detalle, usuario=usuario, motivo="otra vez")


@pytest.mark.django_db
def test_no_se_anula_mas_de_lo_pedido_ni_lo_pendiente(usuario, carta):
    comanda = servicio.abrir(usuario=usuario, mesa=carta["mesa"])
    carga = servicio.agregar(comanda, carta["cerveza"], usuario=usuario)

    with pytest.raises(ValidationError, match="sacalo directamente"):
        servicio.anular_linea(carga.detalle, usuario=usuario, motivo="x")

    servicio.enviar(comanda, usuario=usuario)
    with pytest.raises(ValidationError, match="entre 1 y lo pedido"):
        servicio.anular_linea(carga.detalle, usuario=usuario, motivo="x", cantidad="5")


@pytest.mark.django_db
def test_anular_la_cuenta_libera_la_mesa(usuario, carta):
    comanda = servicio.abrir(usuario=usuario, mesa=carta["mesa"])
    servicio.agregar(comanda, carta["cerveza"], usuario=usuario)
    servicio.agregar(comanda, carta["milanesa"], usuario=usuario)
    servicio.enviar(comanda, usuario=usuario)
    servicio.agregar(comanda, carta["helado"], usuario=usuario)

    servicio.anular_comanda(comanda, usuario=usuario, motivo="Se fueron")

    comanda.refresh_from_db()
    assert comanda.estado == EstadoComanda.ANULADA
    assert comanda.motivo_anulacion == "Se fueron"
    assert servicio.comanda_de_mesa(carta["mesa"]) is None
    avisos = EnvioSector.objects.filter(tipo=TipoEnvio.ANULACION)
    assert set(avisos.values_list("sector__nombre", flat=True)) == {"Barra", "Cocina"}
    assert not comanda.detalles.filter(ronda__isnull=True).exists()


@pytest.mark.django_db
def test_descartar_solo_si_no_se_envio_nada(usuario, carta):
    comanda = servicio.abrir(usuario=usuario, mesa=carta["mesa"])
    servicio.agregar(comanda, carta["cerveza"], usuario=usuario)
    servicio.enviar(comanda, usuario=usuario)

    with pytest.raises(ValidationError, match="anularla con un motivo"):
        servicio.descartar(comanda)


# --- Cuenta --------------------------------------------------------------------


@pytest.mark.django_db
def test_pedir_la_cuenta_exige_todo_enviado(usuario, carta):
    comanda = servicio.abrir(usuario=usuario, mesa=carta["mesa"])

    with pytest.raises(ValidationError, match="no tiene consumo"):
        servicio.pedir_cuenta(comanda)
    servicio.agregar(comanda, carta["cerveza"], usuario=usuario)
    with pytest.raises(ValidationError, match="sin enviar"):
        servicio.pedir_cuenta(comanda)

    servicio.enviar(comanda, usuario=usuario)
    assert servicio.pedir_cuenta(comanda).estado == EstadoComanda.CUENTA_PEDIDA


@pytest.mark.django_db
def test_pedir_algo_mas_reabre_la_cuenta(usuario, carta):
    comanda = servicio.abrir(usuario=usuario, mesa=carta["mesa"])
    servicio.agregar(comanda, carta["cerveza"], usuario=usuario)
    servicio.enviar(comanda, usuario=usuario)
    servicio.pedir_cuenta(comanda)

    servicio.agregar(comanda, carta["helado"], usuario=usuario)

    comanda.refresh_from_db()
    assert comanda.estado == EstadoComanda.ABIERTA


@pytest.mark.django_db
def test_una_cuenta_cerrada_no_se_toca(usuario, carta):
    comanda = servicio.abrir(usuario=usuario, mesa=carta["mesa"])
    servicio.agregar(comanda, carta["cerveza"], usuario=usuario)
    servicio.enviar(comanda, usuario=usuario)
    servicio.anular_comanda(comanda, usuario=usuario, motivo="Prueba")

    with pytest.raises(ValidationError, match="ya está cerrada"):
        servicio.agregar(comanda, carta["cerveza"], usuario=usuario)


# --- Pantallas -----------------------------------------------------------------


@pytest.mark.django_db
def test_el_tablero_pide_el_modulo_prendido(ingresada):
    assert ingresada.get("/mesas/tablero/").status_code == 404


@pytest.mark.django_db
def test_el_tablero_muestra_libres_ocupadas_y_a_nombre(ingresada, usuario, carta):
    _habilitar()
    Mesa.objects.create(nombre="2", zona="Salón")
    comanda = servicio.abrir(usuario=usuario, mesa=carta["mesa"])
    servicio.agregar(comanda, carta["cerveza"], usuario=usuario, cantidad="2")
    servicio.abrir(usuario=usuario, nombre="Juan barra")

    response = ingresada.get("/mesas/tablero/")
    parcial = ingresada.get("/mesas/tablero/?parcial=1")

    content = response.content.decode()
    assert response.status_code == 200
    assert "1 libre" in content
    assert "1 ocupada" in content
    assert "Gs. 30.000" in content
    assert "1 sin enviar" in content
    assert "Juan barra" in content
    assert f'href="/mesas/comandas/{comanda.pk}/"' in content
    assert "<html" not in parcial.content.decode()
    assert "Juan barra" in parcial.content.decode()


@pytest.mark.django_db
def test_tocar_una_mesa_libre_la_abre(ingresada, carta):
    _habilitar()

    response = ingresada.post("/mesas/comandas/abrir/", {"mesa": carta["mesa"].pk})
    otra_vez = ingresada.post("/mesas/comandas/abrir/", {"mesa": carta["mesa"].pk})

    comanda = Comanda.objects.get()
    assert response.url == f"/mesas/comandas/{comanda.pk}/"
    assert otra_vez.url == f"/mesas/comandas/{comanda.pk}/"


@pytest.mark.django_db
def test_abrir_cuenta_a_nombre_desde_el_tablero(ingresada):
    _habilitar()

    vacia = ingresada.post("/mesas/comandas/abrir/", {"nombre": ""}, follow=True)
    ingresada.post("/mesas/comandas/abrir/", {"nombre": "Cumple de Ana", "personas": "6"})

    assert "Escribí un nombre o elegí un cliente." in vacia.content.decode()
    comanda = Comanda.objects.get()
    assert (comanda.nombre, comanda.personas, comanda.mesa) == ("Cumple de Ana", 6, None)


@pytest.mark.django_db
def test_recorrido_cargar_enviar_y_pedir_cuenta(ingresada, carta):
    _habilitar()
    ingresada.post("/mesas/comandas/abrir/", {"mesa": carta["mesa"].pk})
    comanda = Comanda.objects.get()
    base = f"/mesas/comandas/{comanda.pk}/"

    busqueda = ingresada.get(base, {"q": "cerv"})
    assert "Cerveza" in busqueda.content.decode()

    ingresada.post(f"{base}agregar/", {"item": carta["cerveza"].pk, "q": "cerv"})
    ingresada.post(f"{base}agregar/", {"item": carta["milanesa"].pk})
    detalle = comanda.detalles.get(item=carta["cerveza"])
    ingresada.post(f"/mesas/comandas/lineas/{detalle.pk}/", {"accion": "mas"})
    ingresada.post(f"/mesas/comandas/lineas/{detalle.pk}/", {"accion": "nota", "nota": "bien fría"})
    detalle.refresh_from_db()
    assert (detalle.cantidad, detalle.nota) == (Decimal("2"), "bien fría")

    enviado = ingresada.post(f"{base}enviar/", follow=True)
    assert "Ronda 1 enviada a Barra, Cocina." in enviado.content.decode()

    cuenta = ingresada.post(f"{base}cuenta/")
    assert cuenta.url == f"{base}precuenta/"
    precuenta = ingresada.get(f"{base}precuenta/").content.decode()
    assert "PRE-CUENTA" in precuenta
    assert "No válido como comprobante" in precuenta
    assert "Gs. 75.000" in precuenta
    comanda.refresh_from_db()
    assert comanda.estado == EstadoComanda.CUENTA_PEDIDA


@pytest.mark.django_db
def test_la_precuenta_agrupa_y_divide_por_persona(ingresada, usuario, carta):
    _habilitar()
    comanda = servicio.abrir(usuario=usuario, mesa=carta["mesa"], personas=3)
    servicio.agregar(comanda, carta["cerveza"], usuario=usuario)
    servicio.enviar(comanda, usuario=usuario)
    servicio.agregar(comanda, carta["cerveza"], usuario=usuario, cantidad="2")
    servicio.enviar(comanda, usuario=usuario)

    content = ingresada.get(f"/mesas/comandas/{comanda.pk}/precuenta/").content.decode()

    assert content.count('<td class="ticket-desc">Cerveza</td>') == 1
    assert "Gs. 45.000" in content
    assert "Por persona (3)" in content
    assert "Gs. 15.000" in content


@pytest.mark.django_db
def test_el_mozo_sin_permiso_de_anular_no_anula(client, django_user_model, usuario, carta):
    _habilitar()
    mozo = crear_usuario_con_permisos(
        django_user_model, ("comandas", "ver"), ("comandas", "alta"), username="mozo"
    )
    client.force_login(mozo)
    comanda = servicio.abrir(usuario=usuario, mesa=carta["mesa"])
    carga = servicio.agregar(comanda, carta["cerveza"], usuario=usuario)
    servicio.enviar(comanda, usuario=usuario)

    pagina = client.get(f"/mesas/comandas/{comanda.pk}/").content.decode()
    linea = client.post(f"/mesas/comandas/lineas/{carga.detalle.pk}/anular/", {"motivo": "no"})
    cuenta = client.post(f"/mesas/comandas/{comanda.pk}/anular/", {"motivo": "no"})

    assert "Anular la cuenta" not in pagina
    assert linea.status_code == 403
    assert cuenta.status_code == 403
    assert not ComandaAnulacion.objects.exists()


@pytest.mark.django_db
def test_quien_solo_ve_no_abre_ni_carga(client, django_user_model, usuario, carta):
    _habilitar()
    cajero = crear_usuario_con_permisos(django_user_model, ("comandas", "ver"), username="vista")
    client.force_login(cajero)
    comanda = servicio.abrir(usuario=usuario, mesa=carta["mesa"])

    tablero = client.get("/mesas/tablero/").content.decode()
    abrir = client.post("/mesas/comandas/abrir/", {"nombre": "X"})
    agregar = client.post(f"/mesas/comandas/{comanda.pk}/agregar/", {"item": carta["cerveza"].pk})

    assert "Cuenta a nombre" not in tablero
    assert abrir.status_code == 403
    assert agregar.status_code == 403


@pytest.mark.django_db
def test_el_aviso_de_stock_llega_a_la_pantalla(ingresada, carta):
    _habilitar()
    agua = _item("Agua", "Bebidas", precio="8000", stock="")
    ingresada.post("/mesas/comandas/abrir/", {"mesa": carta["mesa"].pk})
    comanda = Comanda.objects.get()

    response = ingresada.post(
        f"/mesas/comandas/{comanda.pk}/agregar/", {"item": agua.pk}, follow=True
    )

    assert "no hay stock suficiente de Agua" in response.content.decode()
    assert comanda.detalles.count() == 1

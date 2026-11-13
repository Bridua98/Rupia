from decimal import Decimal

import pytest

from configuracion.models import Ajustes
from configuracion.testing import crear_usuario_con_permisos
from inventario.models import Item, ItemCategoria, Marca, TasaIva, TipoItem, UnidadMedida
from mesas.models import Mesa, Sector, SectorCategoria, SectorItem
from mesas.ruteo import sector_de
from negocio.models import UnidadNegocio


def _habilitar(valor=True):
    ajustes = Ajustes.actuales()
    ajustes.mesas_habilitadas = valor
    ajustes.save()


def _categoria(descripcion="Bebidas"):
    return ItemCategoria.objects.get_or_create(descripcion=descripcion)[0]


def _item(descripcion="Cerveza", categoria=None, codigo="BEB-001"):
    marca, _ = Marca.objects.get_or_create(descripcion="Genérica")
    unidad, _ = UnidadMedida.objects.get_or_create(descripcion="Unidad", defaults={"simbolo": "Un"})
    negocio, _ = UnidadNegocio.objects.get_or_create(
        abreviado="DEP", defaults={"descripcion": "Depósito"}
    )
    return Item.objects.create(
        marca=marca,
        categoria=categoria or _categoria(),
        unidad_medida=unidad,
        unidad_negocio=negocio,
        codigo_barra=codigo,
        descripcion=descripcion,
        tipo=TipoItem.PRODUCTO,
        activo=True,
        precio=Decimal("15000"),
        tasa_iva=TasaIva.DIEZ,
        ultimo_costo=Decimal("9000"),
    )


def _etiquetas_menu(client):
    return [entrada["label"] for entrada in client.get("/").context["menu"]]


# --- Módulo apagado / prendido -------------------------------------------------


@pytest.mark.django_db
def test_con_el_modulo_apagado_no_hay_menu_ni_pantallas(ingresada):
    assert "Mesas" not in _etiquetas_menu(ingresada)
    assert ingresada.get("/mesas/").status_code == 404
    assert ingresada.get("/mesas/sectores/").status_code == 404
    assert ingresada.get("/mesas/sectores/productos/").status_code == 404


@pytest.mark.django_db
def test_con_el_modulo_prendido_aparece_el_grupo_mesas(ingresada):
    _habilitar()

    menu = ingresada.get("/").context["menu"]
    mesas = next(entrada for entrada in menu if entrada["label"] == "Mesas")

    assert [hijo["label"] for hijo in mesas["children"]] == [
        "Tablero",
        "Mesas",
        "Sectores de preparación",
        "Productos con otro sector",
    ]
    assert ingresada.get("/mesas/").status_code == 200


@pytest.mark.django_db
def test_sin_permiso_no_ve_las_mesas(client, django_user_model):
    _habilitar()
    usuario = crear_usuario_con_permisos(django_user_model, ("punto_de_venta", "ver"))
    client.force_login(usuario)

    assert "Mesas" not in _etiquetas_menu(client)
    assert client.get("/mesas/").status_code == 403


# --- Ajustes generales ----------------------------------------------------------


@pytest.mark.django_db
def test_ajustes_prende_y_apaga_el_modulo(ingresada):
    response = ingresada.get("/configuracion/ajustes/")
    assert response.status_code == 200
    assert "Usar mesas y comandas" in response.content.decode()

    response = ingresada.post("/configuracion/ajustes/", {"mesas_habilitadas": "on"})
    assert response.status_code == 302
    assert Ajustes.actuales().mesas_habilitadas is True

    ingresada.post("/configuracion/ajustes/", {})
    assert Ajustes.actuales().mesas_habilitadas is False


@pytest.mark.django_db
def test_ajustes_sin_permiso_de_modificar_no_graba(client, django_user_model):
    usuario = crear_usuario_con_permisos(django_user_model, ("ajustes", "ver"))
    client.force_login(usuario)

    assert client.get("/configuracion/ajustes/").status_code == 200
    response = client.post("/configuracion/ajustes/", {"mesas_habilitadas": "on"})

    assert response.status_code == 403
    assert Ajustes.actuales().mesas_habilitadas is False


@pytest.mark.django_db
def test_ajustes_es_una_sola_fila():
    Ajustes(mesas_habilitadas=True).save()
    Ajustes(mesas_habilitadas=False).save()

    assert Ajustes.objects.count() == 1
    assert Ajustes.actuales().mesas_habilitadas is False


# --- Mesas ----------------------------------------------------------------------


@pytest.mark.django_db
def test_alta_de_mesa(ingresada):
    _habilitar()

    response = ingresada.post(
        "/mesas/nueva/",
        {"nombre": " 12 ", "zona": "Terraza", "capacidad": "4", "orden": "", "activa": "on"},
    )

    assert response.status_code == 302
    mesa = Mesa.objects.get()
    assert (mesa.nombre, mesa.zona, mesa.capacidad, mesa.orden, mesa.activa) == (
        "12",
        "Terraza",
        4,
        0,
        True,
    )


@pytest.mark.django_db
def test_mesa_sin_nombre_o_repetida_no_graba(ingresada):
    _habilitar()
    Mesa.objects.create(nombre="1")

    vacia = ingresada.post("/mesas/nueva/", {"nombre": "  "})
    repetida = ingresada.post("/mesas/nueva/", {"nombre": "1"})

    assert "Escribí el nombre o número de la mesa." in vacia.content.decode()
    assert "Ya hay una mesa con ese nombre." in repetida.content.decode()
    assert Mesa.objects.count() == 1


@pytest.mark.django_db
def test_mesa_con_capacidad_cero_no_graba(ingresada):
    _habilitar()

    response = ingresada.post("/mesas/nueva/", {"nombre": "5", "capacidad": "0"})

    assert "La capacidad tiene que ser al menos 1." in response.content.decode()
    assert not Mesa.objects.exists()


# --- Sectores -------------------------------------------------------------------


@pytest.mark.django_db
def test_alta_de_sector_con_categorias(ingresada):
    _habilitar()
    bebidas = _categoria("Bebidas")
    tragos = _categoria("Tragos")
    _categoria("Platos")

    response = ingresada.post(
        "/mesas/sectores/nueva/",
        {"nombre": "Barra", "activo": "on", "categorias": [bebidas.pk, tragos.pk]},
    )

    assert response.status_code == 302
    barra = Sector.objects.get(nombre="Barra")
    assert set(barra.categorias.values_list("categoria__descripcion", flat=True)) == {
        "Bebidas",
        "Tragos",
    }


@pytest.mark.django_db
def test_editar_sector_saca_y_agrega_categorias(ingresada):
    _habilitar()
    bebidas = _categoria("Bebidas")
    tragos = _categoria("Tragos")
    barra = Sector.objects.create(nombre="Barra")
    SectorCategoria.objects.create(sector=barra, categoria=bebidas)

    ingresada.post(
        f"/mesas/sectores/{barra.pk}/",
        {"nombre": "Barra", "activo": "on", "categorias": [tragos.pk]},
    )

    assert list(barra.categorias.values_list("categoria_id", flat=True)) == [tragos.pk]


@pytest.mark.django_db
def test_una_categoria_no_puede_ir_a_dos_sectores(ingresada):
    _habilitar()
    bebidas = _categoria("Bebidas")
    barra = Sector.objects.create(nombre="Barra")
    SectorCategoria.objects.create(sector=barra, categoria=bebidas)

    response = ingresada.post(
        "/mesas/sectores/nueva/",
        {"nombre": "Cocina", "activo": "on", "categorias": [bebidas.pk]},
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert "Estas categorías ya van a otro sector: Bebidas" in content
    assert not Sector.objects.filter(nombre="Cocina").exists()


@pytest.mark.django_db
def test_el_formulario_avisa_a_que_sector_va_cada_categoria(ingresada):
    _habilitar()
    bebidas = _categoria("Bebidas")
    barra = Sector.objects.create(nombre="Barra")
    SectorCategoria.objects.create(sector=barra, categoria=bebidas)

    response = ingresada.get("/mesas/sectores/?nueva=1")

    assert "Bebidas (va a Barra)" in response.content.decode()


@pytest.mark.django_db
def test_producto_con_otro_sector(ingresada):
    _habilitar()
    cocina = Sector.objects.create(nombre="Cocina")
    item = _item("Licuado")

    response = ingresada.post(
        "/mesas/sectores/productos/nueva/",
        {"item": item.pk, "sector": cocina.pk},
    )
    repetido = ingresada.post(
        "/mesas/sectores/productos/nueva/",
        {"item": item.pk, "sector": cocina.pk},
    )

    assert response.status_code == 302
    assert SectorItem.objects.get().sector == cocina
    assert "Ese producto ya tiene un sector propio." in repetido.content.decode()


# --- Ruteo ----------------------------------------------------------------------


@pytest.mark.django_db
def test_el_producto_va_al_sector_de_su_categoria():
    bebidas = _categoria("Bebidas")
    barra = Sector.objects.create(nombre="Barra")
    SectorCategoria.objects.create(sector=barra, categoria=bebidas)

    assert sector_de(_item("Cerveza", bebidas)) == barra


@pytest.mark.django_db
def test_la_excepcion_por_producto_le_gana_a_la_categoria():
    bebidas = _categoria("Bebidas")
    barra = Sector.objects.create(nombre="Barra")
    cocina = Sector.objects.create(nombre="Cocina")
    SectorCategoria.objects.create(sector=barra, categoria=bebidas)
    licuado = _item("Licuado", bebidas)
    SectorItem.objects.create(item=licuado, sector=cocina)

    assert sector_de(licuado) == cocina


@pytest.mark.django_db
def test_excepcion_a_sector_inactivo_usa_el_de_la_categoria():
    bebidas = _categoria("Bebidas")
    barra = Sector.objects.create(nombre="Barra")
    parrilla = Sector.objects.create(nombre="Parrilla", activo=False)
    SectorCategoria.objects.create(sector=barra, categoria=bebidas)
    item = _item("Licuado", bebidas)
    SectorItem.objects.create(item=item, sector=parrilla)

    assert sector_de(item) == barra


@pytest.mark.django_db
def test_sin_sector_o_con_sector_inactivo_no_se_manda():
    bebidas = _categoria("Bebidas")
    agua = _item("Agua", bebidas)
    assert sector_de(agua) is None

    barra = Sector.objects.create(nombre="Barra", activo=False)
    SectorCategoria.objects.create(sector=barra, categoria=bebidas)
    assert sector_de(agua) is None

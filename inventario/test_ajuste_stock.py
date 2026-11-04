from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from configuracion.models import Perfil, PerfilPermiso
from inventario.models import (
    AjusteStock,
    AjusteStockDetalle,
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


def _negocio():
    unidad, _ = UnidadNegocio.objects.get_or_create(
        abreviado="DEP",
        defaults={"descripcion": "Depósito central"},
    )
    return unidad


def _producto(
    nombre,
    *,
    unidad=None,
    activo=True,
    tipo=TipoItem.PRODUCTO,
    precio="1500",
    costo="1000",
):
    if unidad is None:
        unidad = UnidadMedida.objects.create(
            descripcion=f"Unidad {nombre}",
            simbolo=f"U{nombre}"[:10],
        )
    marca = Marca.objects.create(descripcion=f"Marca {nombre}")
    categoria = ItemCategoria.objects.create(descripcion=f"Categoría {nombre}")
    return Item.objects.create(
        descripcion=nombre,
        tipo=tipo,
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        unidad_negocio=_negocio() if tipo == TipoItem.PRODUCTO else None,
        precio=Decimal(precio),
        ultimo_costo=Decimal(costo),
        tasa_iva=TasaIva.DIEZ,
        activo=activo,
    )


def _movimiento(item, cantidad, *, pk, tipo=TipoMovimiento.COMPRA, unidad=None, secuencia=""):
    return ItemMovimiento.objects.create(
        id=pk,
        item=item,
        unidad_medida=unidad or item.unidad_medida,
        tipo=tipo,
        fecha_movimiento=date(2026, 10, 1),
        cantidad=Decimal(cantidad),
        precio=item.precio or Decimal("0"),
        costo=item.ultimo_costo or Decimal("0"),
        subtotal=item.precio or Decimal("0"),
        secuencia_origen=secuencia or None,
        es_vigente=True,
    )


def _datos(detalles, *, fecha=None, observacion="Conteo", iniciales=0):
    fecha = fecha or timezone.localdate().isoformat()
    data = {
        "fecha": fecha,
        "observacion": observacion,
        "detalles-TOTAL_FORMS": str(len(detalles)),
        "detalles-INITIAL_FORMS": str(iniciales),
        "detalles-MIN_NUM_FORMS": "1",
        "detalles-MAX_NUM_FORMS": "1000",
    }
    for indice, detalle in enumerate(detalles):
        item = detalle["item"]
        unidad = detalle.get("unidad") or item.unidad_medida
        data[f"detalles-{indice}-item"] = str(item.pk)
        data[f"detalles-{indice}-unidad_medida"] = str(unidad.pk)
        data[f"detalles-{indice}-cantidad_nueva"] = str(detalle["cantidad"])
        if detalle.get("id"):
            data[f"detalles-{indice}-id"] = str(detalle["id"])
        if detalle.get("delete"):
            data[f"detalles-{indice}-DELETE"] = "on"
    return data


def _crear(ingresada, detalles, **kwargs):
    return ingresada.post("/inventario/ajustes/nuevo/", _datos(detalles, **kwargs))


@pytest.mark.django_db
def test_menu_muestra_ajustes_de_stock(ingresada):
    response = ingresada.get("/")

    content = response.content.decode()
    assert response.status_code == 200
    assert 'href="/inventario/ajustes/"' in content
    assert "Ajustes de stock" in content


@pytest.mark.django_db
def test_formulario_alta_renderiza(ingresada):
    response = ingresada.get("/inventario/ajustes/nuevo/")

    content = response.content.decode()
    assert response.status_code == 200
    assert "data-ajuste-stock" in content
    assert "detalles-TOTAL_FORMS" in content
    assert "Agregar detalle" in content
    assert "Guardar ajuste" in content


@pytest.mark.django_db
def test_formulario_edicion_renderiza(ingresada):
    item = _producto("Producto")
    _movimiento(item, "10", pk=1)
    _crear(ingresada, [{"item": item, "cantidad": "8"}])
    ajuste = AjusteStock.objects.get()

    response = ingresada.get(f"/inventario/ajustes/{ajuste.pk}/editar/")

    content = response.content.decode()
    assert response.status_code == 200
    assert f"Ajuste de stock N.º {ajuste.pk}" in content
    assert "Producto" in content
    assert "detalles-INITIAL_FORMS" in content


@pytest.mark.django_db
def test_alta_crea_detalle_y_movimiento_negativo(ingresada):
    item = _producto("Arroz")
    _movimiento(item, "10", pk=1)

    response = _crear(ingresada, [{"item": item, "cantidad": "8"}])

    assert response.status_code == 302
    ajuste = AjusteStock.objects.get()
    detalle = ajuste.detalles.get()
    assert detalle.cantidad_anterior == Decimal("10.000")
    assert detalle.cantidad_nueva == Decimal("8.000")
    assert detalle.cantidad == Decimal("-2.000")
    movimiento = ItemMovimiento.objects.get(secuencia_origen=f"A{ajuste.pk}")
    assert movimiento.tipo == TipoMovimiento.AJUSTE_NEGATIVO
    assert movimiento.cantidad == Decimal("2.000")
    assert movimiento.precio == Decimal("1500.000")
    assert movimiento.costo == Decimal("1000.000")
    assert movimiento.subtotal == Decimal("2000")
    assert movimiento.fecha_movimiento == timezone.localdate()
    assert movimiento.unidad_medida_id == item.unidad_medida_id


@pytest.mark.django_db
def test_alta_positiva_y_sin_diferencia(ingresada):
    sube = _producto("Sube")
    igual = _producto("Igual")
    _movimiento(sube, "10", pk=1)
    _movimiento(igual, "5", pk=2)

    response = _crear(
        ingresada,
        [
            {"item": sube, "cantidad": "12"},
            {"item": igual, "cantidad": "5"},
        ],
    )

    assert response.status_code == 302
    ajuste = AjusteStock.objects.get()
    detalles = {detalle.item_id: detalle for detalle in ajuste.detalles.all()}
    assert detalles[sube.pk].cantidad == Decimal("2.000")
    assert detalles[igual.pk].cantidad == Decimal("0.000")
    movimientos = ItemMovimiento.objects.filter(secuencia_origen=f"A{ajuste.pk}")
    assert movimientos.count() == 1
    assert movimientos.get().tipo == TipoMovimiento.AJUSTE_POSITIVO
    assert movimientos.get().cantidad == Decimal("2.000")


@pytest.mark.django_db
def test_cantidad_anterior_no_se_confia_del_post(ingresada):
    item = _producto("Producto")
    _movimiento(item, "10", pk=1)
    data = _datos([{"item": item, "cantidad": "8"}])
    data["detalles-0-cantidad_anterior"] = "999"

    response = ingresada.post("/inventario/ajustes/nuevo/", data)

    assert response.status_code == 302
    detalle = AjusteStock.objects.get().detalles.get()
    assert detalle.cantidad_anterior == Decimal("10.000")
    assert detalle.cantidad == Decimal("-2.000")


@pytest.mark.django_db
def test_edicion_desactiva_movimientos_y_recalcula(ingresada):
    item = _producto("Producto")
    _movimiento(item, "10", pk=1)
    _crear(ingresada, [{"item": item, "cantidad": "8"}])
    ajuste = AjusteStock.objects.get()
    detalle = ajuste.detalles.get()
    anterior = ItemMovimiento.objects.get(secuencia_origen=f"A{ajuste.pk}")

    response = ingresada.post(
        f"/inventario/ajustes/{ajuste.pk}/editar/",
        _datos(
            [{"item": item, "cantidad": "9", "id": detalle.pk}],
            iniciales=1,
        ),
    )

    assert response.status_code == 302
    anterior.refresh_from_db()
    detalle.refresh_from_db()
    assert anterior.es_vigente is False
    assert detalle.cantidad_anterior == Decimal("10.000")
    assert detalle.cantidad == Decimal("-1.000")
    nuevo = ItemMovimiento.objects.get(
        secuencia_origen=f"A{ajuste.pk}",
        es_vigente=True,
    )
    assert nuevo.tipo == TipoMovimiento.AJUSTE_NEGATIVO
    assert nuevo.cantidad == Decimal("1.000")


@pytest.mark.django_db
def test_eliminacion_desactiva_movimientos_y_borra_detalles(ingresada):
    item = _producto("Producto")
    _movimiento(item, "10", pk=1)
    _crear(ingresada, [{"item": item, "cantidad": "8"}])
    ajuste = AjusteStock.objects.get()
    movimiento = ItemMovimiento.objects.get(secuencia_origen=f"A{ajuste.pk}")

    response = ingresada.post(f"/inventario/ajustes/{ajuste.pk}/eliminar/")

    assert response.status_code == 302
    assert not AjusteStock.objects.exists()
    assert not AjusteStockDetalle.objects.exists()
    movimiento.refresh_from_db()
    assert movimiento.es_vigente is False


@pytest.mark.django_db
def test_exige_al_menos_un_detalle(ingresada):
    response = ingresada.post("/inventario/ajustes/nuevo/", _datos([]))

    assert response.status_code == 200
    assert "Agregá al menos un ítem al ajuste." in response.content.decode()
    assert not AjusteStock.objects.exists()


@pytest.mark.django_db
def test_no_permite_item_duplicado(ingresada):
    item = _producto("Producto")
    _movimiento(item, "10", pk=1)

    response = _crear(
        ingresada,
        [
            {"item": item, "cantidad": "8"},
            {"item": item, "cantidad": "7"},
        ],
    )

    assert response.status_code == 200
    assert "Ese ítem ya está en el ajuste." in response.content.decode()
    assert not AjusteStock.objects.exists()


@pytest.mark.django_db
def test_no_permite_gasto_ni_item_inactivo(ingresada):
    gasto = _producto("Gasto", tipo=TipoItem.GASTO)
    inactivo = _producto("Inactivo", activo=False)

    for item in (gasto, inactivo):
        response = _crear(ingresada, [{"item": item, "cantidad": "1"}])
        assert response.status_code == 200
        assert "Elegí un producto activo." in response.content.decode()
    assert not AjusteStock.objects.exists()


@pytest.mark.django_db
def test_no_permite_unidad_no_relacionada(ingresada):
    item = _producto("Producto")
    _movimiento(item, "10", pk=1)
    otra = UnidadMedida.objects.create(descripcion="Litro", simbolo="L")

    response = _crear(ingresada, [{"item": item, "unidad": otra, "cantidad": "8"}])

    assert response.status_code == 200
    assert "Esa unidad no está relacionada con el ítem." in response.content.decode()
    assert not AjusteStock.objects.exists()


@pytest.mark.django_db
def test_no_permite_cantidad_negativa(ingresada):
    item = _producto("Producto")
    _movimiento(item, "10", pk=1)

    response = _crear(ingresada, [{"item": item, "cantidad": "-1"}])

    assert response.status_code == 200
    assert "Escribí la cantidad." in response.content.decode()
    assert not AjusteStock.objects.exists()


@pytest.mark.django_db
def test_endpoint_item_devuelve_unidades_y_stock(ingresada):
    item = _producto("Vaso")
    caja = UnidadMedida.objects.create(descripcion="Caja", simbolo="CJA")
    ItemUnidad.objects.create(
        item=item,
        unidad_medida=caja,
        relacion=RelacionUnidad.MAYOR,
        valor=Decimal("12"),
    )
    _movimiento(item, "10", pk=1)

    response = ingresada.get(reverse("ajuste_stock_item", args=[item.pk]))

    assert response.status_code == 200
    data = response.json()
    assert data["stock_base"] == "10.000"
    assert data["item"]["unidad_base_id"] == item.unidad_medida_id
    unidades = {unidad["id"]: unidad for unidad in data["unidades"]}
    assert unidades[item.unidad_medida_id]["stock"] == "10.000"
    assert unidades[caja.pk]["stock"] == "0.833"
    assert data["aviso"] == ""


@pytest.mark.django_db
def test_endpoint_item_rechaza_gasto(ingresada):
    gasto = _producto("Gasto", tipo=TipoItem.GASTO)

    response = ingresada.get(reverse("ajuste_stock_item", args=[gasto.pk]))

    assert response.status_code == 404


@pytest.mark.django_db
def test_endpoint_item_sin_permiso(client, django_user_model):
    item = _producto("Producto")
    user = django_user_model.objects.create_user("sin-perfil", password="clave")
    client.force_login(user)

    response = client.get(reverse("ajuste_stock_item", args=[item.pk]))

    assert response.status_code == 403


@pytest.mark.django_db
def test_listado_panel_y_acciones(ingresada):
    item = _producto("Producto")
    _movimiento(item, "10", pk=1)
    _crear(ingresada, [{"item": item, "cantidad": "8"}], observacion="Conteo de prueba")
    ajuste = AjusteStock.objects.get()

    response = ingresada.get("/inventario/ajustes/")

    content = response.content.decode()
    assert response.status_code == 200
    assert "Ajustes de stock" in content
    assert "Conteo de prueba" in content
    assert f'href="/inventario/ajustes/{ajuste.pk}/editar/"' in content

    panel = ingresada.get(f"/inventario/ajustes/?ajuste={ajuste.pk}")
    contenido_panel = panel.content.decode()
    assert "view-panel" in contenido_panel
    assert "Producto" in contenido_panel
    assert f'href="/inventario/ajustes/{ajuste.pk}/editar/"' in contenido_panel


@pytest.mark.django_db
def test_permisos_solo_ver(client, django_user_model):
    item = _producto("Producto")
    _movimiento(item, "10", pk=1)
    user = django_user_model.objects.create_user("consulta", password="clave")
    perfil = Perfil.objects.create(descripcion="Consulta ajustes")
    PerfilPermiso.objects.create(
        perfil=perfil,
        formulario="ajustes_stock",
        accion="ver",
    )
    perfil.usuarios.add(user)
    client.force_login(user)

    lista = client.get("/inventario/ajustes/")
    content = lista.content.decode()
    assert lista.status_code == 200
    assert "Nuevo ajuste" not in content
    assert "/editar/" not in content
    assert "/eliminar/" not in content

    assert client.get("/inventario/ajustes/nuevo/").status_code == 403
    assert client.post("/inventario/ajustes/nuevo/", {}).status_code == 403
    assert client.get(reverse("ajuste_stock_item", args=[item.pk])).status_code == 200


@pytest.mark.django_db
def test_atomicidad_si_falla_un_movimiento(ingresada, monkeypatch):
    item = _producto("Producto")
    _movimiento(item, "10", pk=1)

    def falla(*args, **kwargs):
        raise ValidationError("Falla simulada.")

    monkeypatch.setattr("inventario.stock._registrar_movimientos", falla)

    response = _crear(ingresada, [{"item": item, "cantidad": "8"}])

    assert response.status_code == 200
    assert "Falla simulada." in response.content.decode()
    assert not AjusteStock.objects.exists()
    assert not AjusteStockDetalle.objects.exists()
    assert ItemMovimiento.objects.count() == 1


@pytest.mark.django_db
def test_ids_manuales_consecutivos(ingresada):
    item = _producto("Producto")
    _movimiento(item, "10", pk=1)
    _crear(ingresada, [{"item": item, "cantidad": "9"}])
    _crear(ingresada, [{"item": item, "cantidad": "8"}])

    ajustes = list(AjusteStock.objects.order_by("pk"))
    detalles = list(AjusteStockDetalle.objects.order_by("pk"))
    movimientos = list(ItemMovimiento.objects.order_by("pk"))
    assert [ajuste.pk for ajuste in ajustes] == [1, 2]
    assert [detalle.pk for detalle in detalles] == [1, 2]
    assert [movimiento.pk for movimiento in movimientos] == [1, 2, 3]


@pytest.mark.django_db
def test_listado_filtra_por_fecha(ingresada):
    item = _producto("Producto")
    _movimiento(item, "10", pk=1)
    ayer = timezone.localdate() - timedelta(days=1)
    _crear(ingresada, [{"item": item, "cantidad": "9"}], fecha=ayer.isoformat())
    _crear(ingresada, [{"item": item, "cantidad": "8"}], fecha=timezone.localdate().isoformat())

    response = ingresada.get(f"/inventario/ajustes/?fecha_desde={timezone.localdate().isoformat()}")

    content = response.content.decode()
    cuerpo = content.split("<tbody>")[1].split("</tbody>")[0]
    assert cuerpo.count("<tr") == 1


@pytest.mark.django_db
def test_exportaciones(ingresada):
    item = _producto("Producto")
    _movimiento(item, "10", pk=1)
    _crear(ingresada, [{"item": item, "cantidad": "8"}])

    imprimir = ingresada.get("/inventario/ajustes/imprimir/")
    assert imprimir.status_code == 200
    assert "Ajustes de stock" in imprimir.content.decode()

    excel = ingresada.get("/inventario/ajustes/exportar.xlsx")
    assert excel.status_code == 200
    libro = load_workbook(BytesIO(excel.content))
    assert libro.active.cell(1, 1).value == "N.º"

    pdf = ingresada.get("/inventario/ajustes/exportar.pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")

from django.utils.safestring import SafeString

from core.enlaces import (
    html_enlace_origen,
    url_origen_caja,
    url_origen_movimiento,
    url_ver_registro,
)
from inventario.models import TipoMovimiento


def test_url_ver_registro_abre_panel():
    assert url_ver_registro("venta_list", "venta", 7) == "/ventas/?venta=7&ver=1"
    assert url_ver_registro("compra_list", "compra", None) == ""


def test_html_enlace_abre_en_otra_pestana():
    html = html_enlace_origen("001-001-1", "/ventas/?venta=1&ver=1")
    assert isinstance(html, SafeString)
    assert 'class="sheet-origen"' in html
    assert 'target="_blank"' in html
    assert html_enlace_origen("Saldo anterior", "") == "Saldo anterior"


def test_url_origen_caja_segun_etiqueta():
    assert url_origen_caja("Venta", 3) == "/ventas/?venta=3&ver=1"
    assert url_origen_caja("Egreso", 9) == "/compras/?compra=9&ver=1"
    assert url_origen_caja("Transferencia", 4) == (
        "/cuentas/transferencias/?transferencia=4&ver=1"
    )
    assert url_origen_caja("", 1) == ""


def test_url_origen_movimiento_por_secuencia():
    assert url_origen_movimiento(TipoMovimiento.COMPRA, "C15") == "/compras/?compra=15&ver=1"
    assert (
        url_origen_movimiento(TipoMovimiento.AJUSTE_NEGATIVO, "A8")
        == "/inventario/ajustes/?ajuste=8&ver=1"
    )
    assert url_origen_movimiento(TipoMovimiento.VENTA, "001-001-1", venta_id=21) == (
        "/ventas/?venta=21&ver=1"
    )
    assert url_origen_movimiento(TipoMovimiento.COMPRA, "") == ""

from urllib.parse import urlencode

from django.urls import reverse
from django.utils.html import format_html

from inventario.models import TipoMovimiento

PREFIJO_COMPRA = "C"
PREFIJO_AJUSTE = "A"


def url_ver_registro(url_name, selection_param, pk):
    if not pk:
        return ""
    destino = reverse(url_name)
    return f"{destino}?{urlencode({selection_param: pk, 'ver': 1})}"


def html_enlace_origen(texto, url):
    if not url:
        return texto
    return format_html(
        '<a class="sheet-origen" href="{}" target="_blank" rel="noopener">{}</a>',
        url,
        texto,
    )


def url_origen_caja(origen, origen_id):
    if origen == "Venta":
        return url_ver_registro("venta_list", "venta", origen_id)
    if origen in ("Compra", "Egreso"):
        return url_ver_registro("compra_list", "compra", origen_id)
    if origen == "Transferencia":
        return url_ver_registro("transferencia_list", "transferencia", origen_id)
    return ""


def url_origen_movimiento(tipo, secuencia_origen, *, venta_id=None):
    if not secuencia_origen:
        return ""
    if tipo == TipoMovimiento.COMPRA:
        return url_ver_registro(
            "compra_list",
            "compra",
            _pk_con_prefijo(secuencia_origen, PREFIJO_COMPRA),
        )
    if tipo in (TipoMovimiento.AJUSTE_POSITIVO, TipoMovimiento.AJUSTE_NEGATIVO):
        return url_ver_registro(
            "ajuste_stock_list",
            "ajuste",
            _pk_con_prefijo(secuencia_origen, PREFIJO_AJUSTE),
        )
    if tipo == TipoMovimiento.VENTA:
        if venta_id is None:
            from ventas.models import Venta

            venta_id = (
                Venta.objects.filter(numero_completo=secuencia_origen)
                .values_list("pk", flat=True)
                .first()
            )
        return url_ver_registro("venta_list", "venta", venta_id)
    return ""


def _pk_con_prefijo(secuencia, prefijo):
    if not str(secuencia).startswith(prefijo):
        return None
    resto = str(secuencia)[len(prefijo) :]
    return int(resto) if resto.isdigit() else None

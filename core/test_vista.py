from compras.models import Compra, EstadoCompra
from core.vista import format_value, record_anulado
from personas.models import Persona
from ventas.models import EstadoVenta, Venta


def test_booleano_muestra_check():
    persona = Persona(activo=True)
    html = str(format_value(persona, Persona._meta.get_field("activo")))
    assert "rupia-check is-on" in html
    assert "Sí" in html

    persona.activo = False
    html = str(format_value(persona, Persona._meta.get_field("activo")))
    assert "rupia-check is-off" in html
    assert "No" in html


def test_situacion_vigente_y_anulada():
    compra = Compra(estado=EstadoCompra.CONFIRMADA)
    html = str(format_value(compra, Compra._meta.get_field("estado")))
    assert "rupia-badge is-vigente" in html
    assert "Confirmada" in html
    assert not record_anulado(compra)

    compra.estado = EstadoCompra.ANULADA
    html = str(format_value(compra, Compra._meta.get_field("estado")))
    assert "rupia-badge is-anulado" in html
    assert "Anulada" in html
    assert record_anulado(compra)

    venta = Venta(estado=EstadoVenta.COBRADA)
    html = str(format_value(venta, Venta._meta.get_field("estado")))
    assert "rupia-badge is-vigente" in html
    assert "Cobrada" in html

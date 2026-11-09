from django.test import RequestFactory
from django.utils import timezone

from core.listado import filter_values


def test_fechas_por_defecto_comienzan_el_mes_y_terminan_hoy():
    request = RequestFactory().get("/")
    hoy = timezone.localdate()
    valores = filter_values(
        request,
        (
            {"name": "fecha_desde", "kind": "date", "default": "month_start"},
            {"name": "fecha_hasta", "kind": "date", "default": "today"},
            {"name": "cuenta", "kind": "fk"},
        ),
    )
    assert valores["fecha_desde"] == hoy.replace(day=1).isoformat()
    assert valores["fecha_hasta"] == hoy.isoformat()
    assert "cuenta" not in valores


def test_fechas_explicitas_pisan_el_defecto():
    request = RequestFactory().get("/?fecha_desde=2026-01-01&fecha_hasta=2026-01-31")
    valores = filter_values(
        request,
        (
            {"name": "fecha_desde", "kind": "date", "default": "month_start"},
            {"name": "fecha_hasta", "kind": "date", "default": "today"},
        ),
    )
    assert valores["fecha_desde"] == "2026-01-01"
    assert valores["fecha_hasta"] == "2026-01-31"

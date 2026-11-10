from django.test import RequestFactory
from django.utils import timezone

from core.listado import apply_filters, filter_values


class _Lookup:
    def __init__(self, validos):
        self.validos = {str(valor) for valor in validos}

    def filter(self, **kwargs):
        pk = str(kwargs.get("pk", ""))
        parent = self

        class _Result:
            def exists(self):
                return pk in parent.validos

        return _Result()


class _Query:
    def __init__(self):
        self.calls = []

    def filter(self, **kwargs):
        self.calls.append(kwargs)
        return self


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


def test_filtro_fk_invalido_no_aplica():
    queryset = _Query()
    resultado = apply_filters(
        queryset,
        {"cuenta": "999"},
        ({"name": "cuenta", "kind": "fk", "queryset": _Lookup({"1"})},),
    )
    assert resultado is queryset
    assert queryset.calls == []


def test_filtro_fk_valido_aplica():
    queryset = _Query()
    apply_filters(
        queryset,
        {"cuenta": "1"},
        ({"name": "cuenta", "kind": "fk", "queryset": _Lookup({"1"})},),
    )
    assert queryset.calls == [{"cuenta": "1"}]

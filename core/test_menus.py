import pytest


@pytest.mark.django_db
def test_gestion_agrupa_timbrados_cuentas_y_unidades_de_negocio(ingresada):
    menu = ingresada.get("/").context["menu"]
    etiquetas = [entrada["label"] for entrada in menu]

    assert "Gestión" in etiquetas
    assert "Caja" not in etiquetas

    gestion = next(entrada for entrada in menu if entrada["label"] == "Gestión")
    assert [hijo["label"] for hijo in gestion["children"]] == [
        "Timbrados",
        "Cuentas",
        "Transferencias",
        "Disponibilidad",
        "Informe de gastos",
        "Informe de ventas",
        "Cuentas a pagar",
        "Pagos a proveedor",
        "Unidades de negocio",
    ]

    inventario = next(entrada for entrada in menu if entrada["label"] == "Inventario")
    assert "Unidades de negocio" not in [hijo["label"] for hijo in inventario["children"]]

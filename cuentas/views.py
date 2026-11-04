from core.mantenimiento import (
    MantenimientoCreateView,
    MantenimientoDeleteView,
    MantenimientoListView,
    MantenimientoUpdateView,
)
from cuentas.forms import CuentaForm
from cuentas.models import Cuenta
from cuentas.tables import CuentaTable


class CuentaMantenimiento:
    model = Cuenta
    form_class = CuentaForm
    table_class = CuentaTable
    permiso_formulario = "cuentas"
    page_title = "Cuentas"
    eyebrow = "Caja"
    title = "Cuentas"
    create_label = "Nueva cuenta"
    list_hint = "Flechas para moverse. Enter abre la cuenta."
    search_label = "Buscar"
    search_placeholder = "Buscar por descripción, nombre corto o número..."
    search_field = "descripcion"
    search_fields = ("descripcion", "nombre_corto", "numero")
    filters = (
        {"name": "es_banco", "label": "Banco", "kind": "bool"},
        {"name": "es_tarjeta", "label": "Tarjeta", "kind": "bool"},
    )
    selection_param = "cuenta"
    record_noun = "cuenta"
    order_by = ("descripcion", "pk")
    list_url_name = "cuenta_list"
    create_url_name = "cuenta_create"
    update_url_name = "cuenta_update"
    delete_url_name = "cuenta_delete"
    print_url_name = "cuenta_print"
    export_xlsx_url_name = "cuenta_export_xlsx"
    export_pdf_url_name = "cuenta_export_pdf"
    export_basename = "cuentas"


class CuentaListView(CuentaMantenimiento, MantenimientoListView):
    pass


class CuentaCreateView(CuentaMantenimiento, MantenimientoCreateView):
    list_view_class = CuentaListView


class CuentaUpdateView(CuentaMantenimiento, MantenimientoUpdateView):
    list_view_class = CuentaListView


class CuentaDeleteView(CuentaMantenimiento, MantenimientoDeleteView):
    pass

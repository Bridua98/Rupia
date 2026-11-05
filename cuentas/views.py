from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from configuracion.permisos import PermisoRequeridoMixin
from core.mantenimiento import (
    MantenimientoCreateView,
    MantenimientoDeleteView,
    MantenimientoListView,
    MantenimientoUpdateView,
)
from cuentas.forms import CuentaForm, TransferenciaForm
from cuentas.models import Cuenta, EstadoTransferencia, Transferencia
from cuentas.tables import CuentaTable, TransferenciaTable
from cuentas.transferencia import anular as anular_transferencia


class CuentaMantenimiento:
    model = Cuenta
    form_class = CuentaForm
    table_class = CuentaTable
    permiso_formulario = "cuentas"
    page_title = "Cuentas"
    eyebrow = "Gestión"
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


def _error(exc: ValidationError) -> str:
    if hasattr(exc, "message") and exc.message:
        return str(exc.message)
    if exc.messages:
        return str(exc.messages[0])
    return "No se pudo completar la transferencia."


class TransferenciaListado:
    model = Transferencia
    form_class = TransferenciaForm
    table_class = TransferenciaTable
    permiso_formulario = "transferencias"
    page_title = "Transferencias"
    eyebrow = "Gestión"
    title = "Transferencias"
    create_label = "Nueva transferencia"
    list_hint = "Flechas para moverse. Enter abre la transferencia."
    search_label = "Buscar"
    search_placeholder = "Buscar por comprobante o cuenta..."
    search_field = "comprobante"
    search_fields = (
        "comprobante",
        "cuenta_origen__descripcion",
        "cuenta_destino__descripcion",
        "cuenta_origen__nombre_corto",
        "cuenta_destino__nombre_corto",
    )
    filters = (
        {
            "name": "estado",
            "label": "Estado",
            "kind": "choice",
            "choices": EstadoTransferencia.choices,
        },
        {
            "name": "fecha_desde",
            "label": "Desde",
            "kind": "date",
            "field": "fecha",
            "lookup": "gte",
        },
        {
            "name": "fecha_hasta",
            "label": "Hasta",
            "kind": "date",
            "field": "fecha",
            "lookup": "lte",
        },
    )
    selection_param = "transferencia"
    record_noun = "transferencia"
    order_by = ("-fecha", "-pk")
    list_url_name = "transferencia_list"
    create_url_name = "transferencia_create"
    print_url_name = "transferencia_print"
    export_xlsx_url_name = "transferencia_export_xlsx"
    export_pdf_url_name = "transferencia_export_pdf"
    export_basename = "transferencias"
    view_exclude = ("anulado_en", "anulado_por")


class TransferenciaListView(TransferenciaListado, MantenimientoListView):
    def get_queryset(self):
        return super().get_queryset().select_related("cuenta_origen", "cuenta_destino")

    def get_table(self, **kwargs):
        table = super().get_table(**kwargs)
        table.puede_anular = self.puede("anular")
        return table


class TransferenciaCreateView(TransferenciaListado, MantenimientoCreateView):
    list_view_class = TransferenciaListView

    def form_valid(self, form):
        form.instance.usuario = self.request.user
        return super().form_valid(form)


class AnularTransferenciaView(LoginRequiredMixin, PermisoRequeridoMixin, View):
    permiso_formulario = "transferencias"
    permiso_accion = "anular"

    def post(self, request, pk):
        transferencia = get_object_or_404(Transferencia, pk=pk)
        try:
            anular_transferencia(transferencia, usuario=request.user)
            messages.success(request, f"Se anuló {transferencia}.")
        except ValidationError as exc:
            messages.error(request, _error(exc))
        return redirect("transferencia_list")

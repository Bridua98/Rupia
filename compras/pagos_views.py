from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from compras.cuotas import cuotas_abiertas_proveedor
from compras.pago_proveedor import anular, confirmar_pago_desde_post
from compras.models import EstadoPagoProveedor, PagoProveedor
from compras.tables import PagoProveedorTable
from configuracion.permisos import PermisoRequeridoMixin
from core.mantenimiento import MantenimientoListView
from core.moneda import formatear_guaranies
from cuentas.models import Cuenta
from personas.models import Persona


def _error(exc: ValidationError) -> str:
    if hasattr(exc, "message") and exc.message:
        return str(exc.message)
    if exc.messages:
        return str(exc.messages[0])
    return "No se pudo completar el pago."


class PagoProveedorListado:
    model = PagoProveedor
    table_class = PagoProveedorTable
    permiso_formulario = "pagos_proveedor"
    page_title = "Pagos a proveedor"
    eyebrow = "Compras"
    title = "Pagos a proveedor"
    create_label = "Nuevo pago"
    list_hint = "Pagos que cancelan cuotas de facturas a crédito."
    search_label = "Buscar"
    search_placeholder = "Buscar por proveedor, cuenta u observación..."
    search_fields = (
        "proveedor__razon_social",
        "proveedor__documento",
        "cuenta__descripcion",
        "observacion",
    )
    filters = (
        {
            "name": "estado",
            "label": "Estado",
            "kind": "choice",
            "choices": EstadoPagoProveedor.choices,
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
        {
            "name": "proveedor",
            "label": "Proveedor",
            "kind": "fk",
            "queryset": lambda: Persona.objects.filter(es_proveedor=True).order_by("razon_social"),
        },
        {
            "name": "cuenta",
            "label": "Cuenta",
            "kind": "fk",
            "queryset": lambda: Cuenta.objects.order_by("descripcion"),
        },
    )
    record_noun = "pago"
    selection_param = "pago"
    order_by = ("-fecha", "-pk")
    list_url_name = "pago_proveedor_list"
    create_url_name = "pago_proveedor_nuevo"
    print_url_name = "pago_proveedor_print"
    export_xlsx_url_name = "pago_proveedor_export_xlsx"
    export_pdf_url_name = "pago_proveedor_export_pdf"
    export_basename = "pagos-proveedor"
    view_exclude = ("anulado_en", "anulado_por")


class PagoProveedorListView(PagoProveedorListado, MantenimientoListView):
    def creating(self):
        return False

    def get_queryset(self):
        return super().get_queryset().select_related("proveedor", "cuenta")

    def get_table(self, **kwargs):
        table = super().get_table(**kwargs)
        table.puede_anular = self.puede("anular")
        return table

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.puede("alta"):
            context["create_url"] = reverse("pago_proveedor_nuevo")
        return context


class PagoProveedorNuevoView(LoginRequiredMixin, PermisoRequeridoMixin, View):
    permiso_formulario = "pagos_proveedor"
    permiso_accion = "alta"

    def get(self, request):
        return render(request, "compras/pago_proveedor_form.html", self._contexto(request))

    def post(self, request):
        try:
            pago = confirmar_pago_desde_post(request.user, request.POST)
            messages.success(request, f"Se registró el pago {pago.pk}.")
            return redirect("pago_proveedor_list")
        except ValidationError as exc:
            messages.error(request, _error(exc))
            return render(
                request,
                "compras/pago_proveedor_form.html",
                self._contexto(request, post=request.POST),
            )
        except (Persona.DoesNotExist, Cuenta.DoesNotExist):
            messages.error(request, "Elegí un proveedor y una cuenta válidos.")
            return redirect("pago_proveedor_nuevo")

    def _contexto(self, request, post=None):
        proveedor_id = (post or request.GET).get("proveedor") or ""
        try:
            proveedor_id = int(proveedor_id) if proveedor_id else None
        except (TypeError, ValueError):
            proveedor_id = None
        cuotas = []
        if proveedor_id:
            for cuota, saldo in cuotas_abiertas_proveedor(proveedor_id):
                aplicado = ""
                if post:
                    aplicado = post.get(f"aplicar_{cuota.pk}", "")
                cuotas.append(
                    {
                        "pk": cuota.pk,
                        "compra": cuota.compra.numero_completo or str(cuota.compra),
                        "numero": cuota.numero,
                        "vencimiento": cuota.vencimiento.strftime("%Y-%m-%d"),
                        "vencimiento_txt": cuota.vencimiento.strftime("%d/%m/%Y"),
                        "importe_txt": formatear_guaranies(cuota.importe),
                        "saldo": saldo,
                        "saldo_txt": formatear_guaranies(saldo),
                        "aplicar": aplicado,
                    }
                )
        fecha = (post or {}).get("fecha") or timezone.localdate().isoformat()
        return {
            "fecha": fecha,
            "proveedor_id": proveedor_id or "",
            "cuenta_id": (post or {}).get("cuenta", ""),
            "observacion": (post or {}).get("observacion", ""),
            "cuentas": Cuenta.objects.order_by("descripcion"),
            "proveedores": Persona.objects.filter(es_proveedor=True).order_by("razon_social"),
            "cuotas": cuotas,
        }


class AnularPagoProveedorView(LoginRequiredMixin, PermisoRequeridoMixin, View):
    permiso_formulario = "pagos_proveedor"
    permiso_accion = "anular"

    def post(self, request, pk):
        pago = get_object_or_404(PagoProveedor, pk=pk)
        try:
            anular(pago, usuario=request.user)
            messages.success(request, f"Se anuló el pago {pago.pk}.")
        except ValidationError as exc:
            messages.error(request, _error(exc))
        return redirect("pago_proveedor_list")

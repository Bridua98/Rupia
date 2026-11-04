from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View

from configuracion.permisos import PermisoRequeridoMixin
from core.mantenimiento import (
    MantenimientoCreateView,
    MantenimientoDeleteView,
    MantenimientoListView,
    MantenimientoUpdateView,
)
from personas.consulta import buscar, consultar_ruc
from personas.forms import PersonaForm
from personas.models import Genero, Persona, TipoDocumento
from personas.tables import PersonaTable


class PersonaMantenimiento:
    model = Persona
    form_class = PersonaForm
    table_class = PersonaTable
    permiso_formulario = "personas"

    page_title = "Personas"
    eyebrow = "Personas"
    title = "Personas"
    create_label = "Nueva persona"
    list_hint = "Flechas para moverse. Enter abre la persona."

    search_label = "Buscar"
    search_placeholder = "Buscar por razón social, documento o celular..."
    search_field = "razon_social"
    search_fields = ("razon_social", "documento", "celular")

    filters = (
        {
            "name": "tipo_documento",
            "label": "Tipo de documento",
            "kind": "choice",
            "choices": TipoDocumento.choices,
        },
        {
            "name": "genero",
            "label": "Género",
            "kind": "choice",
            "choices": Genero.choices,
        },
        {"name": "es_cliente", "label": "Cliente", "kind": "bool"},
        {"name": "es_proveedor", "label": "Proveedor", "kind": "bool"},
        {"name": "es_empleado", "label": "Personal", "kind": "bool"},
        {"name": "activo", "label": "Activo", "kind": "bool"},
    )

    selection_param = "persona"
    record_noun = "persona"
    order_by = ("razon_social", "pk")

    list_url_name = "persona_list"
    create_url_name = "persona_create"
    update_url_name = "persona_update"
    delete_url_name = "persona_delete"
    print_url_name = "persona_print"
    export_xlsx_url_name = "persona_export_xlsx"
    export_pdf_url_name = "persona_export_pdf"
    export_basename = "personas"


class PersonaListView(PersonaMantenimiento, MantenimientoListView):
    def _panel_form(self, nueva, selected):
        form = super()._panel_form(nueva, selected)
        if not nueva or form is None or form.is_bound:
            return form
        if self.request.GET.get("proveedor") == "1":
            form.initial["es_proveedor"] = True
            form.fields["es_proveedor"].initial = True
        if self.request.GET.get("cliente") == "1":
            form.initial["es_cliente"] = True
            form.fields["es_cliente"].initial = True
        documento = (self.request.GET.get("documento") or "").strip()
        if documento:
            form.initial["documento"] = documento
            form.fields["documento"].initial = documento
        razon = (self.request.GET.get("razon_social") or "").strip()
        if razon:
            form.initial["razon_social"] = razon
            form.fields["razon_social"].initial = razon
        return form


class PersonaCreateView(PersonaMantenimiento, MantenimientoCreateView):
    list_view_class = PersonaListView


class PersonaUpdateView(PersonaMantenimiento, MantenimientoUpdateView):
    list_view_class = PersonaListView


class PersonaDeleteView(PersonaMantenimiento, MantenimientoDeleteView):
    pass


class PersonaConsultaView(LoginRequiredMixin, PermisoRequeridoMixin, View):
    permiso_formulario = "personas"
    def get(self, request):
        ruc = request.GET.get("ruc", "").strip()
        if ruc:
            ficha = consultar_ruc(ruc)
            if ficha is None:
                return JsonResponse({}, status=404)
            return JsonResponse(ficha)
        return JsonResponse({"results": buscar(request.GET.get("q", ""))})

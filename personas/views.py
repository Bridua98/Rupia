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
    pass


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

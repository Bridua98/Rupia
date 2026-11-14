from django.contrib.auth import get_user_model
from django.db.models import Prefetch

from core.listado import apply_filters, apply_search, filter_specs_for, filter_values
from core.mantenimiento import MantenimientoListView
from core.vista import record_anulado
from mesas.historial import expresion_total, relato_cuenta
from mesas.models import Comanda, ComandaDetalle, EstadoComanda, Mesa
from mesas.tables import ServicioHistorialTable
from mesas.views import ModuloMesasMixin

ESTADOS_HISTORIAL = (
    (EstadoComanda.CERRADA, "Cerrada"),
    (EstadoComanda.ANULADA, "Anulada"),
)


class HistorialServiciosView(ModuloMesasMixin, MantenimientoListView):
    model = Comanda
    table_class = ServicioHistorialTable
    permiso_formulario = "comandas"
    page_title = "Historial de servicios"
    eyebrow = "Mesas"
    title = "Historial"
    show_create = False
    create_label = ""
    list_hint = "Cuentas cerradas y anuladas. Enter abre el servicio."
    search_label = "Buscar"
    search_placeholder = "Buscar por mesa, pedido, mozo o cliente..."
    search_fields = (
        "mesa__nombre",
        "nombre",
        "cliente__razon_social",
        "mozo__username",
        "mozo__first_name",
    )
    selection_param = "servicio"
    record_noun = "servicio"
    order_by = ("-abierta_en", "-pk")
    list_url_name = "servicio_historial"
    filters = (
        {
            "name": "fecha_desde",
            "label": "Desde",
            "kind": "date",
            "field": "abierta_en",
            "lookup": "date__gte",
        },
        {
            "name": "fecha_hasta",
            "label": "Hasta",
            "kind": "date",
            "field": "abierta_en",
            "lookup": "date__lte",
        },
        {
            "name": "mesa",
            "label": "Mesa",
            "kind": "fk",
            "queryset": lambda: Mesa.objects.order_by("nombre"),
        },
        {
            "name": "mozo",
            "label": "Mozo",
            "kind": "fk",
            "queryset": lambda: get_user_model().objects.order_by("username"),
        },
        {
            "name": "estado",
            "label": "Estado",
            "kind": "choice",
            "choices": ESTADOS_HISTORIAL,
        },
    )

    def get_queryset(self):
        queryset = (
            Comanda.objects.filter(estado__in=(EstadoComanda.CERRADA, EstadoComanda.ANULADA))
            .select_related("mesa", "cliente", "mozo")
            .annotate(total_consumo=expresion_total())
            .prefetch_related(
                Prefetch(
                    "detalles",
                    queryset=ComandaDetalle.objects.filter(
                        venta_detalle__isnull=False
                    ).select_related("venta_detalle__venta"),
                    to_attr="lineas_cobradas",
                )
            )
            .order_by(*self.order_by)
        )
        queryset = apply_search(queryset, self.query(), self.search_fields)
        specs = filter_specs_for(self)
        return apply_filters(queryset, filter_values(self.request, specs), specs)

    def build_panel_view_context(self, record):
        return {
            "view_record": record,
            "view_fields": [],
            "view_tables": [],
            "view_anulado": record_anulado(record),
            "view_extra_template": "mesas/servicio_relato.html",
            "servicio": relato_cuenta(record),
        }

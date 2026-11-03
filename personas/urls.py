from django.urls import path

from core.mantenimiento import mantenimiento_salida
from personas.views import (
    PersonaConsultaView,
    PersonaCreateView,
    PersonaDeleteView,
    PersonaListView,
    PersonaUpdateView,
)

urlpatterns = [
    path("", PersonaListView.as_view(), name="persona_list"),
    path(
        "imprimir/",
        mantenimiento_salida(PersonaListView, "print").as_view(),
        name="persona_print",
    ),
    path(
        "exportar.xlsx",
        mantenimiento_salida(PersonaListView, "xlsx").as_view(),
        name="persona_export_xlsx",
    ),
    path(
        "exportar.pdf",
        mantenimiento_salida(PersonaListView, "pdf").as_view(),
        name="persona_export_pdf",
    ),
    path("nueva/", PersonaCreateView.as_view(), name="persona_create"),
    path("consulta/", PersonaConsultaView.as_view(), name="persona_consulta"),
    path("<int:pk>/", PersonaUpdateView.as_view(), name="persona_update"),
    path("<int:pk>/eliminar/", PersonaDeleteView.as_view(), name="persona_delete"),
]

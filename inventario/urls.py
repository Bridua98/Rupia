from django.urls import path

from inventario.views import MarcaCreateView, MarcaDeleteView, MarcaListView, MarcaUpdateView

urlpatterns = [
    path("marcas/", MarcaListView.as_view(), name="marca_list"),
    path("marcas/nueva/", MarcaCreateView.as_view(), name="marca_create"),
    path("marcas/<int:pk>/", MarcaUpdateView.as_view(), name="marca_update"),
    path("marcas/<int:pk>/eliminar/", MarcaDeleteView.as_view(), name="marca_delete"),
]

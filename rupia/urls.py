from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from rupia.api import api

admin.site.site_header = "Rupia"
admin.site.site_title = "Rupia"
admin.site.index_title = "Administración"

urlpatterns = [
    path(
        "admin/login/",
        RedirectView.as_view(pattern_name="login", query_string=True),
    ),
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    path("", include("core.urls")),
]

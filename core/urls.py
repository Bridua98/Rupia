from django.contrib.auth import views as auth_views
from django.urls import path

from core.forms import LoginForm
from core.selectors import SelectorCreateView, SelectorSearchView
from core.views import RupiaLoginView, home

urlpatterns = [
    path("", home, name="home"),
    path(
        "login/",
        RupiaLoginView.as_view(
            authentication_form=LoginForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("selector/<slug:clave>/", SelectorSearchView.as_view(), name="selector_search"),
    path("selector/<slug:clave>/nueva/", SelectorCreateView.as_view(), name="selector_create"),
]

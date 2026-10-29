from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import render, resolve_url

from core.menus import main_menu


def _is_admin_path(url):
    path = url.split("?", 1)[0]
    return path == "/admin" or path.startswith("/admin/")


class RupiaLoginView(LoginView):
    def get_success_url(self):
        redirect_to = super().get_success_url()
        user = self.request.user
        if _is_admin_path(redirect_to) and user.is_authenticated and not user.is_staff:
            return resolve_url(settings.LOGIN_REDIRECT_URL)
        return redirect_to


@login_required
def home(request):
    return render(request, "core/home.html", {"menu": main_menu(request)})

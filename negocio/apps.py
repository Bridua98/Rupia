from django.apps import AppConfig


class NegocioConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "negocio"
    verbose_name = "Negocio"

    def ready(self):
        from negocio import forms  # noqa: F401

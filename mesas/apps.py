from django.apps import AppConfig


class MesasConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "mesas"
    verbose_name = "Mesas"

    def ready(self):
        from mesas import forms  # noqa: F401

from django.apps import AppConfig


class MesasConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "mesas"
    verbose_name = "Mesas"

    def ready(self):
        from mesas import forms  # noqa: F401
        from mesas.cobro import al_confirmar_venta
        from ventas.signals import venta_confirmada

        venta_confirmada.connect(al_confirmar_venta, dispatch_uid="mesas_cerrar_cobradas")

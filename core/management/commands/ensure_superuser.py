import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

DEFAULT_USERNAME = "admin"
DEFAULT_EMAIL = "admin@rupia.local"
DEFAULT_DEV_PASSWORD = "Clave-inicial-Rupia-2026"


class Command(BaseCommand):
    help = "Crea el superusuario inicial si todavía no existe."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", DEFAULT_USERNAME).strip()
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", DEFAULT_EMAIL).strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "").strip()
        used_dev_password = False

        if not username:
            raise CommandError("DJANGO_SUPERUSER_USERNAME no puede estar vacío.")

        if not password:
            if settings.DEBUG:
                password = DEFAULT_DEV_PASSWORD
                used_dev_password = True
            else:
                raise CommandError("Definí DJANGO_SUPERUSER_PASSWORD para crear el superusuario.")

        user_model = get_user_model()
        existing = user_model.objects.filter(username=username).first()
        if existing is not None:
            if not existing.is_superuser:
                raise CommandError(f"El usuario {username} ya existe y no es superusuario.")
            self.stdout.write(self.style.WARNING(f"El usuario {username} ya existe."))
            return

        candidate = user_model(username=username, email=email)
        try:
            validate_password(password, candidate)
            user_model.objects.create_superuser(
                username=username,
                email=email,
                password=password,
            )
        except ValidationError as exc:
            detail = "; ".join(exc.messages)
            raise CommandError(f"No se pudo crear el superusuario: {detail}") from exc

        self.stdout.write(self.style.SUCCESS(f"Superusuario {username} creado."))
        if used_dev_password:
            self.stdout.write("Se usó la contraseña de desarrollo documentada en el README.")

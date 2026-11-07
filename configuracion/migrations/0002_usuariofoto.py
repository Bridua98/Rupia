from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("configuracion", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="UsuarioFoto",
            fields=[
                (
                    "id",
                    models.AutoField(
                        db_column="usufoto_id", primary_key=True, serialize=False
                    ),
                ),
                (
                    "imagen",
                    models.CharField(
                        blank=True,
                        db_column="usufoto_imagen",
                        default="",
                        max_length=200,
                        verbose_name="imagen",
                    ),
                ),
                (
                    "usuario",
                    models.OneToOneField(
                        db_column="usufoto_usuario_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="foto",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="usuario",
                    ),
                ),
            ],
            options={
                "verbose_name": "foto de usuario",
                "verbose_name_plural": "fotos de usuario",
                "db_table": "usuario_fotos",
            },
        ),
    ]

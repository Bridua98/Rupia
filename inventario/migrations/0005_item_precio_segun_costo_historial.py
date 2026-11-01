import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("inventario", "0004_item_tasa_iva"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="precio_segun_costo",
            field=models.BooleanField(
                db_column="item_precio_segun_costo",
                default=False,
                verbose_name="precio según último costo",
            ),
        ),
        migrations.CreateModel(
            name="ItemPrecioHistorial",
            fields=[
                (
                    "id",
                    models.AutoField(
                        db_column="itprehist_id",
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "precio_anterior",
                    models.DecimalField(
                        blank=True,
                        db_column="itprehist_precio_anterior",
                        decimal_places=3,
                        max_digits=15,
                        null=True,
                        verbose_name="precio anterior",
                    ),
                ),
                (
                    "precio_nuevo",
                    models.DecimalField(
                        blank=True,
                        db_column="itprehist_precio_nuevo",
                        decimal_places=3,
                        max_digits=15,
                        null=True,
                        verbose_name="precio nuevo",
                    ),
                ),
                (
                    "ultimo_costo",
                    models.DecimalField(
                        blank=True,
                        db_column="itprehist_ultimo_costo",
                        decimal_places=3,
                        max_digits=15,
                        null=True,
                        verbose_name="último costo",
                    ),
                ),
                (
                    "porcentaje",
                    models.DecimalField(
                        blank=True,
                        db_column="itprehist_porcentaje",
                        decimal_places=2,
                        max_digits=6,
                        null=True,
                        verbose_name="porcentaje",
                    ),
                ),
                (
                    "segun_costo",
                    models.BooleanField(
                        db_column="itprehist_segun_costo",
                        verbose_name="según costo",
                    ),
                ),
                (
                    "origen",
                    models.CharField(
                        choices=[("FICHA", "Ficha"), ("MASIVO", "Masivo")],
                        db_column="itprehist_origen",
                        max_length=6,
                        verbose_name="origen",
                    ),
                ),
                (
                    "fecha",
                    models.DateTimeField(
                        db_column="itprehist_fecha",
                        verbose_name="fecha",
                    ),
                ),
                (
                    "lote",
                    models.CharField(
                        blank=True,
                        db_column="itprehist_lote",
                        max_length=32,
                        null=True,
                        verbose_name="lote",
                    ),
                ),
                (
                    "item",
                    models.ForeignKey(
                        db_column="itprehist_item_id",
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="precios_historial",
                        to="inventario.item",
                        verbose_name="ítem",
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        db_column="itprehist_usuario_id",
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="precios_historial",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="usuario",
                    ),
                ),
            ],
            options={
                "verbose_name": "historial de precio",
                "verbose_name_plural": "historial de precios",
                "db_table": "items_precios_historial",
                "ordering": ["-fecha", "-id"],
            },
        ),
    ]

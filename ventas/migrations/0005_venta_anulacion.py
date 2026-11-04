import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ventas", "0004_ventas_timbrado_numero_completo"),
    ]

    operations = [
        migrations.AlterField(
            model_name="venta",
            name="estado",
            field=models.CharField(
                choices=[
                    ("EN_CURSO", "En curso"),
                    ("COBRADA", "Cobrada"),
                    ("ANULADA", "Anulada"),
                ],
                db_column="vent_estado",
                default="EN_CURSO",
                max_length=8,
                verbose_name="estado",
            ),
        ),
        migrations.AddField(
            model_name="venta",
            name="tipo_anulacion",
            field=models.CharField(
                blank=True,
                choices=[
                    ("FISICA", "Anulación física"),
                    ("REUTILIZABLE", "Número reutilizable"),
                ],
                db_column="vent_tipo_anulacion",
                max_length=12,
                verbose_name="tipo de anulación",
            ),
        ),
        migrations.AddField(
            model_name="venta",
            name="anulado_en",
            field=models.DateTimeField(
                blank=True,
                db_column="vent_anulado_en",
                null=True,
                verbose_name="anulado en",
            ),
        ),
        migrations.AddField(
            model_name="venta",
            name="anulado_por",
            field=models.ForeignKey(
                blank=True,
                db_column="vent_anulado_por_id",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ventas_anuladas",
                to=settings.AUTH_USER_MODEL,
                verbose_name="anulado por",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="venta",
            name="ventas_timbrado_numero_completo",
        ),
        migrations.AddConstraint(
            model_name="venta",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    models.Q(
                        ("estado", "COBRADA"),
                        models.Q(("estado", "ANULADA"), ("tipo_anulacion", "FISICA")),
                        _connector="OR",
                    ),
                    ("numero_completo__isnull", False),
                    models.Q(("timbrado", ""), _negated=True),
                ),
                fields=("timbrado", "numero_completo"),
                name="ventas_timbrado_numero_completo",
            ),
        ),
    ]

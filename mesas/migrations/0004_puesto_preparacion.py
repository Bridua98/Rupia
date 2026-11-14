from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mesas", "0003_comanda_venta"),
    ]

    operations = [
        migrations.AddField(
            model_name="sector",
            name="exige_empezar",
            field=models.BooleanField(
                db_column="sect_exige_empezar", default=False, verbose_name="pide empezar"
            ),
        ),
        migrations.AddField(
            model_name="sector",
            name="minutos_demora",
            field=models.PositiveSmallIntegerField(
                db_column="sect_minutos_demora", default=15, verbose_name="minutos de demora"
            ),
        ),
        migrations.AddField(
            model_name="enviosector",
            name="empezado_en",
            field=models.DateTimeField(
                blank=True, db_column="envi_empezado_en", null=True, verbose_name="empezado"
            ),
        ),
        migrations.AlterField(
            model_name="enviosector",
            name="estado",
            field=models.CharField(
                choices=[
                    ("PENDIENTE", "Pendiente"),
                    ("IMPRESO", "Impreso"),
                    ("PREPARACION", "En preparación"),
                    ("LISTO", "Listo"),
                ],
                db_column="envi_estado",
                default="PENDIENTE",
                max_length=11,
                verbose_name="estado",
            ),
        ),
    ]

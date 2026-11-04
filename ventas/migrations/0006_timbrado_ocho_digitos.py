from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ventas", "0005_venta_anulacion"),
    ]

    operations = [
        migrations.AlterField(
            model_name="puntoexpedicion",
            name="timbrado",
            field=models.CharField(
                db_column="puntexpe_timbrado",
                max_length=8,
                verbose_name="timbrado",
            ),
        ),
        migrations.AlterField(
            model_name="venta",
            name="timbrado",
            field=models.CharField(
                blank=True,
                db_column="vent_timbrado",
                max_length=8,
                verbose_name="timbrado",
            ),
        ),
    ]

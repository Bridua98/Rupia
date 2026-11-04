from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ventas", "0002_puntoexpedicion_habilitado"),
    ]

    operations = [
        migrations.AddField(
            model_name="ventadetalle",
            name="descuento_porcentaje",
            field=models.DecimalField(
                db_column="ventdeta_descuento_porcentaje",
                decimal_places=2,
                default=0,
                max_digits=6,
                verbose_name="descuento %",
            ),
        ),
    ]

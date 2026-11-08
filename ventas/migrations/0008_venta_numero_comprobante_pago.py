from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ventas", "0007_venta_numero_por_tipo"),
    ]

    operations = [
        migrations.AddField(
            model_name="venta",
            name="numero_comprobante_pago",
            field=models.CharField(
                blank=True,
                db_column="vent_numero_comprobante_pago",
                max_length=80,
                verbose_name="comprobante de pago",
            ),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ventas", "0003_ventadetalle_descuento_porcentaje"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="venta",
            name="ventas_numero_completo",
        ),
        migrations.AddConstraint(
            model_name="venta",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("numero_completo__isnull", False), models.Q(("timbrado", ""), _negated=True)
                ),
                fields=("timbrado", "numero_completo"),
                name="ventas_timbrado_numero_completo",
            ),
        ),
    ]

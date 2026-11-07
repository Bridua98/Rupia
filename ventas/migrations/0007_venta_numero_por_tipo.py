from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ventas", "0006_timbrado_ocho_digitos"),
    ]

    operations = [
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
                fields=("tipo_comprobante", "timbrado", "numero_completo"),
                name="ventas_timbrado_numero_completo",
            ),
        ),
    ]

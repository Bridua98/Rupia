from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventario", "0003_descripciones_unicas"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="tasa_iva",
            field=models.PositiveSmallIntegerField(
                choices=[(10, "10%"), (5, "5%"), (0, "0%")],
                db_column="item_tasa_iva",
                default=10,
                verbose_name="tasa IVA",
            ),
        ),
    ]

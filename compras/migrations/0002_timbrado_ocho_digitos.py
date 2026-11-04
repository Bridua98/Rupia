from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("compras", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="compra",
            name="timbrado",
            field=models.CharField(
                blank=True,
                db_column="compr_timbrado",
                max_length=8,
                verbose_name="timbrado",
            ),
        ),
    ]

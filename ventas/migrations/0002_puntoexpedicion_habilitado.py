from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ventas", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="puntoexpedicion",
            name="habilitado",
            field=models.BooleanField(
                db_column="puntexpe_habilitado",
                default=True,
                verbose_name="habilitado",
            ),
        ),
    ]

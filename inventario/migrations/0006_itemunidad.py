import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventario", "0005_item_precio_segun_costo_historial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ItemUnidad",
            fields=[
                (
                    "id",
                    models.AutoField(
                        db_column="itemunid_id",
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "relacion",
                    models.CharField(
                        choices=[("MENOR", "Menor"), ("MAYOR", "Mayor")],
                        db_column="itemunid_relacion",
                        max_length=5,
                        verbose_name="relación",
                    ),
                ),
                (
                    "valor",
                    models.DecimalField(
                        db_column="itemunid_valor",
                        decimal_places=3,
                        max_digits=15,
                        verbose_name="valor",
                    ),
                ),
                (
                    "item",
                    models.ForeignKey(
                        db_column="itemunid_item_id",
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="unidades",
                        to="inventario.item",
                        verbose_name="ítem",
                    ),
                ),
                (
                    "unidad_medida",
                    models.ForeignKey(
                        db_column="itemunid_unidmedi_id",
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="items_relacionados",
                        to="inventario.unidadmedida",
                        verbose_name="unidad de medida",
                    ),
                ),
            ],
            options={
                "verbose_name": "unidad relacionada",
                "verbose_name_plural": "unidades relacionadas",
                "db_table": "items_unidades",
                "ordering": ["id"],
            },
        ),
        migrations.AddConstraint(
            model_name="itemunidad",
            constraint=models.UniqueConstraint(
                fields=("item", "unidad_medida"),
                name="items_unidades_item_unidad",
            ),
        ),
    ]

from django.db import models


class UnidadNegocio(models.Model):
    id = models.AutoField(primary_key=True, db_column="unidnego_id")
    descripcion = models.CharField(
        "descripción",
        max_length=200,
        unique=True,
        db_column="unidnego_descripcion",
    )
    abreviado = models.CharField(
        "abreviado",
        max_length=20,
        unique=True,
        db_column="unidnego_abreviado",
    )

    class Meta:
        db_table = "unidades_negocio"
        verbose_name = "unidad de negocio"
        verbose_name_plural = "unidades de negocio"
        ordering = ["descripcion"]

    def __str__(self):
        return f"{self.descripcion} ({self.abreviado})"

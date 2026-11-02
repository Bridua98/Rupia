from django.core.exceptions import ValidationError
from django.db import models


class Cuenta(models.Model):
    id = models.AutoField(primary_key=True, db_column="cuen_id")
    descripcion = models.CharField(
        "descripción",
        max_length=200,
        unique=True,
        db_column="cuen_descripcion",
    )
    nombre_corto = models.CharField(
        "nombre corto",
        max_length=20,
        unique=True,
        db_column="cuen_nombre_corto",
    )
    es_banco = models.BooleanField("banco", default=False, db_column="cuen_es_banco")
    es_tarjeta = models.BooleanField("tarjeta", default=False, db_column="cuen_es_tarjeta")
    numero = models.CharField(
        "número de cuenta",
        max_length=45,
        null=True,
        blank=True,
        db_column="cuen_numero",
    )

    class Meta:
        db_table = "cuentas"
        verbose_name = "cuenta"
        verbose_name_plural = "cuentas"
        ordering = ["descripcion"]

    def __str__(self):
        return self.descripcion

    def clean(self):
        super().clean()
        if not self.es_banco:
            self.es_tarjeta = False
            self.numero = None
            return
        if not (self.numero or "").strip():
            raise ValidationError({"numero": "Escribí el número de cuenta."})
        self.numero = self.numero.strip()

    def tipo_caja(self):
        if self.es_tarjeta:
            return "Tarjeta"
        if self.es_banco:
            return "Banco"
        return "Caja"

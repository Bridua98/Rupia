from django.conf import settings
from django.db import models


class Perfil(models.Model):
    id = models.AutoField(primary_key=True, db_column="perf_id")
    descripcion = models.CharField(
        "descripción",
        max_length=200,
        unique=True,
        db_column="perf_descripcion",
    )
    activo = models.BooleanField(
        "activo",
        default=True,
        db_column="perf_activo",
    )
    usuarios = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="perfiles",
        blank=True,
        db_table="perfil_usuarios",
        verbose_name="usuarios",
    )

    class Meta:
        db_table = "perfiles"
        verbose_name = "perfil"
        verbose_name_plural = "perfiles"
        ordering = ["descripcion"]

    def __str__(self):
        return self.descripcion


class PerfilPermiso(models.Model):
    id = models.AutoField(primary_key=True, db_column="perfperm_id")
    perfil = models.ForeignKey(
        Perfil,
        on_delete=models.CASCADE,
        related_name="permisos",
        db_column="perfperm_perfil_id",
        verbose_name="perfil",
    )
    formulario = models.CharField(
        "formulario",
        max_length=40,
        db_column="perfperm_formulario",
    )
    accion = models.CharField(
        "acción",
        max_length=20,
        db_column="perfperm_accion",
    )

    class Meta:
        db_table = "perfil_permisos"
        verbose_name = "permiso de perfil"
        verbose_name_plural = "permisos de perfil"
        constraints = [
            models.UniqueConstraint(
                fields=("perfil", "formulario", "accion"),
                name="perfil_permiso_unico",
            )
        ]

    def __str__(self):
        return f"{self.perfil}: {self.formulario}.{self.accion}"

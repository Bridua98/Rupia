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


class UsuarioFoto(models.Model):
    id = models.AutoField(primary_key=True, db_column="usufoto_id")
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="foto",
        db_column="usufoto_usuario_id",
        verbose_name="usuario",
    )
    imagen = models.CharField(
        "imagen",
        max_length=200,
        blank=True,
        default="",
        db_column="usufoto_imagen",
    )

    class Meta:
        db_table = "usuario_fotos"
        verbose_name = "foto de usuario"
        verbose_name_plural = "fotos de usuario"

    def __str__(self):
        return self.imagen or str(self.usuario)


class Ajustes(models.Model):
    """Ajustes generales del sistema: una sola fila (pk=1)."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, db_column="ajus_id")
    mesas_habilitadas = models.BooleanField(
        "mesas y comandas",
        default=False,
        db_column="ajus_mesas_habilitadas",
    )

    class Meta:
        db_table = "ajustes"
        verbose_name = "ajustes"
        verbose_name_plural = "ajustes"

    def __str__(self):
        return "Ajustes generales"

    def save(self, *args, **kwargs):
        self.pk = 1
        if self._state.adding and type(self).objects.filter(pk=1).exists():
            # Siempre hay una sola fila: grabar desde una instancia nueva la pisa.
            self._state.adding = False
        super().save(*args, **kwargs)

    @classmethod
    def actuales(cls):
        ajustes, _ = cls.objects.get_or_create(pk=1)
        return ajustes

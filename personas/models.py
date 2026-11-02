from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class TipoDocumento(models.TextChoices):
    CEDULA = "CEDULA", "Cédula"
    RUC = "RUC", "RUC"


class Genero(models.TextChoices):
    SIN_DEFINIR = "SIN DEFINIR", "Sin definir"
    MASCULINO = "MASCULINO", "Masculino"
    FEMENINO = "FEMENINO", "Femenino"


class Persona(models.Model):
    id = models.AutoField(primary_key=True, db_column="pers_id")
    tipo_documento = models.CharField(
        "tipo de documento",
        max_length=6,
        choices=TipoDocumento.choices,
        db_column="pers_tipo_documento",
    )
    documento = models.CharField(
        "documento",
        max_length=45,
        unique=True,
        db_column="pers_documento",
        error_messages={"unique": "Ya hay una persona con ese documento."},
    )
    razon_social = models.CharField("razón social", max_length=300, db_column="pers_razon_social")
    fecha_nacimiento = models.DateField(
        "fecha de nacimiento",
        null=True,
        blank=True,
        db_column="pers_fecha_nacimiento",
    )
    genero = models.CharField(
        "género",
        max_length=11,
        choices=Genero.choices,
        db_column="pers_genero",
    )
    direccion = models.CharField("dirección", max_length=300, db_column="pers_direccion")
    celular = models.CharField(
        "celular",
        max_length=30,
        null=True,
        blank=True,
        db_column="pers_celular",
    )
    activo = models.BooleanField("activo", default=True, db_column="pers_activo")
    observacion = models.CharField(
        "observación",
        max_length=300,
        null=True,
        blank=True,
        db_column="pers_observacion",
    )
    es_cliente = models.BooleanField("cliente", default=False, db_column="pers_es_cliente")
    es_proveedor = models.BooleanField("proveedor", default=False, db_column="pers_es_proveedor")
    es_empleado = models.BooleanField("empleado", default=False, db_column="pers_es_empleado")

    class Meta:
        db_table = "personas"
        verbose_name = "persona"
        verbose_name_plural = "personas"
        ordering = ["razon_social"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(es_cliente=True)
                    | models.Q(es_proveedor=True)
                    | models.Q(es_empleado=True)
                ),
                name="personas_al_menos_un_rol",
                violation_error_message=("Marcá al menos un rol: cliente, proveedor o personal."),
            ),
        ]

    def clean(self):
        super().clean()
        if self.fecha_nacimiento and self.fecha_nacimiento > timezone.localdate():
            raise ValidationError(
                {"fecha_nacimiento": ("La fecha de nacimiento no puede ser futura.")}
            )

    @property
    def roles_lista(self):
        roles = []
        if self.es_cliente:
            roles.append("Cliente")
        if self.es_proveedor:
            roles.append("Proveedor")
        if self.es_empleado:
            roles.append("Personal")
        return roles

    @property
    def roles_texto(self):
        return ", ".join(self.roles_lista) or "—"

    def __str__(self):
        return f"{self.razon_social} ({self.documento})"

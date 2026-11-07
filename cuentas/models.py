from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class EstadoTransferencia(models.TextChoices):
    CONFIRMADA = "CONFIRMADA", "Confirmada"
    ANULADA = "ANULADA", "Anulada"


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

    def etiqueta_cobro(self) -> str:
        numero = (self.numero or "").strip()
        if numero:
            return f"{self.descripcion} · {numero}"
        return self.descripcion


class Transferencia(models.Model):
    id = models.AutoField(primary_key=True, db_column="trans_id")
    fecha = models.DateField("fecha", default=timezone.localdate, db_column="trans_fecha")
    estado = models.CharField(
        "estado",
        max_length=10,
        choices=EstadoTransferencia.choices,
        default=EstadoTransferencia.CONFIRMADA,
        db_column="trans_estado",
    )
    cuenta_origen = models.ForeignKey(
        Cuenta,
        on_delete=models.RESTRICT,
        db_column="trans_cuen_origen_id",
        related_name="transferencias_salida",
        verbose_name="cuenta de salida",
    )
    cuenta_destino = models.ForeignKey(
        Cuenta,
        on_delete=models.RESTRICT,
        db_column="trans_cuen_destino_id",
        related_name="transferencias_entrada",
        verbose_name="cuenta de entrada",
    )
    importe = models.DecimalField(
        "importe",
        max_digits=15,
        decimal_places=0,
        db_column="trans_importe",
    )
    comprobante = models.CharField(
        "comprobante",
        max_length=80,
        blank=True,
        db_column="trans_comprobante",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        db_column="trans_usuario_id",
        related_name="transferencias",
        verbose_name="usuario",
    )
    anulado_en = models.DateTimeField(
        "anulado en",
        null=True,
        blank=True,
        db_column="trans_anulado_en",
    )
    anulado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="trans_anulado_por_id",
        related_name="transferencias_anuladas",
        verbose_name="anulado por",
    )

    class Meta:
        db_table = "transferencias"
        verbose_name = "transferencia"
        verbose_name_plural = "transferencias"
        ordering = ["-fecha", "-id"]

    def __str__(self):
        if self.pk:
            return f"Transferencia {self.pk}"
        return "Transferencia"

    def clean(self):
        super().clean()
        if (
            self.cuenta_origen_id
            and self.cuenta_destino_id
            and self.cuenta_origen_id == self.cuenta_destino_id
        ):
            raise ValidationError("La cuenta de salida y la de entrada tienen que ser distintas.")
        if self.importe is not None and self.importe <= 0:
            raise ValidationError({"importe": "El importe tiene que ser mayor a cero."})
        if self.comprobante:
            self.comprobante = self.comprobante.strip()

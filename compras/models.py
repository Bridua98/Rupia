from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from inventario.models import TipoItem


class TipoCompra(models.TextChoices):
    FACTURA_CONTADO = "FAC_CON", "Factura contado"
    FACTURA_CREDITO = "FAC_CRE", "Factura crédito"
    EGRESO = "EGRESO", "Egreso"


class EstadoCompra(models.TextChoices):
    EN_CURSO = "EN_CURSO", "En curso"
    CONFIRMADA = "CONFIRMADA", "Confirmada"
    ANULADA = "ANULADA", "Anulada"


def formatear_numero_factura(establecimiento, punto, secuencial) -> str:
    return f"{establecimiento}-{punto}-{int(secuencial):07d}"


class Compra(models.Model):
    id = models.AutoField(primary_key=True, db_column="compr_id")
    fecha = models.DateField("fecha", db_column="compr_fecha")
    estado = models.CharField(
        "estado",
        max_length=10,
        choices=EstadoCompra.choices,
        default=EstadoCompra.EN_CURSO,
        db_column="compr_estado",
    )
    tipo = models.CharField(
        "tipo",
        max_length=8,
        choices=TipoCompra.choices,
        default=TipoCompra.FACTURA_CONTADO,
        db_column="compr_tipo",
    )
    proveedor = models.ForeignKey(
        "personas.Persona",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        db_column="compr_pers_id",
        related_name="compras",
        verbose_name="proveedor",
    )
    cuenta = models.ForeignKey(
        "cuentas.Cuenta",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        db_column="compr_cuen_id",
        related_name="compras",
        verbose_name="cuenta",
    )
    timbrado = models.CharField(
        "timbrado",
        max_length=20,
        blank=True,
        db_column="compr_timbrado",
    )
    establecimiento = models.CharField(
        "establecimiento",
        max_length=3,
        blank=True,
        db_column="compr_establecimiento",
    )
    punto_codigo = models.CharField(
        "punto",
        max_length=3,
        blank=True,
        db_column="compr_punto_codigo",
    )
    secuencial = models.PositiveIntegerField(
        "secuencial",
        null=True,
        blank=True,
        db_column="compr_secuencial",
    )
    numero_completo = models.CharField(
        "número",
        max_length=15,
        null=True,
        blank=True,
        db_column="compr_numero_completo",
    )
    observacion = models.CharField(
        "observación",
        max_length=300,
        blank=True,
        db_column="compr_observacion",
    )
    afectar_precios = models.BooleanField(
        "afectar precios",
        default=False,
        db_column="compr_afectar_precios",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        db_column="compr_usuario_id",
        related_name="compras",
        verbose_name="usuario",
    )
    anulado_en = models.DateTimeField(
        "anulado en",
        null=True,
        blank=True,
        db_column="compr_anulado_en",
    )
    anulado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="compr_anulado_por_id",
        related_name="compras_anuladas",
        verbose_name="anulado por",
    )

    class Meta:
        db_table = "compras"
        verbose_name = "compra"
        verbose_name_plural = "compras"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario"],
                condition=models.Q(estado=EstadoCompra.EN_CURSO),
                name="compras_una_en_curso_por_usuario",
            ),
            models.UniqueConstraint(
                fields=["proveedor", "timbrado", "numero_completo"],
                condition=(
                    models.Q(estado=EstadoCompra.CONFIRMADA)
                    & models.Q(
                        tipo__in=(
                            TipoCompra.FACTURA_CONTADO,
                            TipoCompra.FACTURA_CREDITO,
                        )
                    )
                    & models.Q(numero_completo__isnull=False)
                    & ~models.Q(timbrado="")
                ),
                name="compras_proveedor_timbrado_numero",
            ),
        ]

    def __str__(self):
        if self.es_factura and self.numero_completo:
            return self.numero_completo
        if self.pk:
            return f"Compra {self.pk}"
        return "Compra"

    @property
    def es_factura(self) -> bool:
        return self.tipo in (TipoCompra.FACTURA_CONTADO, TipoCompra.FACTURA_CREDITO)


class CompraDetalle(models.Model):
    id = models.AutoField(primary_key=True, db_column="comprdeta_id")
    compra = models.ForeignKey(
        Compra,
        on_delete=models.CASCADE,
        db_column="comprdeta_compr_id",
        related_name="detalles",
        verbose_name="compra",
    )
    item = models.ForeignKey(
        "inventario.Item",
        on_delete=models.RESTRICT,
        db_column="comprdeta_item_id",
        related_name="compras_detalle",
        verbose_name="ítem",
    )
    unidad_medida = models.ForeignKey(
        "inventario.UnidadMedida",
        on_delete=models.RESTRICT,
        db_column="comprdeta_unidmedi_id",
        related_name="compras_detalle",
        verbose_name="unidad de medida",
    )
    unidad_negocio = models.ForeignKey(
        "negocio.UnidadNegocio",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        db_column="comprdeta_unidnego_id",
        related_name="compras_detalle",
        verbose_name="unidad de negocio",
    )
    cantidad = models.DecimalField(
        "cantidad",
        max_digits=15,
        decimal_places=3,
        db_column="comprdeta_cantidad",
    )
    costo = models.DecimalField(
        "costo",
        max_digits=15,
        decimal_places=3,
        db_column="comprdeta_costo",
    )
    tasa_iva = models.PositiveSmallIntegerField(
        "tasa IVA",
        db_column="comprdeta_tasa_iva",
    )
    subtotal = models.DecimalField(
        "subtotal",
        max_digits=15,
        decimal_places=3,
        db_column="comprdeta_subtotal",
    )

    class Meta:
        db_table = "compras_detalles"
        verbose_name = "detalle de compra"
        verbose_name_plural = "detalles de compra"
        ordering = ["id"]

    def __str__(self):
        return f"{self.item} ({self.cantidad})"

    def clean(self):
        super().clean()
        if self.item_id and self.item.tipo == TipoItem.GASTO and not self.unidad_negocio_id:
            raise ValidationError({"unidad_negocio": "Elegí una unidad de negocio."})

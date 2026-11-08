from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class TipoComprobante(models.TextChoices):
    TICKET = "TICKET", "Ticket"
    FACTURA = "FACTURA", "Factura"


class EstadoVenta(models.TextChoices):
    EN_CURSO = "EN_CURSO", "En curso"
    COBRADA = "COBRADA", "Cobrada"
    ANULADA = "ANULADA", "Anulada"


class TipoAnulacion(models.TextChoices):
    FISICA = "FISICA", "Anulación física"
    REUTILIZABLE = "REUTILIZABLE", "Número reutilizable"


class MedioPago(models.TextChoices):
    EFECTIVO = "EFECTIVO", "Efectivo"
    TRANSFERENCIA = "TRANSFERENCIA", "Transferencia"
    TARJETA = "TARJETA", "Tarjeta"
    QR = "QR", "QR"


class CondicionVenta(models.TextChoices):
    CONTADO = "CONTADO", "Contado"


def formatear_numero_comprobante(establecimiento, punto, secuencial) -> str:
    return f"{establecimiento}-{punto}-{int(secuencial):07d}"


class PuntoExpedicion(models.Model):
    id = models.AutoField(primary_key=True, db_column="puntexpe_id")
    tipo = models.CharField(
        "tipo",
        max_length=8,
        choices=TipoComprobante.choices,
        unique=True,
        db_column="puntexpe_tipo",
    )
    establecimiento = models.CharField(
        "establecimiento",
        max_length=3,
        db_column="puntexpe_establecimiento",
    )
    codigo = models.CharField(
        "punto",
        max_length=3,
        db_column="puntexpe_codigo",
    )
    timbrado = models.CharField(
        "timbrado",
        max_length=8,
        db_column="puntexpe_timbrado",
    )
    vigencia_desde = models.DateField(
        "vigencia desde",
        db_column="puntexpe_vigencia_desde",
    )
    vigencia_hasta = models.DateField(
        "vigencia hasta",
        db_column="puntexpe_vigencia_hasta",
    )
    numero_desde = models.PositiveIntegerField(
        "número desde",
        db_column="puntexpe_numero_desde",
    )
    numero_hasta = models.PositiveIntegerField(
        "número hasta",
        db_column="puntexpe_numero_hasta",
    )
    numero_proximo = models.PositiveIntegerField(
        "número próximo",
        db_column="puntexpe_numero_proximo",
    )
    habilitado = models.BooleanField(
        "habilitado",
        default=True,
        db_column="puntexpe_habilitado",
    )
    emisor_razon_social = models.CharField(
        "razón social",
        max_length=300,
        db_column="puntexpe_emisor_razon_social",
    )
    emisor_ruc = models.CharField(
        "RUC",
        max_length=45,
        db_column="puntexpe_emisor_ruc",
    )
    emisor_direccion = models.CharField(
        "dirección",
        max_length=300,
        db_column="puntexpe_emisor_direccion",
    )
    emisor_telefono = models.CharField(
        "teléfono",
        max_length=45,
        blank=True,
        db_column="puntexpe_emisor_telefono",
    )
    emisor_actividad = models.CharField(
        "actividad",
        max_length=300,
        blank=True,
        db_column="puntexpe_emisor_actividad",
    )

    class Meta:
        db_table = "puntos_expedicion"
        verbose_name = "punto de expedición"
        verbose_name_plural = "puntos de expedición"
        ordering = ["tipo"]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.establecimiento}-{self.codigo}"

    @property
    def serie(self):
        return f"{self.establecimiento}-{self.codigo}"

    def clean(self):
        super().clean()
        errores = {}
        if not (self.establecimiento or "").isdigit() or len(self.establecimiento) != 3:
            errores["establecimiento"] = "El establecimiento tiene tres dígitos."
        if not (self.codigo or "").isdigit() or len(self.codigo) != 3:
            errores["codigo"] = "El punto tiene tres dígitos."
        if self.numero_desde and self.numero_hasta and self.numero_desde > self.numero_hasta:
            errores["numero_hasta"] = "El rango de números está al revés."
        if (
            self.numero_proximo
            and self.numero_desde
            and self.numero_hasta
            and not (self.numero_desde <= self.numero_proximo <= self.numero_hasta)
        ):
            errores["numero_proximo"] = "El próximo número tiene que estar en el rango."
        if (
            self.vigencia_desde
            and self.vigencia_hasta
            and self.vigencia_desde > self.vigencia_hasta
        ):
            errores["vigencia_hasta"] = "La vigencia está al revés."
        if errores:
            raise ValidationError(errores)

    def numero_completo(self, secuencial=None) -> str:
        return formatear_numero_comprobante(
            self.establecimiento,
            self.codigo,
            self.numero_proximo if secuencial is None else secuencial,
        )


class Venta(models.Model):
    id = models.AutoField(primary_key=True, db_column="vent_id")
    fecha = models.DateField("fecha", db_column="vent_fecha")
    estado = models.CharField(
        "estado",
        max_length=8,
        choices=EstadoVenta.choices,
        default=EstadoVenta.EN_CURSO,
        db_column="vent_estado",
    )
    cliente = models.ForeignKey(
        "personas.Persona",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        db_column="vent_pers_id",
        related_name="ventas",
        verbose_name="cliente",
    )
    caja = models.ForeignKey(
        "cuentas.Cuenta",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        db_column="vent_caja_id",
        related_name="ventas_caja",
        verbose_name="caja",
    )
    cuenta_cobro = models.ForeignKey(
        "cuentas.Cuenta",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        db_column="vent_cuen_id",
        related_name="ventas_cobro",
        verbose_name="cuenta de cobro",
    )
    medio = models.CharField(
        "medio de pago",
        max_length=14,
        choices=MedioPago.choices,
        default=MedioPago.EFECTIVO,
        db_column="vent_medio",
    )
    numero_comprobante_pago = models.CharField(
        "comprobante de pago",
        max_length=80,
        blank=True,
        db_column="vent_numero_comprobante_pago",
    )
    descuento = models.DecimalField(
        "descuento",
        max_digits=15,
        decimal_places=3,
        default=0,
        db_column="vent_descuento",
    )
    importe_recibido = models.DecimalField(
        "importe recibido",
        max_digits=15,
        decimal_places=3,
        default=0,
        db_column="vent_importe_recibido",
    )
    observacion = models.CharField(
        "observación",
        max_length=300,
        blank=True,
        db_column="vent_observacion",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        db_column="vent_usuario_id",
        related_name="ventas",
        verbose_name="usuario",
    )
    tipo_comprobante = models.CharField(
        "comprobante",
        max_length=8,
        choices=TipoComprobante.choices,
        default=TipoComprobante.TICKET,
        db_column="vent_tipo_comprobante",
    )
    punto = models.ForeignKey(
        PuntoExpedicion,
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        db_column="vent_puntexpe_id",
        related_name="ventas",
        verbose_name="punto de expedición",
    )
    timbrado = models.CharField(
        "timbrado",
        max_length=8,
        blank=True,
        db_column="vent_timbrado",
    )
    vigencia_desde = models.DateField(
        "vigencia desde",
        null=True,
        blank=True,
        db_column="vent_vigencia_desde",
    )
    vigencia_hasta = models.DateField(
        "vigencia hasta",
        null=True,
        blank=True,
        db_column="vent_vigencia_hasta",
    )
    establecimiento = models.CharField(
        "establecimiento",
        max_length=3,
        blank=True,
        db_column="vent_establecimiento",
    )
    punto_codigo = models.CharField(
        "punto",
        max_length=3,
        blank=True,
        db_column="vent_punto_codigo",
    )
    secuencial = models.PositiveIntegerField(
        "secuencial",
        null=True,
        blank=True,
        db_column="vent_secuencial",
    )
    numero_completo = models.CharField(
        "número",
        max_length=15,
        null=True,
        blank=True,
        db_column="vent_numero_completo",
    )
    emisor_razon_social = models.CharField(
        "razón social",
        max_length=300,
        blank=True,
        db_column="vent_emisor_razon_social",
    )
    emisor_ruc = models.CharField(
        "RUC",
        max_length=45,
        blank=True,
        db_column="vent_emisor_ruc",
    )
    emisor_direccion = models.CharField(
        "dirección",
        max_length=300,
        blank=True,
        db_column="vent_emisor_direccion",
    )
    emisor_telefono = models.CharField(
        "teléfono",
        max_length=45,
        blank=True,
        db_column="vent_emisor_telefono",
    )
    emisor_actividad = models.CharField(
        "actividad",
        max_length=300,
        blank=True,
        db_column="vent_emisor_actividad",
    )
    condicion_venta = models.CharField(
        "condición de venta",
        max_length=8,
        choices=CondicionVenta.choices,
        default=CondicionVenta.CONTADO,
        db_column="vent_condicion",
    )
    tipo_anulacion = models.CharField(
        "tipo de anulación",
        max_length=12,
        choices=TipoAnulacion.choices,
        blank=True,
        db_column="vent_tipo_anulacion",
    )
    anulado_en = models.DateTimeField(
        "anulado en",
        null=True,
        blank=True,
        db_column="vent_anulado_en",
    )
    anulado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="vent_anulado_por_id",
        related_name="ventas_anuladas",
        verbose_name="anulado por",
    )

    class Meta:
        db_table = "ventas"
        verbose_name = "venta"
        verbose_name_plural = "ventas"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario"],
                condition=models.Q(estado=EstadoVenta.EN_CURSO),
                name="ventas_una_en_curso_por_usuario",
            ),
            models.UniqueConstraint(
                fields=["tipo_comprobante", "timbrado", "numero_completo"],
                condition=(
                    (
                        models.Q(estado=EstadoVenta.COBRADA)
                        | models.Q(
                            estado=EstadoVenta.ANULADA,
                            tipo_anulacion=TipoAnulacion.FISICA,
                        )
                    )
                    & models.Q(numero_completo__isnull=False)
                    & ~models.Q(timbrado="")
                ),
                name="ventas_timbrado_numero_completo",
            ),
        ]

    def __str__(self):
        return self.numero_completo or f"Venta {self.pk}"


class VentaDetalle(models.Model):
    id = models.AutoField(primary_key=True, db_column="ventdeta_id")
    venta = models.ForeignKey(
        Venta,
        on_delete=models.CASCADE,
        db_column="ventdeta_vent_id",
        related_name="detalles",
        verbose_name="venta",
    )
    item = models.ForeignKey(
        "inventario.Item",
        on_delete=models.RESTRICT,
        db_column="ventdeta_item_id",
        related_name="ventas_detalle",
        verbose_name="ítem",
    )
    unidad_medida = models.ForeignKey(
        "inventario.UnidadMedida",
        on_delete=models.RESTRICT,
        db_column="ventdeta_unidmedi_id",
        related_name="ventas_detalle",
        verbose_name="unidad de medida",
    )
    cantidad = models.DecimalField(
        "cantidad",
        max_digits=15,
        decimal_places=3,
        db_column="ventdeta_cantidad",
    )
    precio = models.DecimalField(
        "precio",
        max_digits=15,
        decimal_places=3,
        db_column="ventdeta_precio",
    )
    tasa_iva = models.PositiveSmallIntegerField(
        "tasa IVA",
        db_column="ventdeta_tasa_iva",
    )
    subtotal = models.DecimalField(
        "subtotal",
        max_digits=15,
        decimal_places=3,
        db_column="ventdeta_subtotal",
    )
    descuento_porcentaje = models.DecimalField(
        "descuento %",
        max_digits=6,
        decimal_places=2,
        default=0,
        db_column="ventdeta_descuento_porcentaje",
    )

    class Meta:
        db_table = "ventas_detalles"
        verbose_name = "detalle de venta"
        verbose_name_plural = "detalles de venta"
        ordering = ["id"]

    def __str__(self):
        return f"{self.item} ({self.cantidad})"

from django.conf import settings
from django.db import models


class Sector(models.Model):
    """Lugar donde se prepara lo que se pide: cocina, barra, parrilla..."""

    id = models.AutoField(primary_key=True, db_column="sect_id")
    nombre = models.CharField(
        "nombre",
        max_length=80,
        unique=True,
        db_column="sect_nombre",
    )
    activo = models.BooleanField("activo", default=True, db_column="sect_activo")
    exige_empezar = models.BooleanField(
        "pide empezar",
        default=False,
        db_column="sect_exige_empezar",
    )
    minutos_demora = models.PositiveSmallIntegerField(
        "minutos de demora",
        default=15,
        db_column="sect_minutos_demora",
    )

    class Meta:
        db_table = "sectores"
        verbose_name = "sector de preparación"
        verbose_name_plural = "sectores de preparación"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class SectorCategoria(models.Model):
    """A qué sector va cada categoría. Una categoría va a un solo sector."""

    id = models.AutoField(primary_key=True, db_column="sectcate_id")
    sector = models.ForeignKey(
        Sector,
        on_delete=models.CASCADE,
        db_column="sectcate_sect_id",
        related_name="categorias",
        verbose_name="sector",
    )
    categoria = models.OneToOneField(
        "inventario.ItemCategoria",
        on_delete=models.CASCADE,
        db_column="sectcate_itemcate_id",
        related_name="sector_preparacion",
        verbose_name="categoría",
    )

    class Meta:
        db_table = "sectores_categorias"
        verbose_name = "categoría del sector"
        verbose_name_plural = "categorías del sector"

    def __str__(self):
        return f"{self.categoria} → {self.sector}"


class SectorItem(models.Model):
    """Excepción por producto: le gana al sector de su categoría."""

    id = models.AutoField(primary_key=True, db_column="sectitem_id")
    item = models.OneToOneField(
        "inventario.Item",
        on_delete=models.CASCADE,
        db_column="sectitem_item_id",
        related_name="sector_preparacion",
        verbose_name="producto",
    )
    sector = models.ForeignKey(
        Sector,
        on_delete=models.CASCADE,
        db_column="sectitem_sect_id",
        related_name="items",
        verbose_name="sector",
    )

    class Meta:
        db_table = "sectores_items"
        verbose_name = "producto con otro sector"
        verbose_name_plural = "productos con otro sector"
        ordering = ["item__descripcion"]

    def __str__(self):
        return f"{self.item} → {self.sector}"


class Mesa(models.Model):
    id = models.AutoField(primary_key=True, db_column="mesa_id")
    nombre = models.CharField(
        "nombre",
        max_length=40,
        unique=True,
        db_column="mesa_nombre",
    )
    zona = models.CharField(
        "zona",
        max_length=60,
        blank=True,
        db_column="mesa_zona",
    )
    capacidad = models.PositiveSmallIntegerField(
        "capacidad",
        null=True,
        blank=True,
        db_column="mesa_capacidad",
    )
    orden = models.PositiveIntegerField("orden", default=0, db_column="mesa_orden")
    activa = models.BooleanField("activa", default=True, db_column="mesa_activa")

    class Meta:
        db_table = "mesas"
        verbose_name = "mesa"
        verbose_name_plural = "mesas"
        ordering = ["zona", "orden", "nombre"]

    def __str__(self):
        return self.nombre


class EstadoComanda(models.TextChoices):
    ABIERTA = "ABIERTA", "Abierta"
    CUENTA_PEDIDA = "CUENTA", "Pidió la cuenta"
    CERRADA = "CERRADA", "Cerrada"
    ANULADA = "ANULADA", "Anulada"


ESTADOS_ACTIVOS = (EstadoComanda.ABIERTA, EstadoComanda.CUENTA_PEDIDA)


class Comanda(models.Model):
    """Cuenta abierta de una mesa o a nombre de alguien."""

    id = models.AutoField(primary_key=True, db_column="coma_id")
    mesa = models.ForeignKey(
        Mesa,
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        db_column="coma_mesa_id",
        related_name="comandas",
        verbose_name="mesa",
    )
    nombre = models.CharField(
        "a nombre de",
        max_length=80,
        blank=True,
        db_column="coma_nombre",
    )
    cliente = models.ForeignKey(
        "personas.Persona",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        db_column="coma_pers_id",
        related_name="comandas",
        verbose_name="cliente",
    )
    personas = models.PositiveSmallIntegerField(
        "personas",
        null=True,
        blank=True,
        db_column="coma_personas",
    )
    mozo = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        db_column="coma_mozo_id",
        related_name="comandas",
        verbose_name="mozo",
    )
    estado = models.CharField(
        "estado",
        max_length=8,
        choices=EstadoComanda.choices,
        default=EstadoComanda.ABIERTA,
        db_column="coma_estado",
    )
    abierta_en = models.DateTimeField("abierta", db_column="coma_abierta_en")
    cerrada_en = models.DateTimeField(
        "cerrada",
        null=True,
        blank=True,
        db_column="coma_cerrada_en",
    )
    motivo_anulacion = models.CharField(
        "motivo de anulación",
        max_length=200,
        blank=True,
        db_column="coma_motivo_anulacion",
    )
    anulada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="coma_anulada_por_id",
        related_name="comandas_anuladas",
        verbose_name="anulada por",
    )

    class Meta:
        db_table = "comandas"
        verbose_name = "comanda"
        verbose_name_plural = "comandas"
        ordering = ["-id"]
        constraints = [
            # MySQL ignora las restricciones condicionales: el código además
            # bloquea la mesa al abrir (ver mesas.comandas.abrir).
            models.UniqueConstraint(
                fields=["mesa"],
                condition=models.Q(estado__in=["ABIERTA", "CUENTA"]),
                name="comandas_una_activa_por_mesa",
            ),
        ]

    def __str__(self):
        return self.titulo

    @property
    def titulo(self):
        if self.mesa_id:
            return f"Mesa {self.mesa.nombre}"
        if self.nombre:
            return self.nombre
        if self.cliente_id:
            return str(self.cliente)
        return f"Comanda {self.pk}"

    @property
    def activa(self):
        return self.estado in ESTADOS_ACTIVOS


class Ronda(models.Model):
    """Lo que el mozo envió de una vez a cocina y barra."""

    id = models.AutoField(primary_key=True, db_column="rond_id")
    comanda = models.ForeignKey(
        Comanda,
        on_delete=models.CASCADE,
        db_column="rond_coma_id",
        related_name="rondas",
        verbose_name="comanda",
    )
    numero = models.PositiveSmallIntegerField("número", db_column="rond_numero")
    enviada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        db_column="rond_usuario_id",
        related_name="rondas_enviadas",
        verbose_name="enviada por",
    )
    enviada_en = models.DateTimeField("enviada", db_column="rond_enviada_en")

    class Meta:
        db_table = "comandas_rondas"
        verbose_name = "ronda"
        verbose_name_plural = "rondas"
        ordering = ["comanda", "numero"]
        constraints = [
            models.UniqueConstraint(
                fields=["comanda", "numero"],
                name="comandas_rondas_numero",
            ),
        ]

    def __str__(self):
        return f"Ronda {self.numero}"


class ComandaDetalle(models.Model):
    id = models.AutoField(primary_key=True, db_column="comadeta_id")
    comanda = models.ForeignKey(
        Comanda,
        on_delete=models.CASCADE,
        db_column="comadeta_coma_id",
        related_name="detalles",
        verbose_name="comanda",
    )
    item = models.ForeignKey(
        "inventario.Item",
        on_delete=models.RESTRICT,
        db_column="comadeta_item_id",
        related_name="comandas_detalle",
        verbose_name="ítem",
    )
    unidad_medida = models.ForeignKey(
        "inventario.UnidadMedida",
        on_delete=models.RESTRICT,
        db_column="comadeta_unidmedi_id",
        related_name="comandas_detalle",
        verbose_name="unidad de medida",
    )
    cantidad = models.DecimalField(
        "cantidad",
        max_digits=15,
        decimal_places=3,
        db_column="comadeta_cantidad",
    )
    precio = models.DecimalField(
        "precio",
        max_digits=15,
        decimal_places=3,
        db_column="comadeta_precio",
    )
    tasa_iva = models.PositiveSmallIntegerField("tasa IVA", db_column="comadeta_tasa_iva")
    nota = models.CharField("nota", max_length=120, blank=True, db_column="comadeta_nota")
    cargado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        db_column="comadeta_usuario_id",
        related_name="comandas_cargadas",
        verbose_name="cargado por",
    )
    cargado_en = models.DateTimeField("cargado", db_column="comadeta_cargado_en")
    ronda = models.ForeignKey(
        Ronda,
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        db_column="comadeta_rond_id",
        related_name="detalles",
        verbose_name="ronda",
    )
    sector = models.ForeignKey(
        Sector,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="comadeta_sect_id",
        related_name="comandas_detalle",
        verbose_name="sector",
    )
    anulado = models.BooleanField("anulado", default=False, db_column="comadeta_anulado")
    # La línea de venta que la cobra. Si se quita de la venta o la venta se
    # cancela, el vínculo se borra solo y la línea vuelve a estar pendiente.
    venta_detalle = models.ForeignKey(
        "ventas.VentaDetalle",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="comadeta_ventdeta_id",
        related_name="comanda_detalles",
        verbose_name="línea de venta",
    )

    class Meta:
        db_table = "comandas_detalles"
        verbose_name = "detalle de comanda"
        verbose_name_plural = "detalles de comanda"
        ordering = ["id"]

    def __str__(self):
        return f"{self.item} ({self.cantidad})"

    @property
    def enviado(self):
        return self.ronda_id is not None


class ComandaAnulacion(models.Model):
    """Registro de lo que se sacó después de enviarse a cocina o barra."""

    id = models.AutoField(primary_key=True, db_column="comaanul_id")
    detalle = models.ForeignKey(
        ComandaDetalle,
        on_delete=models.CASCADE,
        db_column="comaanul_comadeta_id",
        related_name="anulaciones",
        verbose_name="detalle",
    )
    cantidad = models.DecimalField(
        "cantidad",
        max_digits=15,
        decimal_places=3,
        db_column="comaanul_cantidad",
    )
    motivo = models.CharField("motivo", max_length=200, db_column="comaanul_motivo")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        db_column="comaanul_usuario_id",
        related_name="comandas_anulaciones",
        verbose_name="usuario",
    )
    fecha = models.DateTimeField("fecha", db_column="comaanul_fecha")

    class Meta:
        db_table = "comandas_anulaciones"
        verbose_name = "anulación de comanda"
        verbose_name_plural = "anulaciones de comanda"
        ordering = ["-fecha"]


class TipoEnvio(models.TextChoices):
    PEDIDO = "PEDIDO", "Pedido"
    ANULACION = "ANULA", "Anulación"


class EstadoEnvio(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    IMPRESO = "IMPRESO", "Impreso"
    PREPARACION = "PREPARACION", "En preparación"
    LISTO = "LISTO", "Listo"


class EnvioSector(models.Model):
    """Lo que le llega a un sector: el pedido de una ronda o una anulación."""

    id = models.AutoField(primary_key=True, db_column="envi_id")
    comanda = models.ForeignKey(
        Comanda,
        on_delete=models.CASCADE,
        db_column="envi_coma_id",
        related_name="envios",
        verbose_name="comanda",
    )
    ronda = models.ForeignKey(
        Ronda,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_column="envi_rond_id",
        related_name="envios",
        verbose_name="ronda",
    )
    sector = models.ForeignKey(
        Sector,
        on_delete=models.RESTRICT,
        db_column="envi_sect_id",
        related_name="envios",
        verbose_name="sector",
    )
    tipo = models.CharField(
        "tipo",
        max_length=6,
        choices=TipoEnvio.choices,
        default=TipoEnvio.PEDIDO,
        db_column="envi_tipo",
    )
    estado = models.CharField(
        "estado",
        max_length=11,
        choices=EstadoEnvio.choices,
        default=EstadoEnvio.PENDIENTE,
        db_column="envi_estado",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        db_column="envi_usuario_id",
        related_name="envios_sector",
        verbose_name="usuario",
    )
    creado_en = models.DateTimeField("creado", db_column="envi_creado_en")
    impreso_en = models.DateTimeField("impreso", null=True, blank=True, db_column="envi_impreso_en")
    empezado_en = models.DateTimeField(
        "empezado", null=True, blank=True, db_column="envi_empezado_en"
    )
    listo_en = models.DateTimeField("listo", null=True, blank=True, db_column="envi_listo_en")

    class Meta:
        db_table = "comandas_envios"
        verbose_name = "envío a sector"
        verbose_name_plural = "envíos a sector"
        ordering = ["creado_en", "id"]
        indexes = [
            models.Index(fields=["sector", "estado"], name="comandas_envios_cola"),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.comanda} → {self.sector}"


class EnvioSectorLinea(models.Model):
    id = models.AutoField(primary_key=True, db_column="envilin_id")
    envio = models.ForeignKey(
        EnvioSector,
        on_delete=models.CASCADE,
        db_column="envilin_envi_id",
        related_name="lineas",
        verbose_name="envío",
    )
    detalle = models.ForeignKey(
        ComandaDetalle,
        on_delete=models.CASCADE,
        db_column="envilin_comadeta_id",
        related_name="envios",
        verbose_name="detalle",
    )
    descripcion = models.CharField("descripción", max_length=300, db_column="envilin_descripcion")
    cantidad = models.DecimalField(
        "cantidad",
        max_digits=15,
        decimal_places=3,
        db_column="envilin_cantidad",
    )
    unidad = models.CharField("unidad", max_length=20, db_column="envilin_unidad")
    nota = models.CharField("nota", max_length=120, blank=True, db_column="envilin_nota")

    class Meta:
        db_table = "comandas_envios_lineas"
        verbose_name = "línea de envío"
        verbose_name_plural = "líneas de envío"
        ordering = ["id"]

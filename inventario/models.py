from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class TipoItem(models.TextChoices):
    PRODUCTO = "PRODUCTO", "Producto"
    GASTO = "GASTO", "Gasto"


class TasaIva(models.IntegerChoices):
    DIEZ = 10, "10%"
    CINCO = 5, "5%"
    CERO = 0, "0%"


class TipoMovimiento(models.TextChoices):
    COMPRA = "CM", "Compra"
    VENTA = "VT", "Venta"
    AJUSTE_POSITIVO = "A+", "Ajuste positivo"
    AJUSTE_NEGATIVO = "A-", "Ajuste negativo"


class OrigenPrecio(models.TextChoices):
    FICHA = "FICHA", "Ficha"
    MASIVO = "MASIVO", "Masivo"
    COMPRA = "COMPRA", "Compra"


class RelacionUnidad(models.TextChoices):
    MENOR = "MENOR", "Menor"
    MAYOR = "MAYOR", "Mayor"


class Marca(models.Model):
    id = models.AutoField(primary_key=True, db_column="marc_id")
    descripcion = models.CharField(
        "descripción",
        max_length=200,
        unique=True,
        db_column="marc_descripcion",
    )

    class Meta:
        db_table = "marcas"
        verbose_name = "marca"
        verbose_name_plural = "marcas"
        ordering = ["descripcion"]

    def __str__(self):
        return self.descripcion


class ItemCategoria(models.Model):
    id = models.AutoField(primary_key=True, db_column="itemcate_id")
    descripcion = models.CharField(
        "descripción",
        max_length=300,
        unique=True,
        db_column="itemcate_descripcion",
    )

    class Meta:
        db_table = "items_categorias"
        verbose_name = "categoría de ítem"
        verbose_name_plural = "categorías de ítems"
        ordering = ["descripcion"]

    def __str__(self):
        return self.descripcion


class UnidadMedida(models.Model):
    id = models.AutoField(primary_key=True, db_column="unidmedi_id")
    descripcion = models.CharField(
        "descripción",
        max_length=100,
        unique=True,
        db_column="unidmedi_descripcion",
    )
    simbolo = models.CharField(
        "símbolo",
        max_length=10,
        unique=True,
        db_column="unidmedi_simbolo",
    )

    class Meta:
        db_table = "unidades_medidas"
        verbose_name = "unidad de medida"
        verbose_name_plural = "unidades de medida"
        ordering = ["descripcion"]

    def __str__(self):
        return f"{self.descripcion} ({self.simbolo})"


class Item(models.Model):
    id = models.AutoField(primary_key=True, db_column="item_id")
    marca = models.ForeignKey(
        Marca,
        on_delete=models.RESTRICT,
        db_column="item_marc_id",
        related_name="items",
        verbose_name="marca",
    )
    categoria = models.ForeignKey(
        ItemCategoria,
        on_delete=models.RESTRICT,
        db_column="item_itemcate_id",
        related_name="items",
        verbose_name="categoría",
    )
    unidad_medida = models.ForeignKey(
        UnidadMedida,
        on_delete=models.RESTRICT,
        db_column="item_unidmedi_id",
        related_name="items",
        verbose_name="unidad de medida",
    )
    unidad_negocio = models.ForeignKey(
        "negocio.UnidadNegocio",
        on_delete=models.RESTRICT,
        db_column="item_unidnego_id",
        related_name="items",
        verbose_name="unidad de negocio",
        null=True,
        blank=True,
    )
    codigo_barra = models.CharField(
        "código de barra",
        max_length=300,
        null=True,
        blank=True,
        db_column="item_codigo_barra",
    )
    descripcion = models.CharField(
        "descripción",
        max_length=300,
        unique=True,
        db_column="item_descripcion",
    )
    tipo = models.CharField("tipo", max_length=8, choices=TipoItem.choices, db_column="item_tipo")
    activo = models.BooleanField("activo", default=True, db_column="item_activo")
    precio = models.DecimalField(
        "precio",
        max_digits=15,
        decimal_places=3,
        null=True,
        blank=True,
        db_column="item_precio",
    )
    tasa_iva = models.PositiveSmallIntegerField(
        "tasa IVA",
        choices=TasaIva.choices,
        default=TasaIva.DIEZ,
        db_column="item_tasa_iva",
    )
    ultimo_costo = models.DecimalField(
        "último costo",
        max_digits=15,
        decimal_places=3,
        null=True,
        blank=True,
        db_column="item_ultimo_costo",
    )
    precio_segun_costo = models.BooleanField(
        "precio según último costo",
        default=False,
        db_column="item_precio_segun_costo",
    )
    imagen = models.CharField(
        "imagen",
        max_length=200,
        null=True,
        blank=True,
        db_column="item_imagen",
    )

    class Meta:
        db_table = "items"
        verbose_name = "ítem"
        verbose_name_plural = "ítems"
        ordering = ["descripcion"]

    def __str__(self):
        return self.descripcion

    def clean(self):
        super().clean()
        if self.tipo == TipoItem.PRODUCTO and not self.unidad_negocio_id:
            raise ValidationError({"unidad_negocio": "Elegí una unidad de negocio."})


class ItemMovimiento(models.Model):
    id = models.IntegerField(primary_key=True, db_column="itemmovi_id")
    item = models.ForeignKey(
        Item,
        on_delete=models.RESTRICT,
        db_column="itemmovi_item_id",
        related_name="movimientos",
        verbose_name="ítem",
    )
    unidad_medida = models.ForeignKey(
        UnidadMedida,
        on_delete=models.RESTRICT,
        db_column="itemmovi_unidmedi_id",
        related_name="movimientos",
        verbose_name="unidad de medida",
    )
    tipo = models.CharField(
        "tipo",
        max_length=2,
        choices=TipoMovimiento.choices,
        db_column="itemmovi_tipo",
    )
    fecha_movimiento = models.DateField(
        "fecha de movimiento",
        db_column="itemmovi_fecha_movimiento",
    )
    cantidad = models.DecimalField(
        "cantidad",
        max_digits=15,
        decimal_places=3,
        db_column="itemmovi_cantidad",
    )
    precio = models.DecimalField(
        "precio",
        max_digits=15,
        decimal_places=3,
        db_column="itemmovi_precio",
    )
    costo = models.DecimalField(
        "costo",
        max_digits=15,
        decimal_places=3,
        db_column="itemmovi_costo",
    )
    subtotal = models.DecimalField(
        "subtotal",
        max_digits=15,
        decimal_places=3,
        db_column="itemmovi_subtotal",
    )
    secuencia_origen = models.CharField(
        "secuencia de origen",
        max_length=45,
        null=True,
        blank=True,
        db_column="itemmovi_secuencia_origen",
    )
    secuencia_detalle_origen = models.IntegerField(
        "secuencia de detalle de origen",
        null=True,
        blank=True,
        db_column="itemmovi_secuencia_detalle_origen",
    )
    es_vigente = models.BooleanField("vigente", default=True, db_column="itemmovi_es_vigente")

    class Meta:
        db_table = "items_movimientos"
        verbose_name = "movimiento de ítem"
        verbose_name_plural = "movimientos de ítems"
        ordering = ["-fecha_movimiento", "-id"]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.item} ({self.fecha_movimiento})"


class AjusteStock(models.Model):
    id = models.PositiveIntegerField(primary_key=True, db_column="ajusstoc_id")
    fecha = models.DateField("fecha", db_column="ajusstoc_fecha")
    observacion = models.CharField(
        "observación",
        max_length=45,
        db_column="ajusstoc_observacion",
    )

    class Meta:
        db_table = "ajustes_stock"
        verbose_name = "ajuste de stock"
        verbose_name_plural = "ajustes de stock"
        ordering = ["-id"]

    def __str__(self):
        return f"Ajuste {self.id} ({self.fecha})"


class AjusteStockDetalle(models.Model):
    id = models.PositiveIntegerField(primary_key=True, db_column="ajusstocdeta_id")
    ajuste = models.ForeignKey(
        AjusteStock,
        on_delete=models.CASCADE,
        db_column="ajusstocdeta_ajusstoc_id",
        related_name="detalles",
        verbose_name="ajuste",
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.RESTRICT,
        db_column="ajusstocdeta_item_id",
        related_name="ajustes_detalle",
        verbose_name="ítem",
    )
    unidad_medida = models.ForeignKey(
        UnidadMedida,
        on_delete=models.RESTRICT,
        db_column="ajusstocdeta_unidmedi_id",
        related_name="ajustes_detalle",
        verbose_name="unidad de medida",
    )
    cantidad_anterior = models.DecimalField(
        "cantidad anterior",
        max_digits=15,
        decimal_places=3,
        db_column="ajusstocdeta_cantidad_anterior",
    )
    cantidad_nueva = models.DecimalField(
        "cantidad nueva",
        max_digits=15,
        decimal_places=3,
        db_column="ajusstocdeta_cantidad_nueva",
    )
    cantidad = models.DecimalField(
        "cantidad",
        max_digits=15,
        decimal_places=3,
        db_column="ajusstocdeta_cantidad",
    )

    class Meta:
        db_table = "ajustes_stock_detalles"
        verbose_name = "detalle de ajuste de stock"
        verbose_name_plural = "detalles de ajuste de stock"
        ordering = ["id"]

    def __str__(self):
        return f"{self.item} ({self.cantidad})"


class ItemPrecioHistorial(models.Model):
    id = models.AutoField(primary_key=True, db_column="itprehist_id")
    item = models.ForeignKey(
        Item,
        on_delete=models.RESTRICT,
        db_column="itprehist_item_id",
        related_name="precios_historial",
        verbose_name="ítem",
    )
    precio_anterior = models.DecimalField(
        "precio anterior",
        max_digits=15,
        decimal_places=3,
        null=True,
        blank=True,
        db_column="itprehist_precio_anterior",
    )
    precio_nuevo = models.DecimalField(
        "precio nuevo",
        max_digits=15,
        decimal_places=3,
        null=True,
        blank=True,
        db_column="itprehist_precio_nuevo",
    )
    ultimo_costo = models.DecimalField(
        "último costo",
        max_digits=15,
        decimal_places=3,
        null=True,
        blank=True,
        db_column="itprehist_ultimo_costo",
    )
    porcentaje = models.DecimalField(
        "porcentaje",
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        db_column="itprehist_porcentaje",
    )
    segun_costo = models.BooleanField(
        "según costo",
        db_column="itprehist_segun_costo",
    )
    origen = models.CharField(
        "origen",
        max_length=6,
        choices=OrigenPrecio.choices,
        db_column="itprehist_origen",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        db_column="itprehist_usuario_id",
        related_name="precios_historial",
        verbose_name="usuario",
    )
    fecha = models.DateTimeField("fecha", db_column="itprehist_fecha")
    lote = models.CharField(
        "lote",
        max_length=32,
        null=True,
        blank=True,
        db_column="itprehist_lote",
    )

    class Meta:
        db_table = "items_precios_historial"
        verbose_name = "historial de precio"
        verbose_name_plural = "historial de precios"
        ordering = ["-fecha", "-id"]

    def __str__(self):
        return f"{self.item} ({self.fecha})"


class ItemUnidad(models.Model):
    id = models.AutoField(primary_key=True, db_column="itemunid_id")
    item = models.ForeignKey(
        Item,
        on_delete=models.RESTRICT,
        db_column="itemunid_item_id",
        related_name="unidades",
        verbose_name="ítem",
    )
    unidad_medida = models.ForeignKey(
        UnidadMedida,
        on_delete=models.RESTRICT,
        db_column="itemunid_unidmedi_id",
        related_name="items_relacionados",
        verbose_name="unidad de medida",
    )
    relacion = models.CharField(
        "relación",
        max_length=5,
        choices=RelacionUnidad.choices,
        db_column="itemunid_relacion",
    )
    valor = models.DecimalField(
        "valor",
        max_digits=15,
        decimal_places=3,
        db_column="itemunid_valor",
    )

    class Meta:
        db_table = "items_unidades"
        verbose_name = "unidad relacionada"
        verbose_name_plural = "unidades relacionadas"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["item", "unidad_medida"],
                name="items_unidades_item_unidad",
            ),
        ]

    def __str__(self):
        return f"{self.item} · {self.unidad_medida}"

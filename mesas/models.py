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

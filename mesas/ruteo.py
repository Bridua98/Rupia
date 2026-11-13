"""A qué sector de preparación va cada producto."""

from mesas.models import SectorCategoria, SectorItem


def sector_de(item):
    """Sector activo al que va el ítem, o None si no se manda a ningún lado.

    La excepción por producto le gana a la de su categoría. Un sector inactivo
    no recibe nada: si la excepción apunta a uno, vale el de la categoría.
    """
    excepcion = (
        SectorItem.objects.select_related("sector")
        .filter(item_id=item.pk, sector__activo=True)
        .first()
    )
    if excepcion:
        return excepcion.sector
    por_categoria = (
        SectorCategoria.objects.select_related("sector")
        .filter(categoria_id=item.categoria_id, sector__activo=True)
        .first()
    )
    return por_categoria.sector if por_categoria else None

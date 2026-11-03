from django.db import models
from django.db.models import Prefetch
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.html import format_html

from core.cantidad import formatear_cantidad
from core.moneda import formatear_guaranies

_MONEDA = ("precio", "costo", "subtotal")


def _es_moneda(field):
    nombre = field.name.lower()
    etiqueta = str(field.verbose_name).lower()
    return any(token in nombre or token in etiqueta for token in _MONEDA)


def format_value(record, field):
    name = field.name
    value = getattr(record, name)

    if field.many_to_many:
        if not value.exists():
            return "—"
        return ", ".join(str(obj) for obj in value.all())

    if field.is_relation:
        if value is None:
            return "—"
        return str(value)

    if isinstance(field, models.BooleanField):
        return "Sí" if value else "No"

    if field.choices:
        if value is None or value == "":
            return "—"
        getter = getattr(record, f"get_{name}_display", None)
        return getter() if getter else str(value)

    if isinstance(field, models.DateTimeField):
        if value is None:
            return "—"
        return timezone.localtime(value).strftime("%d/%m/%Y %H:%M")

    if isinstance(field, models.DateField):
        if value is None:
            return "—"
        return value.strftime("%d/%m/%Y")

    if isinstance(field, models.DecimalField):
        if value is None:
            return "—"
        if _es_moneda(field):
            return formatear_guaranies(value)
        return formatear_cantidad(value)

    if name == "imagen" and value:
        try:
            url = reverse("item_imagen", args=[value])
        except NoReverseMatch:
            return str(value)
        return format_html(
            '<a class="view-imagen-link" href="{}" target="_blank" rel="noopener">Ver imagen</a>',
            url,
        )

    if value is None or value == "":
        return "—"
    return str(value)


def _es_catalogo(model):
    if model._meta.model_name == "user":
        return True
    campos = [field for field in model._meta.fields if not field.primary_key]
    if len(campos) <= 3 and any(field.name == "descripcion" for field in campos):
        return True
    return False


def _fk_maestro(child_model):
    fks = [
        field
        for field in child_model._meta.fields
        if field.many_to_one and not field.auto_created
    ]
    propias = [field for field in fks if not _es_catalogo(field.related_model)]
    if not propias:
        return None
    for field in propias:
        if field.remote_field.related_name in {"detalles", "unidades", "lineas"}:
            return field
    return propias[0]


def visible_fields(model, *, exclude=()):
    excluded = set(exclude)
    fields = []
    for field in model._meta.fields:
        if field.primary_key or field.name in excluded:
            continue
        fields.append(field)
    return fields


def record_header_fields(record):
    rows = []
    for field in visible_fields(record._meta.model):
        label = str(field.verbose_name).capitalize() if field.verbose_name else field.name
        rows.append({"label": label, "value": format_value(record, field)})
    return rows


def detail_relations(model):
    relations = []
    for rel in model._meta.related_objects:
        if not rel.one_to_many or rel.parent_link:
            continue
        accessor = rel.get_accessor_name()
        if not accessor or accessor == "+":
            continue
        maestro = _fk_maestro(rel.related_model)
        if maestro is None or maestro.name != rel.field.name:
            continue
        relations.append(rel)
    return relations


def _child_select_related(rel):
    names = []
    for field in rel.related_model._meta.fields:
        if field.is_relation and field.name != rel.field.name and not field.auto_created:
            names.append(field.name)
    return names


def view_queryset(model):
    queryset = model.objects.all()
    prefetches = []
    for rel in detail_relations(model):
        related_qs = rel.related_model.objects.all()
        select = _child_select_related(rel)
        if select:
            related_qs = related_qs.select_related(*select)
        prefetches.append(Prefetch(rel.get_accessor_name(), queryset=related_qs))
    if prefetches:
        queryset = queryset.prefetch_related(*prefetches)
    return queryset


def build_detail_tables(record):
    tables = []
    for rel in detail_relations(record._meta.model):
        child_fields = visible_fields(rel.related_model, exclude=(rel.field.name,))
        if not child_fields:
            continue
        headers = [
            str(field.verbose_name).capitalize() if field.verbose_name else field.name
            for field in child_fields
        ]
        rows = [
            [format_value(child, field) for field in child_fields]
            for child in getattr(record, rel.get_accessor_name()).all()
        ]
        tables.append(
            {
                "title": str(rel.related_model._meta.verbose_name_plural).capitalize(),
                "headers": headers,
                "rows": rows,
            }
        )
    return tables


def build_view_context(record):
    return {
        "view_record": record,
        "view_fields": record_header_fields(record),
        "view_tables": build_detail_tables(record),
    }

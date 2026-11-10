from django.db.models import Q
from django.utils import timezone

DEFAULT_MONTH_START = "month_start"
DEFAULT_TODAY = "today"


def default_date_value(spec):
    default = spec.get("default")
    if not default:
        return ""
    hoy = timezone.localdate()
    if default == DEFAULT_MONTH_START:
        return hoy.replace(day=1).isoformat()
    if default == DEFAULT_TODAY:
        return hoy.isoformat()
    return str(default)


def search_fields_for(view):
    fields = getattr(view, "search_fields", ()) or ()
    if fields:
        return fields
    return (view.search_field,)


def filter_specs_for(view):
    return getattr(view, "filters", ()) or ()


def filter_values(request, specs):
    values = {}
    for spec in specs:
        name = spec["name"]
        value = request.GET.get(name, "").strip()
        if not value and request.method == "POST":
            value = request.POST.get(f"filtro_{name}", "").strip()
        if not value:
            value = default_date_value(spec)
        if value:
            values[name] = value
    return values


def apply_search(queryset, query, fields):
    if not query:
        return queryset
    combined = Q()
    for field in fields:
        combined |= Q(**{f"{field}__icontains": query})
    return queryset.filter(combined)


def apply_filters(queryset, values, specs):
    for spec in specs:
        name = spec["name"]
        value = values.get(name)
        if not value:
            continue
        kind = spec.get("kind", "choice")
        if kind == "bool":
            if value == "1":
                queryset = queryset.filter(**{name: True})
            elif value == "0":
                queryset = queryset.filter(**{name: False})
        elif kind == "date":
            field = spec.get("field", name)
            lookup = spec.get("lookup", "exact")
            queryset = queryset.filter(**{f"{field}__{lookup}": value})
        elif kind == "skip":
            continue
        elif kind == "fk":
            options = spec.get("queryset")
            if callable(options):
                options = options()
            if options is None or not options.filter(pk=value).exists():
                continue
            queryset = queryset.filter(**{name: value})
        else:
            queryset = queryset.filter(**{name: value})
    return queryset


def filter_options(spec):
    kind = spec.get("kind", "choice")
    if kind in ("choice", "skip"):
        return list(spec.get("choices", ()))
    if kind == "fk":
        queryset = spec["queryset"]
        if callable(queryset):
            queryset = queryset()
        return list(queryset)
    if kind == "bool":
        return [("1", "Sí"), ("0", "No")]
    return list(spec.get("choices", ()))


def listado_query_params(view, extra=None):
    params = {}
    query = view.query()
    if query:
        params["q"] = query
    page = view.request.GET.get("page", "").strip()
    if page:
        params["page"] = page
    for name, value in filter_values(view.request, filter_specs_for(view)).items():
        params[name] = value
    if extra:
        for key, value in extra.items():
            if value is None or value == "":
                params.pop(key, None)
            else:
                params[key] = value
    return params

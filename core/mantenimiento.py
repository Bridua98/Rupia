from io import BytesIO
from urllib.parse import urlencode

import pandas as pd
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models.deletion import RestrictedError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, UpdateView
from django_tables2 import SingleTableView
from xhtml2pdf import pisa

from configuracion.permisos import PermisoRequeridoMixin, tiene_permiso
from core.listado import (
    apply_filters,
    apply_search,
    filter_options,
    filter_specs_for,
    filter_values,
    listado_query_params,
    search_fields_for,
)
from core.vista import build_view_context, view_queryset


def _skip_export(column):
    inner = getattr(column, "column", column)
    if getattr(inner, "exclude_from_export", False):
        return True
    return column.name == "acciones"


class ListadoExportMixin:
    """Imprime y exporta el listado filtrado completo, sin la página visible."""

    print_url_name = ""
    export_xlsx_url_name = ""
    export_pdf_url_name = ""
    export_basename = "listado"

    export_totals = False

    def export_dataset(self):
        table = self.table_class(self.get_queryset().none())
        columns = [column for column in table.columns if not _skip_export(column)]
        headers = [str(column.header) for column in columns]
        rows = []
        for record in self.get_queryset():
            row = []
            for column in columns:
                value = column.accessor.resolve(record)
                row.append("" if value is None else value)
            rows.append(row)
        if self.export_totals:
            total_row = self.export_totals_row(columns)
            if total_row is not None:
                rows.append(total_row)
        return headers, rows

    def export_totals_row(self, columns):
        return None

    def salida_extra_context(self):
        return {}

    def _salida_context(self):
        headers, rows = self.export_dataset()
        context = {
            "title": self.title,
            "query": self.query(),
            "headers": headers,
            "rows": rows,
            "record_count": len(rows),
            "list_url": self.list_query(),
            "generated_at": timezone.localtime().strftime("%d/%m/%Y %H:%M"),
        }
        context.update(self.salida_extra_context())
        return context

    def print_response(self):
        return render(self.request, "core/listado_print.html", self._salida_context())

    def xlsx_response(self):
        headers, rows = self.export_dataset()
        frame = pd.DataFrame(rows, columns=headers)
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            frame.to_excel(writer, index=False, sheet_name=self._sheet_name())
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{self.export_basename}.xlsx"'
        return response

    def pdf_response(self):
        html = render(
            self.request,
            "core/listado_pdf.html",
            self._salida_context(),
        ).content.decode()
        buffer = BytesIO()
        status = pisa.CreatePDF(html, dest=buffer, encoding="utf-8")
        if status.err:
            return HttpResponse("No se pudo generar el PDF.", status=500)
        response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{self.export_basename}.pdf"'
        return response

    def _sheet_name(self):
        cleaned = "".join(" " if char in "[]:*?/\\" else char for char in self.title)
        return (cleaned.strip() or "Listado")[:31]

    def _salida_url(self, url_name):
        if not url_name:
            return ""
        base = reverse(url_name)
        params = listado_query_params(self)
        params.pop("page", None)
        if not params:
            return base
        return f"{base}?{urlencode(params)}"


def mantenimiento_salida(list_view_class, kind):
    class SalidaView(LoginRequiredMixin, PermisoRequeridoMixin, View):
        permiso_formulario = getattr(list_view_class, "permiso_formulario", "")
        permiso_accion = "exportar"

        def get(self, request, *args, **kwargs):
            listado = list_view_class()
            listado.setup(request, *args, **kwargs)
            if kind == "print":
                return listado.print_response()
            if kind == "xlsx":
                return listado.xlsx_response()
            return listado.pdf_response()

    SalidaView.__name__ = f"{list_view_class.__name__}{kind.title()}View"
    return SalidaView


class MantenimientoListView(
    ListadoExportMixin, LoginRequiredMixin, PermisoRequeridoMixin, SingleTableView
):
    template_name = "core/mantenimiento_list.html"
    per_page = 10
    search_field = "descripcion"
    search_fields = ()
    filters = ()
    selection_param = "sel"
    search_label = ""
    search_placeholder = ""
    list_hint = ""
    record_noun = "registro"
    order_by = ("pk",)
    back_url_name = "home"
    panel_form_override = None
    force_nueva = False
    selected_override = None
    show_create = True
    permiso_accion = "ver"
    form_fields_template = "core/form_fields.html"
    view_exclude = ()

    def get_table_pagination(self, table):
        if not self.per_page:
            return False
        return {"per_page": self.per_page}

    def _listado_record_count(self):
        queryset = self.get_queryset()
        if isinstance(queryset, list):
            return len(queryset)
        return queryset.count()

    def query(self):
        if "q" in self.request.GET:
            return self.request.GET.get("q", "").strip()
        return self.request.POST.get("q", "").strip()

    def list_query(self, **extra):
        params = listado_query_params(self, extra)
        base = reverse(self.list_url_name)
        if not params:
            return base
        return f"{base}?{urlencode(params)}"

    def get_queryset(self):
        queryset = self.model.objects.order_by(*self.order_by)
        queryset = apply_search(queryset, self.query(), search_fields_for(self))
        specs = filter_specs_for(self)
        queryset = apply_filters(queryset, filter_values(self.request, specs), specs)
        return queryset

    def _filter_context(self):
        specs = filter_specs_for(self)
        if not specs:
            return {
                "list_filters": [],
                "filters_open": False,
                "active_filter_count": 0,
                "filter_values": {},
            }
        values = filter_values(self.request, specs)
        rows = []
        for spec in specs:
            name = spec["name"]
            rows.append(
                {
                    "name": name,
                    "label": spec["label"],
                    "kind": spec.get("kind", "choice"),
                    "value": values.get(name, ""),
                    "options": filter_options(spec),
                }
            )
        active = sum(1 for row in rows if row["value"])
        return {
            "list_filters": rows,
            "filters_open": active > 0 or self.request.GET.get("filtros") == "1",
            "active_filter_count": active,
            "filter_values": values,
        }

    def creating(self):
        return self.force_nueva or self.request.GET.get("nueva") == "1"

    def viewing(self):
        if self.creating():
            return False
        if self.panel_pk() is None:
            return False
        if self.request.GET.get("ver") == "1":
            return True
        if not getattr(self, "update_url_name", ""):
            return True
        formulario = getattr(self, "permiso_formulario", "")
        if formulario and not tiene_permiso(self.request.user, formulario, "modificar"):
            return True
        return False

    def puede(self, accion):
        formulario = getattr(self, "permiso_formulario", "")
        if not formulario:
            return True
        return tiene_permiso(self.request.user, formulario, accion)

    def panel_pk(self):
        if self.creating():
            return None
        if self.selected_override:
            return self.selected_override
        raw = self.request.GET.get(self.selection_param, "")
        if not str(raw).isdigit():
            return None
        pk = int(raw)
        if self.get_queryset().filter(pk=pk).exists():
            return pk
        return None

    def page_number_for_pk(self, pk):
        ids = list(self.get_queryset().values_list("pk", flat=True))
        try:
            index = ids.index(pk)
        except ValueError:
            return None
        return index // self.per_page + 1

    def get(self, request, *args, **kwargs):
        if (
            self.selection_param in request.GET
            and "page" not in request.GET
            and not self.creating()
        ):
            raw = request.GET.get(self.selection_param, "")
            if str(raw).isdigit():
                page = self.page_number_for_pk(int(raw))
                if page and page > 1:
                    params = request.GET.copy()
                    params["page"] = str(page)
                    return redirect(f"{request.path}?{params.urlencode()}")
        return super().get(request, *args, **kwargs)

    def get_table(self, **kwargs):
        table = super().get_table(**kwargs)
        table.list_query = self.list_query
        table.selection_param = self.selection_param
        table.update_url_name = (
            getattr(self, "update_url_name", "") if self.puede("modificar") else ""
        )
        table.delete_url_name = (
            getattr(self, "delete_url_name", "") if self.puede("eliminar") else ""
        )
        table.permiso_formulario = getattr(self, "permiso_formulario", "")
        self._visible_pks = [row.record.pk for row in table.paginated_rows]
        return table

    def selected_pk(self):
        if getattr(self, "_selected_cached", False):
            return self._selected_value
        if self.creating():
            value = None
        else:
            visible = getattr(self, "_visible_pks", None)
            if visible is None:
                visible = list(self.get_queryset().values_list("pk", flat=True)[: self.per_page])
            opened = self.panel_pk()
            value = opened if opened in visible else (visible[0] if visible else None)
        self._selected_value = value
        self._selected_cached = True
        return value

    def _panel_form(self, nueva, selected):
        if self.panel_form_override is not None:
            form = self.panel_form_override
        elif not getattr(self, "form_class", None):
            return None
        elif nueva:
            form = self.form_class()
        elif selected:
            form = self.form_class(instance=self.model.objects.get(pk=selected))
        else:
            return None
        if not nueva:
            for field in form.fields.values():
                if "autofocus" in field.widget.attrs:
                    field.widget.attrs = {
                        key: value
                        for key, value in field.widget.attrs.items()
                        if key != "autofocus"
                    }
        return form

    def get_view_record_queryset(self):
        return view_queryset(self.model)

    def _view_record(self, pk):
        return self.get_view_record_queryset().get(pk=pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        nueva = self.creating()
        viewing = self.viewing()
        selected = self.panel_pk()
        panel_form = None
        view_open = False
        view_context = {}
        panel_object = None

        if viewing and selected:
            record = self._view_record(selected)
            view_context = self.build_panel_view_context(record)
            view_open = True
            panel_object = record
        elif not viewing:
            panel_form = self._panel_form(nueva, selected)
            if panel_form is not None and getattr(panel_form.instance, "pk", None):
                panel_object = panel_form.instance

        detail_open = view_open or panel_form is not None
        edit_url = ""
        if (
            view_open
            and panel_object
            and getattr(self, "update_url_name", "")
            and self.puede("modificar")
        ):
            edit_url = self.list_query(**{self.selection_param: panel_object.pk})
        update_url_name = getattr(self, "update_url_name", "")
        create_url_name = getattr(self, "create_url_name", "")
        if not viewing and panel_object and update_url_name:
            panel_action = reverse(update_url_name, args=[panel_object.pk])
        elif not viewing and create_url_name:
            panel_action = reverse(create_url_name)
        else:
            panel_action = ""

        context.update(
            {
                "page_title": self.page_title,
                "eyebrow": self.eyebrow,
                "title": self.title,
                "back_url": reverse(self.back_url_name),
                "list_url": reverse(self.list_url_name),
                "create_url": self.list_query(nueva=1),
                "create_label": self.create_label,
                "show_create": self.show_create and self.puede("alta"),
                "form_fields_template": getattr(
                    self, "form_fields_template", "core/form_fields.html"
                ),
                "record_count": self._listado_record_count(),
                "list_hint": self.list_hint,
                "query": self.query(),
                "search_label": self.search_label,
                "search_placeholder": self.search_placeholder or self.search_label,
                "detail_open": detail_open,
                "view_open": view_open,
                "panel_form": panel_form,
                "panel_object": panel_object,
                "edit_url": edit_url,
                "panel_action": panel_action,
                "close_url": self.list_query(),
                "print_url": (
                    self._salida_url(self.print_url_name) if self.puede("exportar") else ""
                ),
                "export_xlsx_url": (
                    self._salida_url(self.export_xlsx_url_name) if self.puede("exportar") else ""
                ),
                "export_pdf_url": (
                    self._salida_url(self.export_pdf_url_name) if self.puede("exportar") else ""
                ),
            }
        )
        context.update(view_context)
        context.update(self._filter_context())
        return context

    def build_panel_view_context(self, record):
        return build_view_context(record, exclude=getattr(self, "view_exclude", ()))

    def get_table_kwargs(self):
        return {
            "row_attrs": {
                "data-id": lambda record: record.pk,
                "data-href": lambda record: self.list_query(**{self.selection_param: record.pk}),
                "aria-selected": lambda record: (
                    "true" if record.pk == self.selected_pk() else "false"
                ),
                "tabindex": lambda record: "0" if record.pk == self.selected_pk() else "-1",
            }
        }


class MantenimientoWriteMixin:
    def list_panel_url(self, **extra):
        params = {key: value for key, value in extra.items() if value not in (None, "")}
        destino = reverse(self.list_url_name)
        if params:
            return f"{destino}?{urlencode(params)}"
        return destino

    def get(self, request, *args, **kwargs):
        pk = kwargs.get("pk")
        if pk:
            return redirect(self.list_panel_url(**{self.selection_param: pk}))
        return redirect(self.list_panel_url(nueva=1))

    def redirect_after_save(self):
        if self.request.POST.get("accion") == "seguir":
            return redirect(self.list_panel_url(nueva=1))
        params = {}
        query = self.request.POST.get("q", "").strip()
        if query:
            params["q"] = query
        if self.request.POST.get("desde") == "listado":
            for name, value in filter_values(self.request, filter_specs_for(self)).items():
                params[name] = value
        return redirect(self.list_panel_url(**params))

    def form_valid(self, form):
        self.object = form.save()
        return self.redirect_after_save()

    def form_invalid(self, form):
        listado = self.list_view_class()
        listado.setup(self.request)
        listado.panel_form_override = form
        listado.force_nueva = not getattr(form.instance, "pk", None)
        if getattr(form.instance, "pk", None):
            listado.selected_override = form.instance.pk
        return listado.get(self.request)


class MantenimientoCreateView(
    LoginRequiredMixin, PermisoRequeridoMixin, MantenimientoWriteMixin, CreateView
):
    permiso_accion = "alta"


class MantenimientoUpdateView(
    LoginRequiredMixin, PermisoRequeridoMixin, MantenimientoWriteMixin, UpdateView
):
    permiso_accion = "modificar"


class MantenimientoDeleteView(LoginRequiredMixin, PermisoRequeridoMixin, View):
    permiso_accion = "eliminar"

    def post(self, request, pk):
        obj = get_object_or_404(self.model, pk=pk)
        label = str(obj)
        try:
            obj.delete()
        except RestrictedError:
            messages.error(request, f"{label} está en uso y no se puede eliminar.")
            destino = reverse(self.list_url_name)
            return redirect(f"{destino}?{urlencode({self.selection_param: pk})}")
        return redirect(self.list_url_name)

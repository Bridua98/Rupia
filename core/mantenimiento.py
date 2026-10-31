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

from core.listado import (
    apply_filters,
    apply_search,
    filter_options,
    filter_specs_for,
    filter_values,
    listado_query_params,
    search_fields_for,
)


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
        return headers, rows

    def _salida_context(self):
        headers, rows = self.export_dataset()
        return {
            "title": self.title,
            "query": self.query(),
            "headers": headers,
            "rows": rows,
            "record_count": len(rows),
            "list_url": self.list_query(),
            "generated_at": timezone.localtime().strftime("%d/%m/%Y %H:%M"),
        }

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
    class SalidaView(LoginRequiredMixin, View):
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


class MantenimientoListView(ListadoExportMixin, LoginRequiredMixin, SingleTableView):
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

    def get_table_pagination(self, table):
        if not self.per_page:
            return False
        return {"per_page": self.per_page}

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
                    params["page"] = page
                    return redirect(f"{request.path}?{params.urlencode()}")
        return super().get(request, *args, **kwargs)

    def get_table(self, **kwargs):
        table = super().get_table(**kwargs)
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        nueva = self.creating()
        selected = self.panel_pk()
        panel_form = self._panel_form(nueva, selected)
        panel_object = None
        if panel_form is not None and getattr(panel_form.instance, "pk", None):
            panel_object = panel_form.instance
        context.update(
            {
                "page_title": self.page_title,
                "eyebrow": self.eyebrow,
                "title": self.title,
                "back_url": reverse(self.back_url_name),
                "list_url": reverse(self.list_url_name),
                "create_url": self.list_query(nueva=1),
                "create_label": self.create_label,
                "record_count": self.get_queryset().count(),
                "list_hint": self.list_hint,
                "query": self.query(),
                "search_label": self.search_label,
                "search_placeholder": self.search_placeholder or self.search_label,
                "detail_open": panel_form is not None,
                "panel_form": panel_form,
                "panel_object": panel_object,
                "panel_action": (
                    reverse(self.update_url_name, args=[panel_object.pk])
                    if panel_object
                    else reverse(self.create_url_name)
                ),
                "close_url": self.list_query(),
                "ficha_url": (
                    reverse(self.update_url_name, args=[panel_object.pk]) if panel_object else ""
                ),
                "print_url": self._salida_url(self.print_url_name),
                "export_xlsx_url": self._salida_url(self.export_xlsx_url_name),
                "export_pdf_url": self._salida_url(self.export_pdf_url_name),
            }
        )
        context.update(self._filter_context())
        return context

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
    template_name = "core/ficha.html"

    def form_valid(self, form):
        self.object = form.save()
        if self.request.POST.get("accion") == "seguir":
            return redirect(self.create_url_name)
        params = {}
        query = self.request.POST.get("q", "").strip()
        if query:
            params["q"] = query
        if self.request.POST.get("desde") == "listado":
            for name, value in filter_values(self.request, filter_specs_for(self)).items():
                params[name] = value
        destino = reverse(self.list_url_name)
        if params:
            destino = f"{destino}?{urlencode(params)}"
        return redirect(destino)

    def form_invalid(self, form):
        if self.request.POST.get("desde") != "listado":
            return super().form_invalid(form)
        listado = self.list_view_class()
        listado.setup(self.request)
        listado.panel_form_override = form
        listado.force_nueva = not getattr(form.instance, "pk", None)
        if getattr(form.instance, "pk", None):
            listado.selected_override = form.instance.pk
        return listado.get(self.request)

    def neighbor_context(self, obj):
        ids = list(self.model.objects.order_by(*self.order_by).values_list("pk", flat=True))
        index = ids.index(obj.pk)
        prev_id = ids[index - 1] if index > 0 else None
        next_id = ids[index + 1] if index + 1 < len(ids) else None
        return {
            "position": index + 1,
            "total": len(ids),
            "prev_url": reverse(self.update_url_name, args=[prev_id]) if prev_id else "",
            "next_url": reverse(self.update_url_name, args=[next_id]) if next_id else "",
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = context.get("object")
        context["eyebrow"] = self.eyebrow
        context["create_label"] = self.create_label
        context["record_noun"] = self.record_noun
        if obj is not None:
            context.update(self.neighbor_context(obj))
            context["list_url"] = (
                f"{reverse(self.list_url_name)}?{urlencode({self.selection_param: obj.pk})}"
            )
            context["delete_url"] = reverse(self.delete_url_name, args=[obj.pk])
        else:
            context["list_url"] = reverse(self.list_url_name)
            context["prev_url"] = ""
            context["next_url"] = ""
            context["delete_url"] = ""
        return context


class MantenimientoCreateView(LoginRequiredMixin, MantenimientoWriteMixin, CreateView):
    pass


class MantenimientoUpdateView(LoginRequiredMixin, MantenimientoWriteMixin, UpdateView):
    pass


class MantenimientoDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        obj = get_object_or_404(self.model, pk=pk)
        label = str(obj)
        try:
            obj.delete()
        except RestrictedError:
            messages.error(request, f"{label} está en uso y no se puede eliminar.")
            return redirect(self.update_url_name, pk=pk)
        return redirect(self.list_url_name)

from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordChangeView
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Prefetch
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.html import format_html
from django.views import View

from configuracion.catalogo import FORMULARIOS, matriz_permisos
from configuracion.copia import (
    CopiaError,
    CopiaNoEncontrada,
    crear_copia,
    eliminar_copia,
    listar_copias,
    resolver_copia,
)
from configuracion.forms import (
    CuentaFotoForm,
    PerfilForm,
    RupiaPasswordChangeForm,
    UsuarioClaveForm,
    UsuarioForm,
)
from configuracion.fotos import resolver_foto
from configuracion.models import Perfil, UsuarioFoto
from configuracion.permisos import PermisoRequeridoMixin, exigir_permiso, tiene_permiso
from configuracion.tables import PerfilTable, UsuarioTable
from core.mantenimiento import (
    MantenimientoCreateView,
    MantenimientoDeleteView,
    MantenimientoListView,
    MantenimientoUpdateView,
    MantenimientoWriteMixin,
)
from core.vista import build_view_context

User = get_user_model()


def _proteger_usuario(request, obj):
    if obj.is_superuser and not request.user.is_superuser:
        raise PermissionDenied("No tenés permiso para esta acción.")


class PerfilMantenimiento:
    model = Perfil
    form_class = PerfilForm
    table_class = PerfilTable
    permiso_formulario = "perfiles"
    form_fields_template = "configuracion/perfil_form_fields.html"
    page_title = "Perfiles"
    eyebrow = "Configuración"
    title = "Perfiles"
    create_label = "Nuevo perfil"
    list_hint = "Flechas para moverse. Enter abre el perfil."
    search_label = "Buscar"
    search_placeholder = "Buscar por descripción..."
    search_field = "descripcion"
    selection_param = "perfil"
    record_noun = "perfil"
    order_by = ("descripcion", "pk")
    list_url_name = "perfil_list"
    create_url_name = "perfil_create"
    update_url_name = "perfil_update"
    delete_url_name = "perfil_delete"
    print_url_name = "perfil_print"
    export_xlsx_url_name = "perfil_export_xlsx"
    export_pdf_url_name = "perfil_export_pdf"
    export_basename = "perfiles"
    back_url_name = "home"


class PerfilListView(PerfilMantenimiento, MantenimientoListView):
    def get_queryset(self):
        return super().get_queryset().annotate(_usuarios=Count("usuarios", distinct=True))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context.get("panel_form")
        if form is not None:
            columnas, filas = matriz_permisos(form)
            context["acciones_catalogo"] = columnas
            context["matriz_permisos"] = filas
        return context

    def build_panel_view_context(self, record):
        context = build_view_context(record)
        otorgados = set(record.permisos.values_list("formulario", "accion"))
        filas = []
        for formulario in FORMULARIOS:
            acciones = [
                accion.etiqueta
                for accion in formulario.acciones
                if (formulario.clave, accion.clave) in otorgados
            ]
            if acciones:
                filas.append([formulario.etiqueta, ", ".join(acciones)])
        context["view_tables"] = [
            {
                "title": "Permisos",
                "headers": ["Formulario", "Acciones"],
                "rows": filas,
            }
        ]
        return context


class PerfilCreateView(PerfilMantenimiento, MantenimientoCreateView):
    list_view_class = PerfilListView


class PerfilUpdateView(PerfilMantenimiento, MantenimientoUpdateView):
    list_view_class = PerfilListView


class PerfilDeleteView(PerfilMantenimiento, MantenimientoDeleteView):
    pass


class UsuarioMantenimiento:
    model = User
    form_class = UsuarioForm
    table_class = UsuarioTable
    permiso_formulario = "usuarios"
    form_fields_template = "configuracion/usuario_form_fields.html"
    page_title = "Usuarios"
    eyebrow = "Configuración"
    title = "Usuarios"
    create_label = "Nuevo usuario"
    list_hint = "Flechas para moverse. Enter abre el usuario."
    search_label = "Buscar"
    search_placeholder = "Buscar por usuario, nombre o correo..."
    search_field = "username"
    search_fields = ("username", "first_name", "last_name", "email")
    filters = ({"name": "is_active", "label": "Activo", "kind": "bool"},)
    selection_param = "usuario"
    record_noun = "usuario"
    order_by = ("username", "pk")
    list_url_name = "usuario_list"
    create_url_name = "usuario_create"
    update_url_name = "usuario_update"
    delete_url_name = "usuario_delete"
    print_url_name = "usuario_print"
    export_xlsx_url_name = "usuario_export_xlsx"
    export_pdf_url_name = "usuario_export_pdf"
    export_basename = "usuarios"
    back_url_name = "home"
    view_exclude = ("password", "is_superuser", "is_staff", "last_login", "date_joined")


class UsuarioListView(UsuarioMantenimiento, MantenimientoListView):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .prefetch_related(
                Prefetch("perfiles", queryset=Perfil.objects.order_by("descripcion"))
            )
        )

    def changing_password(self):
        if isinstance(self.panel_form_override, UsuarioClaveForm):
            return True
        if self.request.GET.get("clave") != "1":
            return False
        if not tiene_permiso(self.request.user, "usuarios", "clave"):
            return False
        return self.panel_pk() is not None

    def creating(self):
        if self.changing_password():
            return False
        return super().creating()

    def viewing(self):
        if self.changing_password():
            return False
        return super().viewing()

    def _panel_form(self, nueva, selected):
        if self.changing_password() and selected:
            usuario = self.model.objects.get(pk=selected)
            if self.panel_form_override is not None:
                return self.panel_form_override
            return UsuarioClaveForm(instance=usuario)
        if self.panel_form_override is not None:
            form = self.panel_form_override
        elif nueva:
            form = self.form_class(request_user=self.request.user)
        elif selected:
            form = self.form_class(
                instance=self.model.objects.get(pk=selected),
                request_user=self.request.user,
            )
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
        if self.changing_password() and context.get("panel_object"):
            context["form_fields_template"] = "core/form_fields.html"
            context["panel_action"] = reverse(
                "usuario_password", args=[context["panel_object"].pk]
            )
            context["create_label"] = "Cambiar contraseña"
        return context

    def build_panel_view_context(self, record):
        context = build_view_context(record, exclude=self.view_exclude)
        nombres = [perfil.descripcion for perfil in record.perfiles.all()]
        context["view_fields"].append(
            {
                "label": "Perfiles",
                "value": ", ".join(nombres) if nombres else "—",
            }
        )
        foto = UsuarioFoto.objects.filter(usuario=record).exclude(imagen="").first()
        if foto:
            context["view_fields"].append(
                {
                    "label": "Imagen",
                    "value": format_html(
                        (
                            '<a class="view-imagen-link" href="{}" '
                            'target="_blank" rel="noopener">Ver imagen</a>'
                        ),
                        reverse("usuario_imagen", args=[foto.imagen]),
                    ),
                }
            )
        context["view_tables"] = []
        return context


class UsuarioWriteMixin(MantenimientoWriteMixin):
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request_user"] = self.request.user
        return kwargs


class UsuarioCreateView(UsuarioMantenimiento, UsuarioWriteMixin, MantenimientoCreateView):
    list_view_class = UsuarioListView


class UsuarioUpdateView(UsuarioMantenimiento, UsuarioWriteMixin, MantenimientoUpdateView):
    list_view_class = UsuarioListView

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        _proteger_usuario(self.request, obj)
        return obj


class UsuarioDeleteView(UsuarioMantenimiento, MantenimientoDeleteView):
    def post(self, request, pk):
        obj = get_object_or_404(self.model, pk=pk)
        _proteger_usuario(request, obj)
        if obj.pk == request.user.pk:
            messages.error(request, "No podés eliminar tu propio usuario.")
            destino = reverse(self.list_url_name)
            return redirect(f"{destino}?{self.selection_param}={pk}")
        if obj.is_superuser and User.objects.filter(is_superuser=True).count() <= 1:
            messages.error(request, "No se puede eliminar el último superusuario.")
            destino = reverse(self.list_url_name)
            return redirect(f"{destino}?{self.selection_param}={pk}")
        return super().post(request, pk)


class UsuarioPasswordView(
    UsuarioMantenimiento,
    LoginRequiredMixin,
    PermisoRequeridoMixin,
    MantenimientoWriteMixin,
    View,
):
    permiso_accion = "clave"
    form_class = UsuarioClaveForm
    list_view_class = UsuarioListView

    def get_object(self):
        obj = get_object_or_404(User, pk=self.kwargs["pk"])
        _proteger_usuario(self.request, obj)
        return obj

    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        return redirect(self.list_panel_url(**{self.selection_param: obj.pk, "clave": 1}))

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = UsuarioClaveForm(request.POST, instance=self.object)
        if form.is_valid():
            form.save()
            if self.object.pk == request.user.pk:
                update_session_auth_hash(request, self.object)
            messages.success(request, "La contraseña se actualizó.")
            return redirect(self.list_panel_url())
        listado = self.list_view_class()
        listado.setup(request)
        listado.panel_form_override = form
        listado.selected_override = self.object.pk
        return listado.get(request)


class CambiarContrasenaView(LoginRequiredMixin, PasswordChangeView):
    form_class = RupiaPasswordChangeForm
    template_name = "configuracion/contrasena.html"
    success_url = reverse_lazy("home")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("foto_form", CuentaFotoForm(instance=self.request.user))
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get("accion") == "foto":
            foto_form = CuentaFotoForm(request.POST, request.FILES, instance=request.user)
            if foto_form.is_valid():
                foto_form.save()
                messages.success(request, "Tu imagen se actualizó.")
                return redirect("cambiar_contrasena")
            return self.render_to_response(
                self.get_context_data(
                    form=self.form_class(user=request.user),
                    foto_form=foto_form,
                )
            )
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Tu contraseña se actualizó.")
        return super().form_valid(form)


class CopiaListView(PermisoRequeridoMixin, View):
    permiso_formulario = "copias"
    permiso_accion = "ver"

    def get(self, request):
        return render(request, "configuracion/copias.html", self._contexto(request))

    def post(self, request):
        if request.POST.get("accion") == "eliminar":
            exigir_permiso(request.user, "copias", "eliminar")
            try:
                eliminar_copia(request.POST.get("nombre", ""))
            except CopiaNoEncontrada:
                messages.error(request, "Esa copia ya no está almacenada.")
            else:
                messages.success(request, "Se eliminó la copia de seguridad.")
            return redirect("copia_list")
        exigir_permiso(request.user, "copias", "alta")
        try:
            copia = crear_copia()
        except CopiaError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Se almacenó la copia {copia.nombre}.")
        return redirect("copia_list")

    def _contexto(self, request):
        return {
            "copias": listar_copias(),
            "puede_crear": tiene_permiso(request.user, "copias", "alta"),
            "puede_eliminar": tiene_permiso(request.user, "copias", "eliminar"),
        }


class CopiaDescargaView(PermisoRequeridoMixin, View):
    permiso_formulario = "copias"
    permiso_accion = "ver"

    def get(self, request, nombre):
        try:
            destino = resolver_copia(nombre)
        except CopiaNoEncontrada as exc:
            raise Http404 from exc
        return FileResponse(destino.open("rb"), as_attachment=True, filename=destino.name)


class UsuarioImagenView(LoginRequiredMixin, View):
    def get(self, request, nombre):
        destino = resolver_foto(nombre)
        if destino is None:
            raise Http404
        return FileResponse(destino.open("rb"))

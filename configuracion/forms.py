from pathlib import Path

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q

from configuracion.catalogo import FORMULARIOS, campo_permiso, pares_permiso
from configuracion.fotos import EXTENSIONES, aplicar_foto, url_foto
from configuracion.models import Perfil, PerfilPermiso, UsuarioFoto
from core.forms import RupiaModelForm

User = get_user_model()


class ImagenInput(forms.FileInput):
    is_imagen = True

    def __init__(self, attrs=None, preview_url=""):
        self.preview_url = preview_url
        base = {
            "accept": "image/jpeg,image/png,image/webp,image/gif",
            "data-imagen-input": True,
        }
        if attrs:
            base.update(attrs)
        super().__init__(attrs=base)


def _validar_imagen(archivo):
    if not archivo:
        return None
    suffix = Path(archivo.name).suffix.lower()
    if suffix not in EXTENSIONES:
        raise ValidationError("La imagen tiene que ser JPG, PNG, WEBP o GIF.")
    return archivo


def _campos_foto():
    return {
        "imagen_archivo": forms.ImageField(
            label="Imagen",
            required=False,
            error_messages={"invalid_image": "Elegí un archivo de imagen."},
            widget=ImagenInput(),
        ),
        "quitar_imagen": forms.BooleanField(label="Quitar imagen", required=False),
    }


def _configurar_campos_foto(form, usuario):
    for nombre, campo in _campos_foto().items():
        if nombre not in form.fields:
            form.fields[nombre] = campo
    foto = None
    if getattr(usuario, "pk", None):
        foto = UsuarioFoto.objects.filter(usuario=usuario).first()
    if not foto or not foto.imagen:
        form.fields.pop("quitar_imagen", None)
        return
    preview = url_foto(usuario)
    if preview:
        form.fields["imagen_archivo"].widget.preview_url = preview


def _clave_widget(autocomplete):
    return forms.PasswordInput(
        attrs={
            "placeholder": " ",
            "autocomplete": autocomplete,
        }
    )


class PerfilForm(RupiaModelForm):
    class Meta:
        model = Perfil
        fields = ["descripcion", "activo"]
        widgets = {
            "descripcion": forms.TextInput(
                attrs={"autofocus": True, "autocomplete": "off", "maxlength": "200"}
            ),
        }
        error_messages = {
            "descripcion": {
                "required": "Escribí la descripción.",
                "unique": "Ya hay un perfil con esa descripción.",
                "max_length": "La descripción admite hasta 200 caracteres.",
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        actuales = set()
        if self.instance.pk:
            actuales = set(self.instance.permisos.values_list("formulario", "accion"))
        for formulario in FORMULARIOS:
            for accion in formulario.acciones:
                name = campo_permiso(formulario.clave, accion.clave)
                field = forms.BooleanField(required=False, label=accion.etiqueta)
                self.fields[name] = field
                if not self.is_bound:
                    field.initial = (formulario.clave, accion.clave) in actuales

    def save(self, commit=True):
        perfil = super().save(commit=commit)
        if commit:
            self._guardar_permisos(perfil)
        return perfil

    def _guardar_permisos(self, perfil):
        deseados = {
            (formulario, accion)
            for formulario, accion in pares_permiso()
            if self.cleaned_data.get(campo_permiso(formulario, accion))
        }
        actuales = set(perfil.permisos.values_list("formulario", "accion"))
        a_borrar = actuales - deseados
        if a_borrar:
            q = Q()
            for formulario, accion in a_borrar:
                q |= Q(formulario=formulario, accion=accion)
            perfil.permisos.filter(q).delete()
        faltantes = [
            PerfilPermiso(perfil=perfil, formulario=formulario, accion=accion)
            for formulario, accion in deseados - actuales
        ]
        if faltantes:
            PerfilPermiso.objects.bulk_create(faltantes)


class UsuarioForm(RupiaModelForm):
    password1 = forms.CharField(
        label="Contraseña",
        required=False,
        widget=_clave_widget("new-password"),
        error_messages={"required": "Escribí la contraseña."},
    )
    password2 = forms.CharField(
        label="Repetí la contraseña",
        required=False,
        widget=_clave_widget("new-password"),
        error_messages={"required": "Repetí la contraseña."},
    )
    perfiles = forms.ModelMultipleChoiceField(
        label="Perfiles",
        queryset=Perfil.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "is_active",
        ]
        labels = {
            "username": "Usuario",
            "first_name": "Nombre",
            "last_name": "Apellido",
            "email": "Correo",
            "is_active": "Activo",
        }
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "autofocus": True,
                    "autocomplete": "off",
                    "autocapitalize": "none",
                    "spellcheck": "false",
                }
            ),
            "email": forms.EmailInput(attrs={"autocomplete": "off"}),
        }
        error_messages = {
            "username": {
                "required": "Escribí el usuario.",
                "unique": "Ya hay un usuario con ese nombre.",
            },
            "email": {"invalid": "Escribí un correo válido."},
        }

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop("request_user", None)
        super().__init__(*args, **kwargs)
        perfiles = Perfil.objects.order_by("descripcion")
        if self.instance.pk:
            perfiles = Perfil.objects.filter(
                Q(activo=True) | Q(pk__in=self.instance.perfiles.values("pk"))
            ).order_by("descripcion")
        else:
            perfiles = Perfil.objects.filter(activo=True).order_by("descripcion")
        self.fields["perfiles"].queryset = perfiles
        if not self.instance.pk:
            self.fields["password1"].required = True
            self.fields["password2"].required = True
        else:
            self.fields.pop("password1")
            self.fields.pop("password2")
        if (
            self.instance.pk
            and self.request_user
            and self.instance.pk == self.request_user.pk
        ):
            self.fields["is_active"].disabled = True
        _configurar_campos_foto(self, self.instance)

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.exclude(pk=self.instance.pk).filter(username=username).exists():
            raise forms.ValidationError("Ya hay un usuario con ese nombre.")
        return username

    def clean_is_active(self):
        activo = self.cleaned_data.get("is_active")
        if (
            self.instance.pk
            and self.request_user
            and self.instance.pk == self.request_user.pk
            and not activo
        ):
            raise forms.ValidationError("No podés desactivar tu propio usuario.")
        return activo

    def clean(self):
        cleaned = super().clean()
        if "password1" not in self.fields:
            return cleaned
        password1 = cleaned.get("password1") or ""
        password2 = cleaned.get("password2") or ""
        if password1 or password2:
            if password1 != password2:
                self.add_error("password2", "Las contraseñas no coinciden.")
            elif password1:
                try:
                    usuario = self.instance if self.instance.pk else User(
                        username=cleaned.get("username")
                    )
                    validate_password(password1, usuario)
                except ValidationError as exc:
                    self.add_error("password1", exc)
        return cleaned

    def clean_imagen_archivo(self):
        return _validar_imagen(self.cleaned_data.get("imagen_archivo"))

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password1")
        if password:
            user.set_password(password)
        if commit:
            user.save()
            user.perfiles.set(self.cleaned_data.get("perfiles") or [])
            aplicar_foto(
                user,
                archivo=self.cleaned_data.get("imagen_archivo"),
                quitar=self.cleaned_data.get("quitar_imagen"),
            )
        return user


class UsuarioClaveForm(forms.Form):
    password1 = forms.CharField(
        label="Contraseña nueva",
        widget=_clave_widget("new-password"),
        error_messages={"required": "Escribí la contraseña."},
    )
    password2 = forms.CharField(
        label="Repetí la contraseña",
        widget=_clave_widget("new-password"),
        error_messages={"required": "Repetí la contraseña."},
    )

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("placeholder", " ")

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1") or ""
        password2 = cleaned.get("password2") or ""
        if password1 != password2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        elif password1:
            try:
                validate_password(password1, self.instance)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    def save(self):
        self.instance.set_password(self.cleaned_data["password1"])
        self.instance.save(update_fields=["password"])
        return self.instance


class CuentaFotoForm(forms.Form):
    imagen_archivo = forms.ImageField(
        label="Imagen",
        required=False,
        error_messages={"invalid_image": "Elegí un archivo de imagen."},
        widget=ImagenInput(),
    )
    quitar_imagen = forms.BooleanField(label="Quitar imagen", required=False)

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        super().__init__(*args, **kwargs)
        _configurar_campos_foto(self, instance)

    def clean_imagen_archivo(self):
        return _validar_imagen(self.cleaned_data.get("imagen_archivo"))

    def save(self):
        aplicar_foto(
            self.instance,
            archivo=self.cleaned_data.get("imagen_archivo"),
            quitar=self.cleaned_data.get("quitar_imagen"),
        )
        return self.instance


class RupiaPasswordChangeForm(PasswordChangeForm):
    error_messages = {
        **PasswordChangeForm.error_messages,
        "password_incorrect": "La contraseña actual no coincide.",
        "password_mismatch": "Las contraseñas no coinciden.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Contraseña actual"
        self.fields["old_password"].widget.attrs.update(
            {"placeholder": " ", "autocomplete": "current-password"}
        )
        self.fields["new_password1"].label = "Contraseña nueva"
        self.fields["new_password1"].widget.attrs.update(
            {"placeholder": " ", "autocomplete": "new-password"}
        )
        self.fields["new_password2"].label = "Repetí la contraseña"
        self.fields["new_password2"].widget.attrs.update(
            {"placeholder": " ", "autocomplete": "new-password"}
        )

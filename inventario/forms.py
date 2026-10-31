from pathlib import Path

from django import forms
from django.core.exceptions import ValidationError
from django.urls import reverse

from core.forms import RupiaModelForm
from core.moneda import MonedaField
from core.selectors import SelectorAlta, registrar
from inventario.imagenes import EXTENSIONES, guardar_imagen, liberar_imagen, resolver_imagen
from inventario.models import Item, ItemCategoria, Marca, TasaIva, TipoItem, UnidadMedida


class MarcaForm(RupiaModelForm):
    descripcion = forms.CharField(
        label="Descripción",
        max_length=200,
        error_messages={
            "required": "Escribí la descripción.",
            "unique": "Ya hay una marca con esa descripción.",
        },
        widget=forms.TextInput(
            attrs={
                "placeholder": " ",
                "autocomplete": "off",
                "autofocus": True,
                "maxlength": "200",
            }
        ),
    )

    class Meta:
        model = Marca
        fields = ["descripcion"]


class CategoriaForm(RupiaModelForm):
    descripcion = forms.CharField(
        label="Descripción",
        max_length=300,
        error_messages={
            "required": "Escribí la descripción.",
            "unique": "Ya hay una categoría con esa descripción.",
        },
        widget=forms.TextInput(
            attrs={
                "placeholder": " ",
                "autocomplete": "off",
                "autofocus": True,
                "maxlength": "300",
            }
        ),
    )

    class Meta:
        model = ItemCategoria
        fields = ["descripcion"]


class UnidadForm(RupiaModelForm):
    descripcion = forms.CharField(
        label="Descripción",
        max_length=100,
        error_messages={
            "required": "Escribí la descripción.",
            "unique": "Ya hay una unidad con esa descripción.",
        },
        widget=forms.TextInput(
            attrs={
                "placeholder": " ",
                "autocomplete": "off",
                "autofocus": True,
                "maxlength": "100",
            }
        ),
    )
    simbolo = forms.CharField(
        label="Símbolo",
        max_length=10,
        error_messages={
            "required": "Escribí el símbolo.",
            "unique": "Ya hay una unidad con ese símbolo.",
        },
        widget=forms.TextInput(
            attrs={
                "placeholder": " ",
                "autocomplete": "off",
                "maxlength": "10",
            }
        ),
    )

    class Meta:
        model = UnidadMedida
        fields = ["descripcion", "simbolo"]


registrar(
    "marca",
    queryset=lambda: Marca.objects.order_by("descripcion"),
    form=MarcaForm,
    search_fields=("descripcion",),
    create_label="Nueva marca",
)
registrar(
    "categoria",
    queryset=lambda: ItemCategoria.objects.order_by("descripcion"),
    form=CategoriaForm,
    search_fields=("descripcion",),
    create_label="Nueva categoría",
)
registrar(
    "unidad",
    queryset=lambda: UnidadMedida.objects.order_by("descripcion"),
    form=UnidadForm,
    search_fields=("descripcion", "simbolo"),
    create_label="Nueva unidad",
)


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


class ItemForm(RupiaModelForm):
    descripcion = forms.CharField(
        label="Descripción",
        max_length=300,
        error_messages={
            "required": "Escribí la descripción.",
            "unique": "Ya hay un ítem con esa descripción.",
        },
        widget=forms.TextInput(
            attrs={
                "placeholder": " ",
                "autocomplete": "off",
                "autofocus": True,
                "maxlength": "300",
            }
        ),
    )
    tipo = forms.ChoiceField(
        label="Tipo",
        choices=TipoItem.choices,
        initial=TipoItem.PRODUCTO,
        widget=forms.Select(),
    )
    marca = SelectorAlta(clave="marca", label="Marca", required_message="Elegí una marca.")
    categoria = SelectorAlta(
        clave="categoria",
        label="Categoría",
        required_message="Elegí una categoría.",
    )
    unidad_medida = SelectorAlta(
        clave="unidad",
        label="Unidad de medida",
        required_message="Elegí una unidad.",
    )
    codigo_barra = forms.CharField(
        label="Código de barra",
        max_length=300,
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": " ",
                "autocomplete": "off",
                "maxlength": "300",
            }
        ),
    )
    precio = MonedaField(label="Precio", required=False)
    tasa_iva = forms.TypedChoiceField(
        label="Tasa IVA",
        choices=TasaIva.choices,
        coerce=int,
        initial=TasaIva.DIEZ,
        widget=forms.Select(),
        error_messages={
            "required": "Elegí la tasa de IVA.",
            "invalid_choice": "Elegí una tasa de IVA válida.",
        },
    )
    activo = forms.BooleanField(label="Activo", required=False, initial=True)
    imagen_archivo = forms.ImageField(
        label="Imagen",
        required=False,
        error_messages={"invalid_image": "Elegí un archivo de imagen."},
        widget=ImagenInput(),
    )
    quitar_imagen = forms.BooleanField(label="Quitar imagen", required=False)

    class Meta:
        model = Item
        fields = [
            "codigo_barra",
            "descripcion",
            "tipo",
            "marca",
            "categoria",
            "unidad_medida",
            "precio",
            "tasa_iva",
            "activo",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        nuevo = not getattr(self.instance, "pk", None)
        if nuevo:
            self.fields["descripcion"].widget = forms.Textarea(
                attrs={
                    "placeholder": " ",
                    "autocomplete": "off",
                    "maxlength": "300",
                    "rows": "4",
                }
            )
            self.fields["codigo_barra"].widget.attrs["autofocus"] = True
        if not self.instance.imagen:
            self.fields.pop("quitar_imagen", None)
        else:
            destino = resolver_imagen(self.instance.imagen)
            if destino is not None:
                self.fields["imagen_archivo"].widget.preview_url = reverse(
                    "item_imagen",
                    kwargs={"nombre": self.instance.imagen},
                )
        orden = [
            "codigo_barra",
            "descripcion",
            "tipo",
            "marca",
            "categoria",
            "unidad_medida",
            "precio",
            "tasa_iva",
            "activo",
            "imagen_archivo",
        ]
        if "quitar_imagen" in self.fields:
            orden.append("quitar_imagen")
        self.order_fields(orden)

    def clean_imagen_archivo(self):
        archivo = self.cleaned_data.get("imagen_archivo")
        if not archivo:
            return archivo
        suffix = Path(archivo.name).suffix.lower()
        if suffix not in EXTENSIONES:
            raise ValidationError("La imagen tiene que ser JPG, PNG, WEBP o GIF.")
        return archivo

    def save(self, commit=True):
        anterior = self.instance.imagen if self.instance.pk else ""
        instance = super().save(commit=False)
        archivo = self.cleaned_data.get("imagen_archivo")
        if archivo:
            instance.imagen = guardar_imagen(archivo, excluir_pk=instance.pk)
        elif self.cleaned_data.get("quitar_imagen"):
            instance.imagen = None
        if commit:
            instance.save()
            self.save_m2m()
            if anterior and anterior != (instance.imagen or ""):
                liberar_imagen(anterior, instance.pk)
        return instance

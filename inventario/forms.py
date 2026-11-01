from decimal import Decimal
from pathlib import Path

from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.urls import reverse

from core.cantidad import CantidadField
from core.forms import RupiaModelForm
from core.moneda import MonedaField
from core.selectors import SelectorAlta, registrar
from inventario.imagenes import EXTENSIONES, guardar_imagen, liberar_imagen, resolver_imagen
from inventario.models import (
    Item,
    ItemCategoria,
    ItemUnidad,
    Marca,
    RelacionUnidad,
    TasaIva,
    TipoItem,
    UnidadMedida,
)
from inventario.precios import registrar_cambio_ficha


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
    precio_segun_costo = forms.BooleanField(
        label="Modificar precio según último costo",
        required=False,
        initial=False,
    )
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
            "precio_segun_costo",
            "tasa_iva",
            "activo",
        ]

    def __init__(self, *args, usuario=None, **kwargs):
        self.usuario = usuario
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
            "precio_segun_costo",
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
        existia = bool(self.instance.pk)
        precio_anterior = None
        if existia:
            precio_anterior = (
                Item.objects.filter(pk=self.instance.pk).values_list("precio", flat=True).first()
            )
        anterior = self.instance.imagen if existia else ""
        instance = super().save(commit=False)
        archivo = self.cleaned_data.get("imagen_archivo")
        if archivo:
            instance.imagen = guardar_imagen(archivo, excluir_pk=instance.pk)
        elif self.cleaned_data.get("quitar_imagen"):
            instance.imagen = None
        if commit:
            instance.save()
            self.save_m2m()
            registrar_cambio_ficha(instance, precio_anterior, self.usuario)
            if anterior and anterior != (instance.imagen or ""):
                liberar_imagen(anterior, instance.pk)
        return instance


class PorcentajeField(forms.DecimalField):
    def to_python(self, value):
        if isinstance(value, str):
            value = value.strip().replace("%", "").replace(",", ".")
        return super().to_python(value)

    def prepare_value(self, value):
        preparado = super().prepare_value(value)
        if preparado in (None, ""):
            return ""
        texto = str(preparado)
        if texto.endswith(".00"):
            texto = texto[:-3]
        elif texto.endswith("0") and "." in texto:
            texto = texto[:-1]
        return texto.replace(".", ",")


class PrecioAjusteForm(forms.Form):
    use_required_attribute = False
    porcentaje = PorcentajeField(
        label="Porcentaje",
        max_digits=6,
        decimal_places=2,
        min_value=Decimal("-99.99"),
        error_messages={
            "required": "Escribí el porcentaje.",
            "invalid": "Escribí un porcentaje.",
            "min_value": "El porcentaje tiene que ser mayor a -100.",
            "max_digits": "El porcentaje admite hasta 4 enteros y 2 decimales.",
        },
        widget=forms.TextInput(
            attrs={
                "placeholder": "0",
                "inputmode": "decimal",
                "autocomplete": "off",
            }
        ),
    )
    todos_filtrados = forms.BooleanField(label="Todos los filtrados", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["porcentaje"].widget.attrs.setdefault("id", "id_porcentaje")


class ItemUnidadForm(RupiaModelForm):
    unidad_medida = SelectorAlta(
        clave="unidad",
        label="Unidad",
        required_message="Elegí una unidad.",
        required=False,
    )
    relacion = forms.ChoiceField(
        label="Relación",
        choices=[("", "Relación"), *RelacionUnidad.choices],
        required=False,
        widget=forms.Select(),
        error_messages={"invalid_choice": "Elegí si es menor o mayor."},
    )
    valor = CantidadField(
        label="Valor",
        required=False,
        max_digits=15,
        decimal_places=3,
        min_value=Decimal("0.001"),
        error_messages={
            "invalid": "Escribí el valor.",
            "min_value": "El valor tiene que ser mayor a 0.",
        },
    )

    class Meta:
        model = ItemUnidad
        fields = ["unidad_medida", "relacion", "valor"]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("DELETE"):
            return cleaned
        unidad = cleaned.get("unidad_medida")
        relacion = cleaned.get("relacion")
        valor = cleaned.get("valor")
        if not unidad and not relacion and valor is None:
            return cleaned
        if not unidad:
            self.add_error("unidad_medida", "Elegí una unidad.")
        if not relacion:
            self.add_error("relacion", "Elegí si es menor o mayor.")
        if valor is None:
            self.add_error("valor", "Escribí el valor.")
        return cleaned


class ItemUnidadFormSetBase(forms.BaseInlineFormSet):
    def __init__(self, *args, unidad_base=None, **kwargs):
        self.unidad_base = unidad_base
        super().__init__(*args, **kwargs)

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        vistas = set()
        base_id = None
        if self.unidad_base is not None:
            base_id = getattr(self.unidad_base, "pk", self.unidad_base)
        elif getattr(self.instance, "unidad_medida_id", None):
            base_id = self.instance.unidad_medida_id
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            cleaned = form.cleaned_data
            if not cleaned or cleaned.get("DELETE"):
                continue
            unidad = cleaned.get("unidad_medida")
            if unidad is None:
                continue
            if base_id and unidad.pk == base_id:
                form.add_error("unidad_medida", "Esa es la unidad del ítem.")
            if unidad.pk in vistas:
                form.add_error("unidad_medida", "Ya está relacionada.")
            vistas.add(unidad.pk)


ItemUnidadFormSet = inlineformset_factory(
    Item,
    ItemUnidad,
    form=ItemUnidadForm,
    formset=ItemUnidadFormSetBase,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


def unidades_formset(*, item=None, data=None, unidad_base=None):
    return ItemUnidadFormSet(
        data=data,
        instance=item if item is not None else Item(),
        prefix="unidades",
        unidad_base=unidad_base,
    )

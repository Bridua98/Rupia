from decimal import Decimal
from pathlib import Path

from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.urls import reverse
from django.utils import timezone

from core.cantidad import CantidadField
from core.forms import RupiaModelForm
from core.moneda import MonedaField
from core.selectors import SelectorAlta, registrar
from inventario.defecto import asegurar_referenciales_defecto
from inventario.imagenes import EXTENSIONES, guardar_imagen, liberar_imagen, resolver_imagen
from inventario.models import (
    AjusteStock,
    AjusteStockDetalle,
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
from inventario.stock import cantidad_en_unidad, stock_actual
from negocio.forms import UnidadNegocioForm  # noqa: F401


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
    formulario="marcas",
)
registrar(
    "categoria",
    queryset=lambda: ItemCategoria.objects.order_by("descripcion"),
    form=CategoriaForm,
    search_fields=("descripcion",),
    create_label="Nueva categoría",
    formulario="categorias",
)
registrar(
    "unidad",
    queryset=lambda: UnidadMedida.objects.order_by("descripcion"),
    form=UnidadForm,
    search_fields=("descripcion", "simbolo"),
    create_label="Nueva unidad",
    formulario="unidades",
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
        widget=forms.Textarea(
            attrs={
                "placeholder": "Ej: Mouse inalámbrico",
                "autocomplete": "off",
                "autofocus": True,
                "maxlength": "300",
                "rows": "5",
            }
        ),
    )
    tipo = forms.ChoiceField(
        label="Tipo",
        choices=TipoItem.choices,
        initial=TipoItem.PRODUCTO,
        widget=forms.Select(),
    )
    unidad_negocio = SelectorAlta(
        clave="unidad_negocio",
        label="Unidad de negocio",
        required_message="Elegí una unidad de negocio.",
        required=False,
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
                "placeholder": "Ej: ITM-001",
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
            "unidad_negocio",
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
            self.fields["descripcion"].widget.attrs.pop("autofocus", None)
            self.fields["codigo_barra"].widget.attrs.pop("autofocus", None)
            self.fields["tipo"].widget.attrs["autofocus"] = True
        tipo = None
        if self.is_bound:
            tipo = self.data.get(self.add_prefix("tipo"))
        elif getattr(self.instance, "tipo", None):
            tipo = self.instance.tipo
        if tipo == TipoItem.GASTO:
            for nombre in ("marca", "categoria", "unidad_medida"):
                self.fields[nombre].required = False
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
            "tipo",
            "unidad_negocio",
            "descripcion",
            "codigo_barra",
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

    def _es_gasto(self):
        tipo = self.cleaned_data.get("tipo") or self.data.get(self.add_prefix("tipo"))
        return tipo == TipoItem.GASTO

    def clean_imagen_archivo(self):
        archivo = self.cleaned_data.get("imagen_archivo")
        if self._es_gasto() or not archivo:
            return None
        suffix = Path(archivo.name).suffix.lower()
        if suffix not in EXTENSIONES:
            raise ValidationError("La imagen tiene que ser JPG, PNG, WEBP o GIF.")
        return archivo

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("tipo") != TipoItem.GASTO:
            return cleaned
        refs = asegurar_referenciales_defecto()
        for nombre in ("marca", "categoria", "unidad_medida"):
            if not cleaned.get(nombre):
                cleaned[nombre] = refs[nombre]
        cleaned["codigo_barra"] = None
        cleaned["precio"] = None
        cleaned["precio_segun_costo"] = False
        cleaned["imagen_archivo"] = None
        return cleaned

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


class AjusteStockForm(RupiaModelForm):
    fecha = forms.DateField(
        label="Fecha",
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"type": "date"}),
        error_messages={
            "required": "Elegí la fecha.",
            "invalid": "Elegí una fecha válida.",
        },
    )
    observacion = forms.CharField(
        label="Observación",
        max_length=45,
        error_messages={"required": "Escribí el motivo del ajuste."},
        widget=forms.TextInput(
            attrs={
                "placeholder": " ",
                "autocomplete": "off",
                "autofocus": True,
                "maxlength": "45",
            }
        ),
    )

    class Meta:
        model = AjusteStock
        fields = ["fecha", "observacion"]

    def clean_fecha(self):
        fecha = self.cleaned_data["fecha"]
        if fecha > timezone.localdate():
            raise ValidationError("La fecha no puede ser futura.", code="fecha")
        return fecha


class ItemProductoField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.descripcion} · {obj.unidad_medida.simbolo}"


class AjusteStockDetalleForm(RupiaModelForm):
    item = ItemProductoField(
        label="Ítem",
        queryset=Item.objects.none(),
        empty_label="Elegí un producto",
        error_messages={
            "required": "Elegí un producto.",
            "invalid_choice": "Elegí un producto activo.",
        },
        widget=forms.Select(attrs={"data-ajuste-item": True}),
    )
    unidad_medida = forms.ModelChoiceField(
        label="Unidad",
        queryset=UnidadMedida.objects.none(),
        empty_label="Elegí una unidad",
        error_messages={
            "required": "Elegí una unidad.",
            "invalid_choice": "Esa unidad no está relacionada con el ítem.",
        },
        widget=forms.Select(attrs={"data-ajuste-unidad": True}),
    )
    cantidad_nueva = CantidadField(
        label="Cantidad nueva",
        min_value=Decimal("0"),
        error_messages={
            "required": "Escribí la cantidad nueva.",
            "invalid": "Escribí una cantidad nueva válida.",
            "min_value": "La cantidad nueva no puede ser negativa.",
        },
    )

    class Meta:
        model = AjusteStockDetalle
        fields = ["item", "unidad_medida", "cantidad_nueva"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aviso = ""
        self.fields["item"].queryset = (
            Item.objects.filter(tipo=TipoItem.PRODUCTO, activo=True)
            .select_related("unidad_medida")
            .order_by("descripcion")
        )
        item = self._item()
        if item is not None:
            unidades = self._unidades(item)
        else:
            unidades = UnidadMedida.objects.order_by("descripcion")
        self.fields["unidad_medida"].queryset = unidades
        if not self.is_bound:
            self._preparar_stock(item)

    def _item(self):
        if self.is_bound:
            raw = self.data.get(self.add_prefix("item"))
            if raw and str(raw).isdigit():
                return Item.objects.filter(pk=raw).select_related("unidad_medida").first()
            return None
        if self.instance.pk and self.instance.item_id:
            return self.instance.item
        return None

    def _unidades(self, item):
        ids = [item.unidad_medida_id]
        ids.extend(item.unidades.values_list("unidad_medida_id", flat=True))
        return UnidadMedida.objects.filter(pk__in=ids).order_by("descripcion")

    def _preparar_stock(self, item):
        if self.instance.cantidad_anterior is None:
            self.instance.cantidad_anterior = Decimal("0")
        if self.instance.cantidad is None:
            self.instance.cantidad = Decimal("0")
        if item is None or not self.instance.pk:
            return
        try:
            anterior_base, omitidos = stock_actual(
                item,
                excluir_ajuste_id=self.instance.ajuste_id,
            )
            anterior = cantidad_en_unidad(item, self.instance.unidad_medida, anterior_base)
        except ValidationError as exc:
            self.aviso = exc.messages[0]
            return
        self.instance.cantidad_anterior = anterior
        self.instance.cantidad = self.instance.cantidad_nueva - anterior
        if omitidos:
            self.aviso = (
                "Hay movimientos con unidades no relacionadas; no entraron en el stock anterior."
            )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("DELETE"):
            return cleaned
        item = cleaned.get("item")
        unidad = cleaned.get("unidad_medida")
        nueva = cleaned.get("cantidad_nueva")
        if item is None or unidad is None or nueva is None:
            return cleaned
        if item.tipo != TipoItem.PRODUCTO or not item.activo:
            self.add_error("item", "Elegí un producto activo.")
            return cleaned
        permitidas = {item.unidad_medida_id}
        permitidas.update(item.unidades.values_list("unidad_medida_id", flat=True))
        if unidad.pk not in permitidas:
            self.add_error("unidad_medida", "Esa unidad no está relacionada con el ítem.")
            return cleaned
        try:
            anterior_base, omitidos = stock_actual(
                item,
                excluir_ajuste_id=self.instance.ajuste_id,
            )
            anterior = cantidad_en_unidad(item, unidad, anterior_base)
        except ValidationError as exc:
            self.add_error("unidad_medida", exc.messages[0])
            return cleaned
        self.instance.cantidad_anterior = anterior
        self.instance.cantidad = nueva - anterior
        self.aviso = (
            "Hay movimientos con unidades no relacionadas; no entraron en el stock anterior."
            if omitidos
            else ""
        )
        return cleaned


class AjusteStockDetalleFormSetBase(forms.BaseInlineFormSet):
    default_error_messages = {
        "too_few_forms": "Agregá al menos un ítem al ajuste.",
    }

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        vistos = set()
        for form in self.forms:
            cleaned = getattr(form, "cleaned_data", None)
            if not cleaned or cleaned.get("DELETE"):
                continue
            item = cleaned.get("item")
            if item is None:
                continue
            if item.pk in vistos:
                form.add_error("item", "Ese ítem ya está en el ajuste.")
            vistos.add(item.pk)
        if not vistos:
            raise ValidationError("Agregá al menos un ítem al ajuste.")


AjusteStockDetalleFormSet = inlineformset_factory(
    AjusteStock,
    AjusteStockDetalle,
    form=AjusteStockDetalleForm,
    formset=AjusteStockDetalleFormSetBase,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


def ajuste_stock_formset(*, ajuste=None, data=None):
    return AjusteStockDetalleFormSet(
        data=data,
        instance=ajuste if ajuste is not None else AjusteStock(),
        prefix="detalles",
    )

from django import forms

from core.forms import RupiaModelForm
from core.selectors import SelectorAlta, registrar
from inventario.models import Item, ItemCategoria, Marca, TipoItem, UnidadMedida


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
    precio = forms.DecimalField(
        label="Precio",
        max_digits=15,
        decimal_places=3,
        required=False,
        localize=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": " ",
                "autocomplete": "off",
                "inputmode": "decimal",
            }
        ),
    )
    activo = forms.BooleanField(label="Activo", required=False)

    class Meta:
        model = Item
        fields = [
            "descripcion",
            "tipo",
            "marca",
            "categoria",
            "unidad_medida",
            "codigo_barra",
            "precio",
            "activo",
        ]

from django import forms
from django.db import transaction

from core.combo import ComboChoiceField
from core.forms import RupiaModelForm
from core.selectors import registrar
from inventario.models import Item, ItemCategoria
from mesas.models import Mesa, Sector, SectorCategoria, SectorItem


class CategoriasSectorField(forms.ModelMultipleChoiceField):
    """Muestra a qué otro sector va cada categoría, para no pisarla sin querer."""

    def __init__(self, *args, sector=None, **kwargs):
        self.sector = sector
        super().__init__(*args, **kwargs)

    def label_from_instance(self, obj):
        actual = getattr(obj, "sector_actual", None)
        if actual and (self.sector is None or actual.pk != self.sector.pk):
            return f"{obj.descripcion} (va a {actual.nombre})"
        return obj.descripcion


class SectorForm(RupiaModelForm):
    categorias = CategoriasSectorField(
        label="Categorías que se preparan acá",
        queryset=ItemCategoria.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Sector
        fields = ["nombre", "activo", "exige_empezar", "minutos_demora"]
        labels = {
            "nombre": "Nombre",
            "activo": "Activo",
            "exige_empezar": "Pide empezar",
            "minutos_demora": "Minutos de demora",
        }
        widgets = {
            "nombre": forms.TextInput(
                attrs={"autofocus": True, "autocomplete": "off", "maxlength": "80"}
            ),
        }
        error_messages = {
            "nombre": {
                "required": "Escribí el nombre del sector.",
                "unique": "Ya hay un sector con ese nombre.",
                "max_length": "El nombre admite hasta 80 caracteres.",
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        sector = self.instance if self.instance.pk else None
        asignadas = {
            fila.categoria_id: fila.sector
            for fila in SectorCategoria.objects.select_related("sector")
        }
        categorias = list(ItemCategoria.objects.order_by("descripcion"))
        for categoria in categorias:
            categoria.sector_actual = asignadas.get(categoria.pk)
        campo = self.fields["categorias"]
        campo.sector = sector
        campo.queryset = ItemCategoria.objects.order_by("descripcion")
        # Las etiquetas salen de las instancias ya anotadas.
        campo.choices = [(c.pk, campo.label_from_instance(c)) for c in categorias]
        self.fields["minutos_demora"].required = False
        self._asignadas = asignadas
        if sector is not None and not self.is_bound:
            self.initial["categorias"] = [
                pk for pk, dueno in asignadas.items() if dueno.pk == sector.pk
            ]

    def clean_nombre(self):
        nombre = (self.cleaned_data.get("nombre") or "").strip()
        if not nombre:
            raise forms.ValidationError("Escribí el nombre del sector.")
        return nombre

    def clean_minutos_demora(self):
        minutos = self.cleaned_data.get("minutos_demora")
        if minutos in (None, ""):
            return 15
        if minutos < 1:
            raise forms.ValidationError("Los minutos de demora tienen que ser 1 o más.")
        return minutos

    def clean_categorias(self):
        elegidas = self.cleaned_data.get("categorias")
        propio = self.instance.pk
        ocupadas = [
            categoria.descripcion
            for categoria in elegidas
            if (dueno := self._asignadas.get(categoria.pk)) is not None and dueno.pk != propio
        ]
        if ocupadas:
            raise forms.ValidationError(
                "Estas categorías ya van a otro sector: "
                + ", ".join(ocupadas)
                + ". Sacalas de ese sector primero."
            )
        return elegidas

    @transaction.atomic
    def save(self, commit=True):
        sector = super().save(commit=commit)
        if commit:
            deseadas = {categoria.pk for categoria in self.cleaned_data.get("categorias", [])}
            sector.categorias.exclude(categoria_id__in=deseadas).delete()
            actuales = set(sector.categorias.values_list("categoria_id", flat=True))
            SectorCategoria.objects.bulk_create(
                [
                    SectorCategoria(sector=sector, categoria_id=pk)
                    for pk in sorted(deseadas - actuales)
                ]
            )
        return sector


class ItemSectorField(ComboChoiceField):
    def label_from_instance(self, obj):
        return obj.descripcion


class SectorItemForm(RupiaModelForm):
    item = ItemSectorField(
        queryset=Item.objects.filter(activo=True),
        clave="item_sector",
        label="Producto",
        required_message="Elegí un producto.",
        error_messages={"invalid_choice": "Elegí un producto activo."},
        placeholder="Buscar producto…",
    )

    class Meta:
        model = SectorItem
        fields = ["item", "sector"]
        labels = {"sector": "Va a"}
        error_messages = {
            "item": {"unique": "Ese producto ya tiene un sector propio."},
            "sector": {"required": "Elegí el sector."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        sectores = Sector.objects.filter(activo=True)
        if self.instance.pk:
            sectores = Sector.objects.filter(activo=True) | Sector.objects.filter(
                pk=self.instance.sector_id
            )
        self.fields["sector"].queryset = sectores.order_by("nombre")
        self.fields["sector"].empty_label = "Elegí un sector"
        if self.instance.pk:
            # Si el producto quedó inactivo, que se pueda seguir editando.
            self.fields["item"].queryset = Item.objects.filter(activo=True) | Item.objects.filter(
                pk=self.instance.item_id
            )

    def clean_item(self):
        item = self.cleaned_data["item"]
        if SectorItem.objects.exclude(pk=self.instance.pk).filter(item=item).exists():
            raise forms.ValidationError("Ese producto ya tiene un sector propio.")
        return item


class MesaForm(RupiaModelForm):
    class Meta:
        model = Mesa
        fields = ["nombre", "zona", "capacidad", "orden", "activa"]
        labels = {
            "nombre": "Nombre o número",
            "zona": "Zona",
            "capacidad": "Capacidad",
            "orden": "Orden",
            "activa": "Activa",
        }
        widgets = {
            "nombre": forms.TextInput(
                attrs={"autofocus": True, "autocomplete": "off", "maxlength": "40"}
            ),
            "zona": forms.TextInput(attrs={"autocomplete": "off", "maxlength": "60"}),
            "capacidad": forms.NumberInput(attrs={"min": "1", "inputmode": "numeric"}),
            "orden": forms.NumberInput(attrs={"min": "0", "inputmode": "numeric"}),
        }
        error_messages = {
            "nombre": {
                "required": "Escribí el nombre o número de la mesa.",
                "unique": "Ya hay una mesa con ese nombre.",
                "max_length": "El nombre admite hasta 40 caracteres.",
            },
            "capacidad": {"invalid": "Escribí la capacidad en números."},
            "orden": {"invalid": "Escribí el orden en números."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["orden"].required = False

    def clean_nombre(self):
        nombre = (self.cleaned_data.get("nombre") or "").strip()
        if not nombre:
            raise forms.ValidationError("Escribí el nombre o número de la mesa.")
        return nombre

    def clean_zona(self):
        return (self.cleaned_data.get("zona") or "").strip()

    def clean_capacidad(self):
        capacidad = self.cleaned_data.get("capacidad")
        if capacidad is not None and capacidad < 1:
            raise forms.ValidationError("La capacidad tiene que ser al menos 1.")
        return capacidad

    def clean_orden(self):
        orden = self.cleaned_data.get("orden")
        return 0 if orden is None else orden


class ClienteComandaField(ComboChoiceField):
    def label_from_instance(self, obj):
        return str(obj)


def _campo_cliente():
    from django.urls import reverse_lazy

    from personas.models import Persona

    return ClienteComandaField(
        queryset=Persona.objects.filter(activo=True, es_cliente=True),
        search_url=reverse_lazy("mesas_clientes"),
        label="Cliente (opcional)",
        required=False,
        required_message="Elegí un cliente de la lista.",
        placeholder="Buscar por nombre o RUC…",
    )


class CuentaForm(forms.Form):
    """Datos de una cuenta: a nombre de quién, cliente y personas."""

    use_required_attribute = False

    nombre = forms.CharField(
        label="A nombre de",
        max_length=80,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": " ", "autocomplete": "off"}),
    )
    personas = forms.IntegerField(
        label="Personas",
        required=False,
        min_value=1,
        error_messages={
            "invalid": "Escribí la cantidad de personas en números.",
            "min_value": "La cantidad de personas tiene que ser al menos 1.",
        },
        widget=forms.NumberInput(attrs={"placeholder": " ", "min": "1", "inputmode": "numeric"}),
    )

    def __init__(self, *args, exigir_destino=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cliente"] = _campo_cliente()
        self.order_fields(["nombre", "cliente", "personas"])
        self.exigir_destino = exigir_destino

    def clean_nombre(self):
        return (self.cleaned_data.get("nombre") or "").strip()

    def clean(self):
        cleaned = super().clean()
        if self.exigir_destino and not cleaned.get("nombre") and not cleaned.get("cliente"):
            raise forms.ValidationError("Escribí un nombre o elegí un cliente.")
        return cleaned


registrar(
    "item_sector",
    queryset=lambda: Item.objects.filter(activo=True).order_by("descripcion"),
    search_fields=("descripcion", "codigo_barra", "marca__descripcion"),
    formulario="sectores",
)

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from compras.carga import (
    actualizar_cabecera,
    agregar_item,
    anular,
    asegurar_proveedor_desde_consulta,
    borrador,
    buscar_items,
    buscar_proveedores_pos,
    cambiar_cantidad,
    cambiar_costo,
    cambiar_tasa,
    cambiar_unidad,
    cambiar_unidad_negocio,
    cancelar,
    confirmar,
    cuentas,
    interpretar_secuencial_compra,
    interpretar_serie_compra,
    lineas_vista,
    liquidar_iva,
    numero_ya_usado,
    precios_pendientes,
    quitar_linea,
    subtotal_compra,
    tasas_iva,
    unidades_negocio,
)
from compras.models import (
    Compra,
    CompraDetalle,
    EstadoCompra,
    TipoCompra,
    formatear_numero_factura,
)
from compras.tables import CompraTable
from configuracion.permisos import PermisoRequeridoMixin, tiene_permiso
from core.cantidad import formatear_cantidad, interpretar_cantidad
from core.listado import (
    apply_filters,
    apply_search,
    filter_specs_for,
    filter_values,
    search_fields_for,
)
from core.mantenimiento import MantenimientoListView
from core.moneda import SIMBOLO, formatear_guaranies, interpretar_guaranies, mostrar_guaranies
from core.timbrado import interpretar_timbrado
from cuentas.models import Cuenta
from inventario.models import Item, TipoItem, UnidadMedida
from negocio.models import UnidadNegocio
from personas.models import Persona


def _dinero(valor) -> str:
    return mostrar_guaranies(valor)


def _error(exc: ValidationError) -> str:
    if hasattr(exc, "message") and exc.message:
        return str(exc.message)
    if exc.messages:
        return str(exc.messages[0])
    return "No se pudo completar la compra."


def _monto(valor, default=None):
    if valor in (None, ""):
        return default
    try:
        return Decimal(interpretar_guaranies(valor))
    except (ValidationError, InvalidOperation):
        try:
            return Decimal(str(valor).replace(".", "").replace(",", "."))
        except (InvalidOperation, ValueError):
            return default


class CompraListado:
    model = Compra
    table_class = CompraTable
    permiso_formulario = "compras"
    page_title = "Compras"
    eyebrow = "Compras"
    title = "Compras"
    create_label = "Nueva compra"
    show_create = True
    list_hint = "Flechas para moverse. Enter abre la compra."
    search_label = "Buscar"
    search_placeholder = "Buscar por número, proveedor o timbrado..."
    search_field = "numero_completo"
    search_fields = ("numero_completo", "proveedor__razon_social", "timbrado")
    filters = (
        {
            "name": "tipo",
            "label": "Tipo",
            "kind": "choice",
            "choices": TipoCompra.choices,
        },
        {
            "name": "estado",
            "label": "Estado",
            "kind": "choice",
            "choices": (
                (EstadoCompra.CONFIRMADA, "Confirmada"),
                (EstadoCompra.ANULADA, "Anulada"),
            ),
        },
        {
            "name": "fecha_desde",
            "label": "Desde",
            "kind": "date",
            "field": "fecha",
            "lookup": "gte",
        },
        {
            "name": "fecha_hasta",
            "label": "Hasta",
            "kind": "date",
            "field": "fecha",
            "lookup": "lte",
        },
    )
    selection_param = "compra"
    record_noun = "compra"
    order_by = ("-fecha", "-pk")
    list_url_name = "compra_list"
    create_url_name = "compra_nueva"
    print_url_name = "compra_print"
    export_xlsx_url_name = "compra_export_xlsx"
    export_pdf_url_name = "compra_export_pdf"
    export_basename = "compras"
    view_exclude = ("anulado_en", "anulado_por", "afectar_precios")


class CompraListView(CompraListado, MantenimientoListView):
    def creating(self):
        return False

    def get_queryset(self):
        cero = Value(0, output_field=DecimalField(max_digits=15, decimal_places=3))
        importe = Coalesce(Sum("detalles__subtotal"), cero)
        queryset = (
            self.model.objects.filter(estado__in=(EstadoCompra.CONFIRMADA, EstadoCompra.ANULADA))
            .select_related("proveedor", "cuenta")
            .annotate(importe=importe)
            .order_by(*self.order_by)
        )
        queryset = apply_search(queryset, self.query(), search_fields_for(self))
        specs = filter_specs_for(self)
        return apply_filters(queryset, filter_values(self.request, specs), specs)

    def get_table(self, **kwargs):
        table = super().get_table(**kwargs)
        table.puede_anular = self.puede("anular")
        return table

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["edit_url"] = ""
        if self.puede("alta"):
            context["create_url"] = reverse("compra_nueva")
        return context


class AnularCompraView(LoginRequiredMixin, PermisoRequeridoMixin, View):
    permiso_formulario = "compras"
    permiso_accion = "anular"

    def post(self, request, pk):
        compra = get_object_or_404(Compra, pk=pk)
        try:
            anular(compra, usuario=request.user)
            messages.success(request, f"Se anuló {compra}.")
        except ValidationError as exc:
            messages.error(request, _error(exc))
        return redirect("compra_list")


class CompraPermisoView(LoginRequiredMixin, PermisoRequeridoMixin, View):
    permiso_formulario = "compras"
    permiso_accion = "alta"


class CompraFormView(CompraPermisoView):
    def get(self, request):
        compra = borrador(request.user)
        return render(request, "compras/formulario.html", self._contexto(compra))

    def post(self, request):
        compra = borrador(request.user)
        try:
            self._aplicar(request, compra)
            if request.POST.get("guardar"):
                messages.success(request, "La compra quedó guardada.")
                return redirect("compra_list")
        except ValidationError as exc:
            messages.error(request, _error(exc))
            return redirect("compra_nueva")
        return redirect("compra_nueva")

    def _aplicar(self, request, compra):
        datos = request.POST
        cuenta = None
        if datos.get("cuenta"):
            cuenta = get_object_or_404(Cuenta, pk=datos.get("cuenta"))
        proveedor = None
        sin_proveedor = datos.get("sin_proveedor") == "1"
        if datos.get("proveedor"):
            proveedor = get_object_or_404(Persona, pk=datos.get("proveedor"))
        tipo = datos.get("tipo")
        if tipo and tipo not in TipoCompra.values:
            tipo = None
        actualizar_cabecera(
            compra,
            cuenta=cuenta,
            tipo=tipo,
            proveedor=proveedor,
            sin_proveedor=sin_proveedor,
            observacion=datos.get("observacion"),
            timbrado=datos.get("timbrado"),
            establecimiento=datos.get("numero_establecimiento"),
            punto_codigo=datos.get("numero_punto"),
            secuencial=datos.get("numero_secuencial"),
        )

    def _contexto(self, compra):
        lineas = lineas_vista(compra)
        iva = liquidar_iva(compra)
        total = subtotal_compra(compra)
        iva_monto = iva.iva_10 + iva.iva_5
        if iva.iva_10 and not iva.iva_5:
            iva_label = "IVA (10%)"
        elif iva.iva_5 and not iva.iva_10:
            iva_label = "IVA (5%)"
        else:
            iva_label = "IVA"
        pendientes = precios_pendientes(compra)
        pendientes_vista = [
            {
                "descripcion": pendiente.descripcion,
                "costo_anterior": (
                    formatear_guaranies(pendiente.costo_anterior)
                    if pendiente.costo_anterior is not None
                    else "—"
                ),
                "costo_nuevo": formatear_guaranies(pendiente.costo_nuevo),
                "precio_anterior": (
                    formatear_guaranies(pendiente.precio_anterior)
                    if pendiente.precio_anterior is not None
                    else "—"
                ),
                "precio_nuevo": formatear_guaranies(pendiente.precio_nuevo),
            }
            for pendiente in pendientes
        ]
        return {
            "compra": compra,
            "lineas": lineas,
            "iva": iva,
            "cuentas": cuentas(),
            "unidades_negocio": unidades_negocio(),
            "tasas": tasas_iva(),
            "tipos": TipoCompra.choices,
            "pendientes": pendientes_vista,
            "hay_precios": bool(pendientes),
            "subtotal": total,
            "total": total,
            "subtotal_txt": _dinero(total),
            "total_txt": _dinero(total),
            "iva_label": iva_label,
            "iva_txt": _dinero(iva_monto),
            "unidades_txt": formatear_cantidad(
                sum((linea.cantidad for linea in lineas), Decimal("0"))
            ),
            "proveedor_label": (str(compra.proveedor) if compra.proveedor_id else ""),
            "cuenta_label": compra.cuenta.nombre_corto if compra.cuenta_id else "Sin cuenta",
            "numero_establecimiento": compra.establecimiento or "",
            "numero_punto": compra.punto_codigo or "",
            "numero_secuencial": (f"{compra.secuencial:07d}" if compra.secuencial else ""),
            "timbrado_txt": compra.timbrado or "",
            "numero_visor": compra.numero_completo or "—",
            "persona_nueva_url": (
                f"{reverse('persona_list')}?nueva=1&proveedor=1"
                if tiene_permiso(self.request.user, "personas", "alta")
                else ""
            ),
        }


class BuscarItemsView(CompraPermisoView):
    def get(self, request):
        query = request.GET.get("q", "")
        try:
            limite = min(20, max(1, int(request.GET.get("limite") or 20)))
        except (TypeError, ValueError):
            limite = 20
        try:
            offset = max(0, int(request.GET.get("offset") or 0))
        except (TypeError, ValueError):
            offset = 0
        hallados = buscar_items(query, limite=limite + 1, offset=offset, catalogo=True)
        hay_mas = len(hallados) > limite
        hallados = hallados[:limite]
        resultados = []
        for item in hallados:
            resultados.append(
                {
                    "id": item.pk,
                    "descripcion": item.descripcion,
                    "marca": item.marca.descripcion if item.marca_id else "",
                    "codigo": item.codigo_barra or "",
                    "tipo": item.get_tipo_display(),
                    "gasto": item.tipo == TipoItem.GASTO,
                    "precio": _dinero(item.ultimo_costo or 0),
                    "unidad": item.unidad_medida.simbolo,
                    "imagen": reverse("item_imagen", args=[item.imagen]) if item.imagen else "",
                }
            )
        return JsonResponse(
            {
                "resultados": resultados,
                "hay_mas": hay_mas,
                "offset": offset,
                "siguiente": offset + len(resultados),
            }
        )


class ValidarNumeroView(CompraPermisoView):
    def get(self, request):
        compra = borrador(request.user)
        try:
            timbrado = interpretar_timbrado(request.GET.get("timbrado"))
            establecimiento = interpretar_serie_compra(
                request.GET.get("establecimiento") or "001",
                "establecimiento",
            )
            codigo = interpretar_serie_compra(request.GET.get("punto") or "001", "punto")
            secuencial = interpretar_secuencial_compra(request.GET.get("secuencial") or "1")
        except ValidationError as exc:
            return JsonResponse({"ok": False, "error": _error(exc)}, status=400)
        numero = formatear_numero_factura(establecimiento, codigo, secuencial)
        if numero_ya_usado(compra.proveedor_id, timbrado, numero, excluir=compra.pk):
            return JsonResponse(
                {
                    "ok": False,
                    "numero": numero,
                    "error": "Ya hay una factura de ese proveedor con ese timbrado y número.",
                }
            )
        return JsonResponse({"ok": True, "numero": numero, "timbrado": timbrado})


class BuscarProveedoresView(CompraPermisoView):
    def get(self, request):
        query = request.GET.get("q", "")
        return JsonResponse({"resultados": buscar_proveedores_pos(query)})

    def post(self, request):
        compra = borrador(request.user)
        try:
            proveedor = asegurar_proveedor_desde_consulta(
                ruc=request.POST.get("ruc", ""),
                query=request.POST.get("q", ""),
            )
            actualizar_cabecera(compra, proveedor=proveedor)
        except ValidationError as exc:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"error": _error(exc)}, status=400)
            messages.error(request, _error(exc))
            return redirect("compra_nueva")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"id": proveedor.pk, "label": str(proveedor)})
        return redirect("compra_nueva")


class AgregarItemView(CompraPermisoView):
    def post(self, request):
        compra = borrador(request.user)
        item = None
        if request.POST.get("item"):
            item = get_object_or_404(Item, pk=request.POST.get("item"))
        try:
            resultado = agregar_item(compra, item=item, query=request.POST.get("q", ""))
        except ValidationError as exc:
            messages.error(request, _error(exc))
            return redirect("compra_nueva")
        if isinstance(resultado, list):
            messages.error(request, "Elegí un ítem de la lista.")
        return redirect("compra_nueva")


class LineaCompraView(CompraPermisoView):
    def post(self, request, pk):
        compra = borrador(request.user)
        detalle = get_object_or_404(CompraDetalle, pk=pk, compra=compra)
        accion = request.POST.get("accion", "")
        try:
            if accion == "quitar":
                quitar_linea(detalle)
            elif accion == "unidad":
                unidad = get_object_or_404(UnidadMedida, pk=request.POST.get("unidad"))
                cambiar_unidad(detalle, unidad)
            elif accion == "negocio":
                negocio = get_object_or_404(UnidadNegocio, pk=request.POST.get("unidad_negocio"))
                cambiar_unidad_negocio(detalle, negocio)
            elif accion == "tasa":
                cambiar_tasa(detalle, request.POST.get("tasa"))
            elif accion == "costo":
                costo = _monto(request.POST.get("costo"), None)
                if costo is None:
                    raise ValidationError("Escribí el costo.", code="costo")
                cambiar_costo(detalle, costo)
            else:
                actual = detalle.cantidad
                if accion == "mas":
                    cambiar_cantidad(detalle, actual + 1)
                elif accion == "menos":
                    cambiar_cantidad(detalle, actual - 1)
                elif request.POST.get("cantidad") not in (None, ""):
                    crudo = interpretar_cantidad(request.POST.get("cantidad"))
                    if not crudo:
                        raise ValidationError("Escribí la cantidad.", code="cantidad")
                    cambiar_cantidad(detalle, Decimal(crudo))
        except ValidationError as exc:
            messages.error(request, _error(exc))
        return redirect("compra_nueva")


class ConfirmarCompraView(CompraPermisoView):
    def post(self, request):
        compra = borrador(request.user)
        try:
            CompraFormView()._aplicar(request, compra)
            compra.refresh_from_db()
            compra = confirmar(
                compra,
                afectar_precios=request.POST.get("afectar_precios") == "1",
            )
        except ValidationError as exc:
            messages.error(request, _error(exc))
            return redirect("compra_nueva")
        messages.success(request, f"Se confirmó {compra}.")
        return redirect("compra_list")


class CancelarCompraView(CompraPermisoView):
    permiso_accion = "cancelar"

    def post(self, request):
        compra = Compra.objects.filter(usuario=request.user, estado=EstadoCompra.EN_CURSO).first()
        if compra:
            try:
                cancelar(compra)
                messages.success(request, "La compra quedó limpia.")
            except ValidationError as exc:
                messages.error(request, _error(exc))
        return redirect("compra_nueva")

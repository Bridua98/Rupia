from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from configuracion.permisos import PermisoRequeridoMixin, tiene_permiso
from core.cantidad import formatear_cantidad, interpretar_cantidad
from core.combo import combo_context
from core.listado import (
    apply_filters,
    apply_search,
    filter_specs_for,
    filter_values,
    search_fields_for,
)
from core.mantenimiento import (
    MantenimientoCreateView,
    MantenimientoDeleteView,
    MantenimientoListView,
    MantenimientoUpdateView,
)
from core.moneda import formatear_guaranies, interpretar_guaranies, mostrar_guaranies
from cuentas.models import Cuenta
from inventario.models import Item, UnidadMedida
from personas.models import Persona
from ventas.cobro import (
    actualizar_cabecera,
    agregar_producto,
    anular,
    asegurar_cliente_desde_consulta,
    borrador,
    buscar_clientes_pos,
    buscar_productos,
    cajas,
    cambiar_cantidad,
    cambiar_descuento,
    cambiar_unidad,
    cancelar,
    cliente_ocasional,
    comprobantes_pos,
    confirmar,
    cuentas_para_medio,
    exigir_cliente_factura,
    exigir_emision,
    factura_pide_cliente,
    formatear_porcentaje,
    importes_rapidos,
    interpretar_secuencial,
    interpretar_serie,
    lineas_vista,
    liquidar_iva,
    medios_disponibles,
    motivo_emision,
    motivo_pos,
    numero_ya_usado,
    proximo_numero,
    puede_cobrar,
    puede_guardar,
    punto_de,
    quitar_linea,
    subtotal_venta,
    total_venta,
    vuelto_venta,
)
from ventas.forms import TimbradoForm
from ventas.models import (
    EstadoVenta,
    MedioPago,
    PuntoExpedicion,
    TipoAnulacion,
    TipoComprobante,
    Venta,
    VentaDetalle,
    formatear_numero_comprobante,
)
from ventas.tables import TimbradoTable, VentaTable


def _dinero(valor) -> str:
    return mostrar_guaranies(valor)


def _numero_visor(venta, punto) -> str:
    if venta.tipo_comprobante != TipoComprobante.FACTURA:
        return proximo_numero(TipoComprobante.TICKET)
    establecimiento = venta.establecimiento or (punto.establecimiento if punto else "")
    codigo = venta.punto_codigo or (punto.codigo if punto else "")
    secuencial = venta.secuencial if venta.secuencial is not None else (
        punto.numero_proximo if punto else None
    )
    if establecimiento and codigo and secuencial is not None:
        return formatear_numero_comprobante(establecimiento, codigo, secuencial)
    return proximo_numero(TipoComprobante.FACTURA)


def _error(exc: ValidationError) -> str:
    if hasattr(exc, "message") and exc.message:
        return str(exc.message)
    if exc.messages:
        return str(exc.messages[0])
    return "No se pudo completar la venta."


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


class TimbradoMantenimiento:
    model = PuntoExpedicion
    form_class = TimbradoForm
    table_class = TimbradoTable
    permiso_formulario = "timbrados"
    page_title = "Timbrados"
    eyebrow = "Gestión"
    title = "Timbrados"
    create_label = "Nuevo timbrado"
    list_hint = "Flechas para moverse. Enter abre el timbrado."
    search_label = "Buscar"
    search_placeholder = "Buscar por timbrado, RUC o razón social..."
    search_field = "timbrado"
    search_fields = ("timbrado", "emisor_ruc", "emisor_razon_social")
    filters = (
        {
            "name": "tipo",
            "label": "Comprobante",
            "kind": "choice",
            "choices": TipoComprobante.choices,
        },
        {"name": "habilitado", "label": "Habilitado", "kind": "bool"},
    )
    selection_param = "timbrado"
    record_noun = "timbrado"
    order_by = ("tipo", "pk")
    list_url_name = "timbrado_list"
    create_url_name = "timbrado_create"
    update_url_name = "timbrado_update"
    delete_url_name = "timbrado_delete"
    print_url_name = "timbrado_print"
    export_xlsx_url_name = "timbrado_export_xlsx"
    export_pdf_url_name = "timbrado_export_pdf"
    export_basename = "timbrados"


class TimbradoListView(TimbradoMantenimiento, MantenimientoListView):
    pass


class VentaListado:
    model = Venta
    table_class = VentaTable
    permiso_formulario = "ventas"
    page_title = "Ventas"
    eyebrow = "Ventas"
    title = "Ventas"
    create_label = ""
    show_create = False
    stage_action_url_name = "punto_de_venta"
    stage_action_label = "Punto de venta"
    stage_action_icon = "bag"
    stage_action_permiso_formulario = "punto_de_venta"
    stage_action_permiso_accion = "ver"
    list_hint = "Flechas para moverse. Enter abre la venta."
    search_label = "Buscar"
    search_placeholder = "Buscar por número, cliente o timbrado..."
    search_field = "numero_completo"
    search_fields = (
        "numero_completo",
        "cliente__razon_social",
        "timbrado",
        "numero_comprobante_pago",
    )
    filters = (
        {
            "name": "tipo_comprobante",
            "label": "Comprobante",
            "kind": "choice",
            "choices": TipoComprobante.choices,
        },
        {
            "name": "estado",
            "label": "Estado",
            "kind": "choice",
            "choices": (
                (EstadoVenta.COBRADA, "Cobrada"),
                (EstadoVenta.ANULADA, "Anulada"),
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
    selection_param = "venta"
    record_noun = "venta"
    order_by = ("-fecha", "-pk")
    list_url_name = "venta_list"
    print_url_name = "venta_print"
    export_xlsx_url_name = "venta_export_xlsx"
    export_pdf_url_name = "venta_export_pdf"
    export_basename = "ventas"
    view_exclude = (
        "punto",
        "vigencia_desde",
        "vigencia_hasta",
        "establecimiento",
        "punto_codigo",
        "secuencial",
        "emisor_razon_social",
        "emisor_ruc",
        "emisor_direccion",
        "emisor_telefono",
        "emisor_actividad",
    )


class VentaListView(VentaListado, MantenimientoListView):
    def get_queryset(self):
        cero = Value(0, output_field=DecimalField(max_digits=15, decimal_places=3))
        importe = Coalesce(Sum("detalles__subtotal"), cero) - Coalesce(F("descuento"), cero)
        queryset = (
            self.model.objects.filter(
                estado__in=(EstadoVenta.COBRADA, EstadoVenta.ANULADA)
            )
            .select_related("cliente")
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
        return context


class AnularVentaView(LoginRequiredMixin, PermisoRequeridoMixin, View):
    permiso_formulario = "ventas"
    permiso_accion = "anular"

    def post(self, request, pk):
        venta = get_object_or_404(Venta, pk=pk)
        tipo = request.POST.get("tipo_anulacion") or TipoAnulacion.FISICA
        try:
            anular(venta, tipo, usuario=request.user)
            messages.success(request, f"Se anuló {venta}.")
        except ValidationError as exc:
            messages.error(request, _error(exc))
        return redirect("venta_list")


class TimbradoCreateView(TimbradoMantenimiento, MantenimientoCreateView):
    list_view_class = TimbradoListView


class TimbradoUpdateView(TimbradoMantenimiento, MantenimientoUpdateView):
    list_view_class = TimbradoListView


class TimbradoDeleteView(TimbradoMantenimiento, MantenimientoDeleteView):
    pass


class PosPermisoView(LoginRequiredMixin, PermisoRequeridoMixin, View):
    permiso_formulario = "punto_de_venta"
    permiso_accion = "ver"


class PuntoVentaView(PosPermisoView):
    def get(self, request):
        venta = borrador(request.user)
        return render(request, "ventas/punto_de_venta.html", self._contexto(venta))

    def post(self, request):
        venta = borrador(request.user)
        try:
            self._aplicar(request, venta)
            if request.POST.get("guardar"):
                exigir_cliente_factura(venta)
                exigir_emision(
                    punto_de(venta.tipo_comprobante),
                    tipo=venta.tipo_comprobante,
                )
                messages.success(request, "La venta quedó guardada.")
                return redirect("home")
        except ValidationError as exc:
            messages.error(request, _error(exc))
            return redirect("punto_de_venta")
        return redirect("punto_de_venta")

    def _aplicar(self, request, venta):
        datos = request.POST
        caja = None
        if datos.get("caja"):
            caja = get_object_or_404(Cuenta, pk=datos.get("caja"))
        cuenta = None
        if datos.get("cuenta_cobro"):
            cuenta = get_object_or_404(Cuenta, pk=datos.get("cuenta_cobro"))
        cliente = None
        consumidor = False
        if datos.get("asignar_ocasional"):
            cliente = cliente_ocasional()
        elif datos.get("consumidor_final") == "1":
            consumidor = True
        elif datos.get("cliente"):
            cliente = get_object_or_404(Persona, pk=datos.get("cliente"))
        tipo = datos.get("tipo_comprobante")
        if tipo and tipo not in TipoComprobante.values:
            tipo = None
        medio = datos.get("medio")
        if medio and medio not in MedioPago.values:
            medio = None
        actualizar_cabecera(
            venta,
            caja=caja,
            tipo_comprobante=tipo,
            medio=medio,
            cuenta_cobro=cuenta,
            descuento=_monto(datos.get("descuento"), None),
            cliente=cliente,
            consumidor_final=consumidor,
            observacion=datos.get("observacion"),
            importe_recibido=_monto(datos.get("importe_recibido"), None),
            numero_comprobante_pago=datos.get("numero_comprobante_pago"),
        )

    def _contexto(self, venta):
        lineas = lineas_vista(venta)
        iva = liquidar_iva(venta)
        total = total_venta(venta)
        subtotal = subtotal_venta(venta)
        punto = punto_de(venta.tipo_comprobante)
        iva_monto = iva.iva_10 + iva.iva_5
        if iva.iva_10 and not iva.iva_5:
            iva_label = "IVA (10%)"
        elif iva.iva_5 and not iva.iva_10:
            iva_label = "IVA (5%)"
        else:
            iva_label = "IVA"
        if subtotal > 0 and venta.descuento:
            descuento_pct = (venta.descuento * Decimal("100") / subtotal).quantize(Decimal("0.01"))
        else:
            descuento_pct = Decimal("0")
        pide_cliente = factura_pide_cliente(venta)
        return {
            "venta": venta,
            "lineas": lineas,
            "iva": iva,
            "cajas": cajas(),
            "cuentas_cobro": cuentas_para_medio(venta.medio, venta.caja),
            "medios": medios_disponibles(venta.medio),
            "comprobantes": comprobantes_pos(),
            "puede_cobrar": puede_cobrar(venta),
            "puede_guardar": puede_guardar(venta),
            "factura_pide_cliente": pide_cliente,
            "emision_motivo": motivo_pos(venta),
            "proximo_numero": proximo_numero(venta.tipo_comprobante),
            "numero_visor": _numero_visor(venta, punto),
            "punto": punto,
            "subtotal": subtotal,
            "total": total,
            "vuelto": vuelto_venta(venta),
            "rapidos": [
                {"valor": monto, "txt": formatear_guaranies(monto)}
                for monto in importes_rapidos(total)
            ],
            "subtotal_entero": int(subtotal),
            "total_entero": int(total),
            "numero_establecimiento": (
                (venta.establecimiento or (punto.establecimiento if punto else ""))
                if venta.tipo_comprobante == TipoComprobante.FACTURA
                else ""
            ),
            "numero_punto": (
                (venta.punto_codigo or (punto.codigo if punto else ""))
                if venta.tipo_comprobante == TipoComprobante.FACTURA
                else ""
            ),
            "numero_secuencial": (
                (
                    f"{venta.secuencial:07d}"
                    if venta.secuencial is not None
                    else (f"{punto.numero_proximo:07d}" if punto else "")
                )
                if venta.tipo_comprobante == TipoComprobante.FACTURA
                else ""
            ),
            "timbrado_txt": (punto.timbrado if punto else ""),
            "subtotal_txt": _dinero(subtotal),
            "total_txt": _dinero(total),
            "iva_label": iva_label,
            "iva_txt": _dinero(iva_monto),
            "descuento_pct_txt": formatear_porcentaje(descuento_pct),
            "descuento_txt": formatear_guaranies(venta.descuento or 0),
            "recibido_txt": formatear_guaranies(venta.importe_recibido or 0),
            "vuelto_txt": _dinero(vuelto_venta(venta)),
            "unidades_txt": formatear_cantidad(
                sum((linea.cantidad for linea in lineas), Decimal("0"))
            ),
            "persona_nueva_url": (
                f"{reverse('persona_list')}?nueva=1&cliente=1"
                if tiene_permiso(self.request.user, "personas", "alta")
                else ""
            ),
            "cliente_label": (str(venta.cliente) if venta.cliente_id else ""),
            "cliente_combo": combo_context(
                name="cliente",
                value=venta.cliente_id or "",
                label="Cliente",
                selected_label=str(venta.cliente) if venta.cliente_id else "",
                search_url=reverse("punto_de_venta_clientes"),
                required=pide_cliente,
                required_message="La factura pide un cliente.",
                submit=True,
                variant="pos",
                placeholder="Buscar cliente por nombre, RUC o cédula...",
                hide_label=True,
                nueva_url=(
                    f"{reverse('persona_list')}?nueva=1&cliente=1"
                    if tiene_permiso(self.request.user, "personas", "alta")
                    else ""
                ),
                nueva_ayuda="Abrir la ficha para cargar un cliente.",
                alta_url=reverse("punto_de_venta_clientes"),
                padron_label="Crear cliente",
                attrs={"id": "pos-cliente-q"},
            ),
            "caja_label": venta.caja.nombre_corto if venta.caja_id else "Sin caja",
            "cliente_ocasional": cliente_ocasional(),
        }


class BuscarProductosView(PosPermisoView):
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
        hallados = buscar_productos(query, limite=limite + 1, offset=offset, catalogo=True)
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
                    "precio": _dinero(item.precio or 0),
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


class ValidarNumeroView(PosPermisoView):
    def get(self, request):
        venta = borrador(request.user)
        if venta.tipo_comprobante != TipoComprobante.FACTURA:
            return JsonResponse(
                {
                    "ok": False,
                    "error": "La numeración manual solo aplica a factura.",
                },
                status=400,
            )
        punto = punto_de(TipoComprobante.FACTURA)
        if punto is None:
            return JsonResponse(
                {
                    "ok": False,
                    "error": motivo_emision(None, tipo=TipoComprobante.FACTURA),
                },
                status=400,
            )
        try:
            exigir_emision(punto, tipo=TipoComprobante.FACTURA)
        except ValidationError as exc:
            return JsonResponse({"ok": False, "error": _error(exc)}, status=400)
        try:
            establecimiento = interpretar_serie(
                request.GET.get("establecimiento"),
                punto.establecimiento,
                "establecimiento",
            )
            codigo = interpretar_serie(request.GET.get("punto"), punto.codigo, "punto")
            secuencial = interpretar_secuencial(request.GET.get("secuencial"), punto.numero_proximo)
        except ValidationError as exc:
            return JsonResponse({"ok": False, "error": _error(exc)}, status=400)
        if not (punto.numero_desde <= secuencial <= punto.numero_hasta):
            return JsonResponse(
                {"ok": False, "error": "Ese número está fuera del rango del timbrado de factura."},
                status=400,
            )
        numero = formatear_numero_comprobante(establecimiento, codigo, secuencial)
        if numero_ya_usado(punto.timbrado, numero, tipo=TipoComprobante.FACTURA):
            return JsonResponse(
                {
                    "ok": False,
                    "numero": numero,
                    "error": "Ya hay un comprobante con ese timbrado y número.",
                }
            )
        return JsonResponse({"ok": True, "numero": numero, "timbrado": punto.timbrado})


class BuscarClientesView(PosPermisoView):
    def get(self, request):
        query = request.GET.get("q", "")
        resultados = buscar_clientes_pos(query)
        return JsonResponse({"results": resultados, "resultados": resultados})

    def post(self, request):
        venta = borrador(request.user)
        try:
            cliente = asegurar_cliente_desde_consulta(
                ruc=request.POST.get("ruc", ""),
                query=request.POST.get("q", ""),
            )
            actualizar_cabecera(venta, cliente=cliente)
        except ValidationError as exc:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"error": _error(exc)}, status=400)
            messages.error(request, _error(exc))
            return redirect("punto_de_venta")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"id": cliente.pk, "label": str(cliente)})
        return redirect("punto_de_venta")


class AgregarProductoView(PosPermisoView):
    def post(self, request):
        venta = borrador(request.user)
        item = None
        if request.POST.get("item"):
            item = get_object_or_404(Item, pk=request.POST.get("item"))
        try:
            resultado = agregar_producto(venta, item=item, query=request.POST.get("q", ""))
        except ValidationError as exc:
            messages.error(request, _error(exc))
            return redirect("punto_de_venta")
        if isinstance(resultado, list):
            messages.error(request, "Elegí un producto de la lista.")
        return redirect("punto_de_venta")


class LineaVentaView(PosPermisoView):
    def post(self, request, pk):
        venta = borrador(request.user)
        detalle = get_object_or_404(VentaDetalle, pk=pk, venta=venta)
        accion = request.POST.get("accion", "")
        try:
            if accion == "quitar":
                quitar_linea(detalle)
            elif accion == "unidad":
                unidad = get_object_or_404(UnidadMedida, pk=request.POST.get("unidad"))
                cambiar_unidad(detalle, unidad)
            elif accion == "descuento":
                cambiar_descuento(detalle, request.POST.get("descuento") or 0)
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
        return redirect("punto_de_venta")


class ConfirmarVentaView(PosPermisoView):
    permiso_accion = "cobrar"

    def post(self, request):
        venta = borrador(request.user)
        try:
            PuntoVentaView()._aplicar(request, venta)
            venta.refresh_from_db()
            venta = confirmar(
                venta,
                establecimiento=request.POST.get("numero_establecimiento"),
                punto_codigo=request.POST.get("numero_punto"),
                secuencial=request.POST.get("numero_secuencial"),
            )
        except ValidationError as exc:
            messages.error(request, _error(exc))
            return redirect("punto_de_venta")
        if venta.tipo_comprobante == TipoComprobante.FACTURA:
            return redirect("venta_factura", pk=venta.pk)
        return redirect("venta_ticket", pk=venta.pk)


class CancelarVentaView(PosPermisoView):
    permiso_accion = "cancelar"

    def post(self, request):
        venta = Venta.objects.filter(usuario=request.user, estado=EstadoVenta.EN_CURSO).first()
        if venta:
            try:
                cancelar(venta)
                messages.success(request, "La venta quedó limpia.")
            except ValidationError as exc:
                messages.error(request, _error(exc))
        return redirect("punto_de_venta")


class ComprobanteView(LoginRequiredMixin, View):
    tipo = TipoComprobante.TICKET
    template_name = "ventas/ticket.html"

    def dispatch(self, request, *args, **kwargs):
        if not (
            tiene_permiso(request.user, "punto_de_venta", "ver")
            or tiene_permiso(request.user, "ventas", "ver")
        ):
            raise PermissionDenied("No tenés permiso para esta acción.")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, pk):
        venta = get_object_or_404(
            Venta.objects.select_related("cliente", "caja", "cuenta_cobro"),
            pk=pk,
            estado=EstadoVenta.COBRADA,
        )
        if venta.tipo_comprobante != self.tipo:
            raise Http404()
        iva = liquidar_iva(venta)
        lineas = lineas_vista(venta)
        ahora = timezone.localtime()
        return render(
            request,
            self.template_name,
            {
                "venta": venta,
                "lineas": lineas,
                "iva": iva,
                "hora_txt": ahora.strftime("%H:%M"),
                "subtotal_txt": _dinero(iva.subtotal),
                "descuento_txt": _dinero(iva.descuento),
                "total_txt": _dinero(iva.total),
                "recibido_txt": _dinero(venta.importe_recibido or 0),
                "vuelto_txt": _dinero(vuelto_venta(venta)),
                "gravadas_10_txt": _dinero(iva.gravadas_10),
                "iva_10_txt": _dinero(iva.iva_10),
                "gravadas_5_txt": _dinero(iva.gravadas_5),
                "iva_5_txt": _dinero(iva.iva_5),
                "exentas_txt": _dinero(iva.exentas),
            },
        )


class TicketView(ComprobanteView):
    tipo = TipoComprobante.TICKET
    template_name = "ventas/ticket.html"


class FacturaView(ComprobanteView):
    tipo = TipoComprobante.FACTURA
    template_name = "ventas/factura.html"

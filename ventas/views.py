from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from core.cantidad import formatear_cantidad
from core.mantenimiento import (
    MantenimientoCreateView,
    MantenimientoDeleteView,
    MantenimientoListView,
    MantenimientoUpdateView,
)
from core.moneda import SIMBOLO, formatear_guaranies, interpretar_guaranies
from cuentas.models import Cuenta
from inventario.models import Item, UnidadMedida
from personas.models import Persona
from ventas.cobro import (
    actualizar_cabecera,
    agregar_producto,
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
    comprobantes_emitibles,
    confirmar,
    cuentas_para_medio,
    formatear_porcentaje,
    importes_rapidos,
    lineas_vista,
    liquidar_iva,
    medios_disponibles,
    motivo_emision,
    proximo_numero,
    puede_emitir,
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
    TipoComprobante,
    Venta,
    VentaDetalle,
)
from ventas.tables import TimbradoTable


def _dinero(valor) -> str:
    return f"{SIMBOLO} {formatear_guaranies(valor)}"


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
    page_title = "Timbrados"
    eyebrow = "Caja"
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


class TimbradoCreateView(TimbradoMantenimiento, MantenimientoCreateView):
    list_view_class = TimbradoListView


class TimbradoUpdateView(TimbradoMantenimiento, MantenimientoUpdateView):
    list_view_class = TimbradoListView


class TimbradoDeleteView(TimbradoMantenimiento, MantenimientoDeleteView):
    pass


class PuntoVentaView(LoginRequiredMixin, View):
    def get(self, request):
        venta = borrador(request.user)
        return render(request, "ventas/punto_de_venta.html", self._contexto(venta))

    def post(self, request):
        venta = borrador(request.user)
        try:
            self._aplicar(request, venta)
        except ValidationError as exc:
            messages.error(request, _error(exc))
            return redirect("punto_de_venta")
        if request.POST.get("guardar"):
            messages.success(request, "La venta quedó guardada.")
            return redirect("home")
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
            descuento_pct = (venta.descuento * Decimal("100") / subtotal).quantize(
                Decimal("0.01")
            )
        else:
            descuento_pct = Decimal("0")
        emitibles = comprobantes_emitibles()
        tipos_emitibles = {tipo for tipo, _etiqueta in emitibles}
        if venta.tipo_comprobante not in tipos_emitibles:
            comprobantes = [
                (venta.tipo_comprobante, venta.get_tipo_comprobante_display()),
                *emitibles,
            ]
        else:
            comprobantes = emitibles
        return {
            "venta": venta,
            "lineas": lineas,
            "iva": iva,
            "cajas": cajas(),
            "cuentas_cobro": cuentas_para_medio(venta.medio, venta.caja),
            "medios": medios_disponibles(venta.medio),
            "comprobantes": comprobantes,
            "puede_emitir": puede_emitir(punto),
            "emision_motivo": motivo_emision(punto),
            "proximo_numero": proximo_numero(venta.tipo_comprobante),
            "punto": punto,
            "subtotal": subtotal,
            "total": total,
            "vuelto": vuelto_venta(venta),
            "rapidos": [
                {"valor": monto, "txt": formatear_guaranies(monto)}
                for monto in importes_rapidos(total)
            ],
            "subtotal_entero": int(subtotal),
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
            "cliente_label": (str(venta.cliente) if venta.cliente_id else ""),
            "caja_label": venta.caja.nombre_corto if venta.caja_id else "Sin caja",
            "cliente_ocasional": cliente_ocasional(),
        }


class BuscarProductosView(LoginRequiredMixin, View):
    def get(self, request):
        query = request.GET.get("q", "")
        resultados = []
        for item in buscar_productos(query):
            resultados.append(
                {
                    "id": item.pk,
                    "descripcion": item.descripcion,
                    "codigo": item.codigo_barra or "",
                    "precio": _dinero(item.precio or 0),
                    "unidad": item.unidad_medida.simbolo,
                }
            )
        return JsonResponse({"resultados": resultados})


class BuscarClientesView(LoginRequiredMixin, View):
    def get(self, request):
        query = request.GET.get("q", "")
        return JsonResponse({"resultados": buscar_clientes_pos(query)})

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


class AgregarProductoView(LoginRequiredMixin, View):
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


class LineaVentaView(LoginRequiredMixin, View):
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
                    cambiar_cantidad(detalle, Decimal(request.POST.get("cantidad")))
        except ValidationError as exc:
            messages.error(request, _error(exc))
        return redirect("punto_de_venta")


class ConfirmarVentaView(LoginRequiredMixin, View):
    def post(self, request):
        venta = borrador(request.user)
        try:
            PuntoVentaView()._aplicar(request, venta)
            venta.refresh_from_db()
            venta = confirmar(venta)
        except ValidationError as exc:
            messages.error(request, _error(exc))
            return redirect("punto_de_venta")
        if venta.tipo_comprobante == TipoComprobante.FACTURA:
            return redirect("venta_factura", pk=venta.pk)
        return redirect("venta_ticket", pk=venta.pk)


class CancelarVentaView(LoginRequiredMixin, View):
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

    def get(self, request, pk):
        venta = get_object_or_404(
            Venta.objects.select_related("cliente", "caja", "cuenta_cobro"),
            pk=pk,
            usuario=request.user,
            estado=EstadoVenta.COBRADA,
        )
        if venta.tipo_comprobante != self.tipo:
            raise Http404()
        iva = liquidar_iva(venta)
        lineas = lineas_vista(venta)
        return render(
            request,
            self.template_name,
            {
                "venta": venta,
                "lineas": lineas,
                "iva": iva,
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

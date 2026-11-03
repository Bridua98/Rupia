from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from core.cantidad import formatear_cantidad
from core.moneda import SIMBOLO, formatear_guaranies, interpretar_guaranies
from cuentas.models import Cuenta
from inventario.models import Item, UnidadMedida
from personas.models import Persona
from ventas.cobro import (
    actualizar_cabecera,
    agregar_producto,
    borrador,
    buscar_clientes,
    buscar_productos,
    cajas,
    cambiar_cantidad,
    cambiar_unidad,
    cancelar,
    confirmar,
    cuentas_para_medio,
    importes_rapidos,
    lineas_vista,
    liquidar_iva,
    proximo_numero,
    punto_para,
    quitar_linea,
    subtotal_venta,
    total_venta,
    vuelto_venta,
)
from ventas.models import EstadoVenta, MedioPago, TipoComprobante, Venta, VentaDetalle


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

    def _aplicar(self, request, venta):
        datos = request.POST
        caja = None
        if datos.get("caja"):
            caja = get_object_or_404(Cuenta, pk=datos.get("caja"))
        cuenta = None
        if datos.get("cuenta_cobro"):
            cuenta = get_object_or_404(Cuenta, pk=datos.get("cuenta_cobro"))
        cliente = None
        consumidor = datos.get("consumidor_final") == "1"
        if datos.get("cliente") and not consumidor:
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
        punto = punto_para(venta.tipo_comprobante)
        return {
            "venta": venta,
            "lineas": lineas,
            "iva": iva,
            "cajas": cajas(),
            "cuentas_cobro": cuentas_para_medio(venta.medio, venta.caja),
            "medios": MedioPago.choices,
            "comprobantes": TipoComprobante.choices,
            "proximo_numero": proximo_numero(venta.tipo_comprobante),
            "punto": punto,
            "subtotal": subtotal,
            "total": total,
            "vuelto": vuelto_venta(venta),
            "rapidos": [
                {"valor": monto, "txt": formatear_guaranies(monto)}
                for monto in importes_rapidos(total)
            ],
            "subtotal_txt": _dinero(subtotal),
            "total_txt": _dinero(total),
            "descuento_txt": formatear_guaranies(venta.descuento or 0),
            "recibido_txt": formatear_guaranies(venta.importe_recibido or 0),
            "vuelto_txt": _dinero(vuelto_venta(venta)),
            "unidades_txt": formatear_cantidad(
                sum((linea.cantidad for linea in lineas), Decimal("0"))
            ),
            "cliente_label": (str(venta.cliente) if venta.cliente_id else "Consumidor final"),
            "caja_label": venta.caja.nombre_corto if venta.caja_id else "Sin caja",
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
        resultados = [
            {
                "id": persona.pk,
                "label": str(persona),
            }
            for persona in buscar_clientes(query)
        ]
        return JsonResponse({"resultados": resultados})


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

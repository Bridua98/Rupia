from collections import OrderedDict
from decimal import Decimal
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Prefetch, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from configuracion.permisos import PermisoRequeridoMixin, tiene_permiso
from core.cantidad import formatear_cantidad
from core.moneda import formatear_guaranies
from inventario.models import Item
from mesas import comandas as servicio
from mesas.forms import CuentaForm
from mesas.models import Comanda, ComandaDetalle, EstadoComanda, Mesa, Ronda
from mesas.views import ModuloMesasMixin
from ventas.cobro import buscar_clientes, buscar_productos
from ventas.models import PuntoExpedicion

CERO = Decimal("0")


def _error(exc: ValidationError) -> str:
    return exc.messages[0] if exc.messages else "No se pudo completar."


def _pk(raw):
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _gs(valor) -> str:
    return f"Gs. {formatear_guaranies(valor or CERO)}"


def _hace(desde) -> str:
    minutos = max(0, int((timezone.now() - desde).total_seconds() // 60))
    if minutos < 60:
        return f"{minutos} min"
    horas, resto = divmod(minutos, 60)
    return f"{horas} h {resto:02d} min"


def _hora(valor) -> str:
    return timezone.localtime(valor).strftime("%H:%M")


def _total_expr():
    return Sum(
        ExpressionWrapper(
            F("detalles__precio") * F("detalles__cantidad"),
            output_field=DecimalField(max_digits=18, decimal_places=3),
        ),
        filter=Q(detalles__anulado=False),
    )


def _comandas_activas_resumen():
    return (
        servicio.comandas_activas()
        .select_related("mesa", "cliente", "mozo")
        .annotate(
            total_consumo=_total_expr(),
            sin_enviar=Count(
                "detalles",
                filter=Q(detalles__anulado=False, detalles__ronda__isnull=True),
            ),
        )
    )


def _tarjeta(comanda):
    return {
        "comanda": comanda,
        "total_txt": _gs(comanda.total_consumo),
        "hace": _hace(comanda.abierta_en),
        "pidio_cuenta": comanda.estado == EstadoComanda.CUENTA_PEDIDA,
        "sin_enviar": comanda.sin_enviar,
    }


class ComandasView(LoginRequiredMixin, ModuloMesasMixin, PermisoRequeridoMixin, View):
    permiso_formulario = "comandas"
    permiso_accion = "ver"

    def comanda(self, pk):
        return get_object_or_404(
            Comanda.objects.select_related("mesa", "cliente", "mozo"),
            pk=pk,
        )

    def volver(self, comanda, **params):
        destino = reverse("comanda_detalle", args=[comanda.pk])
        params = {clave: valor for clave, valor in params.items() if valor}
        return redirect(f"{destino}?{urlencode(params)}" if params else destino)


# --- Tablero -----------------------------------------------------------------


class TableroView(ComandasView):
    def get(self, request):
        contexto = self.contexto(request)
        if request.GET.get("parcial"):
            return render(request, "mesas/tablero_contenido.html", contexto)
        return render(request, "mesas/tablero.html", contexto)

    def contexto(self, request):
        activas = list(_comandas_activas_resumen().order_by("abierta_en"))
        por_mesa = {comanda.mesa_id: comanda for comanda in activas if comanda.mesa_id}
        zonas = OrderedDict()
        for mesa in Mesa.objects.filter(activa=True).order_by("zona", "orden", "nombre"):
            comanda = por_mesa.get(mesa.pk)
            zonas.setdefault(mesa.zona or "", []).append(
                {"mesa": mesa, **(_tarjeta(comanda) if comanda else {"comanda": None})}
            )
        a_nombre = [_tarjeta(comanda) for comanda in activas if not comanda.mesa_id]
        ocupadas = sum(1 for comanda in activas if comanda.mesa_id)
        total_mesas = sum(len(mesas) for mesas in zonas.values())
        return {
            "zonas": zonas,
            "a_nombre": a_nombre,
            "ocupadas": ocupadas,
            "libres": total_mesas - ocupadas,
            "pidieron_cuenta": sum(
                1 for comanda in activas if comanda.estado == EstadoComanda.CUENTA_PEDIDA
            ),
            "puede_abrir": tiene_permiso(request.user, "comandas", "alta"),
            "cuenta_form": CuentaForm(),
        }


class AbrirComandaView(ComandasView):
    permiso_accion = "alta"

    def post(self, request):
        mesa_pk = _pk(request.POST.get("mesa"))
        if mesa_pk:
            mesa = get_object_or_404(Mesa, pk=mesa_pk)
            ocupada = servicio.comanda_de_mesa(mesa)
            if ocupada:
                messages.info(request, f"La mesa {mesa.nombre} ya estaba abierta.")
                return self.volver(ocupada)
            try:
                comanda = servicio.abrir(usuario=request.user, mesa=mesa)
            except ValidationError as exc:
                messages.error(request, _error(exc))
                return redirect("mesas_tablero")
            return self.volver(comanda)
        form = CuentaForm(request.POST)
        if not form.is_valid():
            errores = [error for lista in form.errors.values() for error in lista]
            messages.error(request, errores[0] if errores else "Revisá los datos de la cuenta.")
            return redirect("mesas_tablero")
        try:
            comanda = servicio.abrir(
                usuario=request.user,
                nombre=form.cleaned_data["nombre"],
                cliente=form.cleaned_data.get("cliente"),
                personas=form.cleaned_data.get("personas"),
            )
        except ValidationError as exc:
            messages.error(request, _error(exc))
            return redirect("mesas_tablero")
        return self.volver(comanda)


class BuscarClientesView(ComandasView):
    def get(self, request):
        resultados = [
            {"id": persona.pk, "label": str(persona)}
            for persona in buscar_clientes(request.GET.get("q", ""))
        ]
        return JsonResponse({"results": resultados, "resultados": resultados})


# --- Comanda -----------------------------------------------------------------


def _linea(detalle):
    return {
        "detalle": detalle,
        "cantidad_txt": formatear_cantidad(detalle.cantidad),
        "precio_txt": _gs(detalle.precio),
        "subtotal_txt": _gs(detalle.precio * detalle.cantidad),
    }


class ComandaDetalleView(ComandasView):
    def get(self, request, pk):
        comanda = self.comanda(pk)
        query = request.GET.get("q", "").strip()
        resultados = buscar_productos(query, limite=12) if query and comanda.activa else []
        detalles = comanda.detalles.select_related("item", "unidad_medida", "sector")
        pendientes = [_linea(d) for d in detalles if d.ronda_id is None and not d.anulado]
        rondas = []
        for ronda in comanda.rondas.select_related("enviada_por").prefetch_related(
            Prefetch(
                "detalles",
                queryset=ComandaDetalle.objects.select_related(
                    "item", "unidad_medida", "sector"
                ).prefetch_related("anulaciones"),
            )
        ):
            rondas.append(
                {
                    "ronda": ronda,
                    "hora": _hora(ronda.enviada_en),
                    "lineas": [_linea(d) for d in ronda.detalles.all()],
                }
            )
        rondas.reverse()
        total = servicio.total(comanda)
        return render(
            request,
            "mesas/comanda.html",
            {
                "comanda": comanda,
                "query": query,
                "resultados": [
                    {"item": item, "precio_txt": _gs(item.precio)} for item in resultados
                ],
                "pendientes": pendientes,
                "rondas": rondas,
                "total_txt": _gs(total),
                "hace": _hace(comanda.abierta_en),
                "abierta_hora": _hora(comanda.abierta_en),
                "puede_cargar": comanda.activa and tiene_permiso(request.user, "comandas", "alta"),
                "puede_anular": comanda.activa
                and tiene_permiso(request.user, "comandas", "anular"),
                "hay_enviados": any(r["lineas"] for r in rondas),
                "datos_form": CuentaForm(
                    initial={
                        "nombre": comanda.nombre,
                        "cliente": comanda.cliente_id,
                        "personas": comanda.personas,
                    },
                    exigir_destino=comanda.mesa_id is None,
                ),
            },
        )


class AgregarView(ComandasView):
    permiso_accion = "alta"

    def post(self, request, pk):
        comanda = self.comanda(pk)
        query = request.POST.get("q", "")
        item = get_object_or_404(Item, pk=_pk(request.POST.get("item")))
        try:
            carga = servicio.agregar(
                comanda,
                item,
                usuario=request.user,
                cantidad=request.POST.get("cantidad") or "1",
                nota=request.POST.get("nota", ""),
            )
        except ValidationError as exc:
            messages.error(request, _error(exc))
            return self.volver(comanda, q=query)
        if carga.aviso:
            messages.warning(request, carga.aviso)
        return self.volver(comanda, q=query)


class LineaView(ComandasView):
    permiso_accion = "alta"

    def post(self, request, pk):
        detalle = get_object_or_404(ComandaDetalle.objects.select_related("comanda"), pk=pk)
        accion = request.POST.get("accion")
        try:
            if accion == "mas":
                servicio.cambiar_pendiente(detalle, cantidad=detalle.cantidad + 1)
            elif accion == "menos":
                servicio.cambiar_pendiente(detalle, cantidad=detalle.cantidad - 1)
            elif accion == "quitar":
                servicio.quitar_pendiente(detalle)
            elif accion == "nota":
                servicio.cambiar_pendiente(detalle, nota=request.POST.get("nota", ""))
        except ValidationError as exc:
            messages.error(request, _error(exc))
        return self.volver(detalle.comanda)


class AnularLineaView(ComandasView):
    permiso_accion = "anular"

    def post(self, request, pk):
        detalle = get_object_or_404(ComandaDetalle.objects.select_related("comanda"), pk=pk)
        try:
            servicio.anular_linea(
                detalle,
                usuario=request.user,
                motivo=request.POST.get("motivo", ""),
                cantidad=request.POST.get("cantidad") or None,
            )
            messages.success(request, f"Se anuló {detalle.item.descripcion}.")
        except ValidationError as exc:
            messages.error(request, _error(exc))
        return self.volver(detalle.comanda)


class EnviarView(ComandasView):
    permiso_accion = "alta"

    def post(self, request, pk):
        comanda = self.comanda(pk)
        try:
            ronda = servicio.enviar(comanda, usuario=request.user)
        except ValidationError as exc:
            messages.error(request, _error(exc))
            return self.volver(comanda)
        sectores = list(ronda.envios.values_list("sector__nombre", flat=True))
        if sectores:
            messages.success(request, f"Ronda {ronda.numero} enviada a {', '.join(sectores)}.")
        else:
            messages.success(request, f"Ronda {ronda.numero} registrada.")
        return redirect("mesas_tablero")


class DatosView(ComandasView):
    permiso_accion = "alta"

    def post(self, request, pk):
        comanda = self.comanda(pk)
        form = CuentaForm(request.POST, exigir_destino=comanda.mesa_id is None)
        if not form.is_valid():
            errores = [error for lista in form.errors.values() for error in lista]
            messages.error(request, errores[0] if errores else "Revisá los datos.")
            return self.volver(comanda)
        cliente = form.cleaned_data.get("cliente")
        try:
            servicio.cambiar_datos(
                comanda,
                nombre=form.cleaned_data["nombre"],
                cliente=cliente,
                quitar_cliente=cliente is None,
                personas=form.cleaned_data.get("personas"),
            )
            messages.success(request, "Los datos de la cuenta quedaron guardados.")
        except ValidationError as exc:
            messages.error(request, _error(exc))
        return self.volver(comanda)


class PedirCuentaView(ComandasView):
    permiso_accion = "alta"

    def post(self, request, pk):
        comanda = self.comanda(pk)
        try:
            servicio.pedir_cuenta(comanda)
        except ValidationError as exc:
            messages.error(request, _error(exc))
            return self.volver(comanda)
        return redirect("comanda_precuenta", pk=comanda.pk)


class AnularComandaView(ComandasView):
    permiso_accion = "anular"

    def post(self, request, pk):
        comanda = self.comanda(pk)
        try:
            servicio.anular_comanda(
                comanda, usuario=request.user, motivo=request.POST.get("motivo", "")
            )
        except ValidationError as exc:
            messages.error(request, _error(exc))
            return self.volver(comanda)
        messages.success(request, f"{comanda.titulo}: la cuenta quedó anulada.")
        return redirect("mesas_tablero")


class DescartarView(ComandasView):
    permiso_accion = "alta"

    def post(self, request, pk):
        comanda = self.comanda(pk)
        titulo = comanda.titulo
        try:
            servicio.descartar(comanda)
        except ValidationError as exc:
            messages.error(request, _error(exc))
            return self.volver(comanda)
        messages.success(request, f"{titulo} quedó libre.")
        return redirect("mesas_tablero")


# --- Pre-cuenta --------------------------------------------------------------


class PrecuentaView(ComandasView):
    def get(self, request, pk):
        comanda = self.comanda(pk)
        agrupadas = OrderedDict()
        for detalle in (
            servicio.lineas_vigentes(comanda)
            .filter(ronda__isnull=False)
            .select_related("item", "unidad_medida")
            .order_by("id")
        ):
            clave = (detalle.item_id, detalle.unidad_medida_id, detalle.precio)
            fila = agrupadas.setdefault(
                clave,
                {
                    "descripcion": detalle.item.descripcion,
                    "cantidad": CERO,
                    "precio": detalle.precio,
                },
            )
            fila["cantidad"] += detalle.cantidad
        lineas = [
            {
                "descripcion": fila["descripcion"],
                "cantidad_txt": formatear_cantidad(fila["cantidad"]),
                "subtotal_txt": formatear_guaranies(fila["precio"] * fila["cantidad"]),
            }
            for fila in agrupadas.values()
        ]
        total = sum((fila["precio"] * fila["cantidad"] for fila in agrupadas.values()), CERO)
        por_persona = ""
        if comanda.personas and comanda.personas > 1 and total:
            por_persona = _gs(total / comanda.personas)
        emisor = PuntoExpedicion.objects.filter(habilitado=True).order_by("tipo").first()
        return render(
            request,
            "mesas/precuenta.html",
            {
                "comanda": comanda,
                "lineas": lineas,
                "total_txt": _gs(total),
                "por_persona": por_persona,
                "emisor": emisor,
                "ahora": timezone.localtime(),
                "rondas": Ronda.objects.filter(comanda=comanda).count(),
            },
        )

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views import View

from configuracion.permisos import PermisoRequeridoMixin
from core.cantidad import formatear_cantidad
from mesas import puesto as servicio
from mesas.models import EnvioSector, EstadoEnvio, Sector, TipoEnvio
from mesas.views import ModuloMesasMixin

# En cocina "2 Milanesa" se entiende solo; la unidad se muestra cuando no es por unidad.
UNIDADES_OBVIAS = {"u", "un", "uni", "und", "unid", "unidad", "unidades"}


def _unidad(simbolo):
    return "" if simbolo.strip().rstrip(".").lower() in UNIDADES_OBVIAS else simbolo


def _nombre(usuario):
    return usuario.first_name or usuario.username


def _espera(envio):
    origen = envio.empezado_en or envio.creado_en
    return max(0, int((timezone.now() - origen).total_seconds() // 60))


def _demorado(envio):
    if envio.tipo != TipoEnvio.PEDIDO:
        return False
    if envio.sector.exige_empezar and envio.empezado_en is None:
        return False
    origen = envio.empezado_en or envio.creado_en
    espera = max(0, int((timezone.now() - origen).total_seconds() // 60))
    return espera >= envio.sector.minutos_demora


def _vista(envio):
    """Lo que hace falta para mostrar o imprimir un envío."""
    espera = _espera(envio)
    comanda = envio.comanda
    return {
        "envio": envio,
        "anulacion": envio.tipo == TipoEnvio.ANULACION,
        "titulo": comanda.titulo,
        "ronda": envio.ronda.numero if envio.ronda_id else None,
        "hora": timezone.localtime(envio.creado_en).strftime("%H:%M"),
        "fecha": timezone.localtime(envio.creado_en).strftime("%d/%m/%Y"),
        "mozo": _nombre(envio.usuario),
        "personas": comanda.personas,
        "listo_hora": (
            timezone.localtime(envio.listo_en).strftime("%H:%M") if envio.listo_en else ""
        ),
        "espera": espera,
        "demorado": _demorado(envio),
        "exige_empezar": envio.sector.exige_empezar,
        "sin_empezar": envio.sector.exige_empezar
        and envio.estado in (EstadoEnvio.PENDIENTE, EstadoEnvio.IMPRESO),
        "lineas": [
            {
                "cantidad": formatear_cantidad(linea.cantidad),
                "unidad": _unidad(linea.unidad),
                "descripcion": linea.descripcion,
                "nota": linea.nota,
            }
            for linea in envio.lineas.all()
        ],
    }


def _ticket(request, envio):
    return render_to_string("mesas/puesto_ticket.html", {"t": _vista(envio)}, request=request)


class PuestoBaseView(LoginRequiredMixin, ModuloMesasMixin, PermisoRequeridoMixin, View):
    permiso_formulario = "puesto_sector"
    permiso_accion = "ver"

    def sector(self, pk):
        return get_object_or_404(Sector, pk=pk, activo=True)

    def envio(self, pk):
        return get_object_or_404(
            EnvioSector.objects.select_related("sector"), pk=pk, sector__activo=True
        )


class PuestoElegirView(PuestoBaseView):
    def get(self, request):
        sectores = list(Sector.objects.filter(activo=True).order_by("nombre"))
        if len(sectores) == 1:
            return redirect("puesto_sector", pk=sectores[0].pk)
        return render(request, "mesas/puesto_elegir.html", {"sectores": sectores})


def _contexto(sector):
    return {
        "sector": sector,
        "abiertos": [_vista(envio) for envio in servicio.abiertos(sector)],
        "preparacion": [_vista(envio) for envio in servicio.en_preparacion(sector)],
        "listos": [_vista(envio) for envio in servicio.recientes_listos(sector)],
        "listos_hoy": servicio.listos_hoy(sector),
    }


class PuestoView(PuestoBaseView):
    def get(self, request, pk):
        sector = self.sector(pk)
        contexto = _contexto(sector)
        if request.GET.get("parcial"):
            return render(request, "mesas/puesto_cola.html", contexto)
        return render(request, "mesas/puesto.html", contexto)


class TomarView(PuestoBaseView):
    """La pantalla pregunta si hay algo nuevo; lo que recibe ya quedó reservado."""

    def post(self, request, pk):
        sector = self.sector(pk)
        tomados = servicio.tomar_pendientes(sector)
        return JsonResponse(
            {"tickets": [{"id": envio.pk, "html": _ticket(request, envio)} for envio in tomados]}
        )


class ImprimirView(PuestoBaseView):
    def post(self, request, pk):
        envio = servicio.imprimir(self.envio(pk))
        return JsonResponse({"id": envio.pk, "html": _ticket(request, envio)})


class EmpezarView(PuestoBaseView):
    def post(self, request, pk):
        envio = self.envio(pk)
        try:
            servicio.empezar(envio)
        except ValidationError as exc:
            messages.info(request, exc.messages[0])
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": True})
        return redirect("puesto_sector", pk=envio.sector_id)


class ListoView(PuestoBaseView):
    def post(self, request, pk):
        envio = self.envio(pk)
        try:
            servicio.marcar_listo(envio)
        except ValidationError as exc:
            messages.info(request, exc.messages[0])
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": True})
        return redirect("puesto_sector", pk=envio.sector_id)


class DeshacerListoView(PuestoBaseView):
    def post(self, request, pk):
        envio = self.envio(pk)
        try:
            servicio.volver_a_cola(envio)
        except ValidationError as exc:
            messages.info(request, exc.messages[0])
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": True})
        return redirect("puesto_sector", pk=envio.sector_id)

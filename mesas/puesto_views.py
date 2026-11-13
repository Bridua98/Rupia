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
from mesas.models import EnvioSector, Sector, TipoEnvio
from mesas.views import ModuloMesasMixin

MINUTOS_DEMORA = 15
# En cocina "2 Milanesa" se entiende solo; la unidad se muestra cuando no es por unidad.
UNIDADES_OBVIAS = {"u", "un", "uni", "und", "unid", "unidad", "unidades"}


def _unidad(simbolo):
    return "" if simbolo.strip().rstrip(".").lower() in UNIDADES_OBVIAS else simbolo


def _nombre(usuario):
    return usuario.first_name or usuario.username


def _vista(envio):
    """Lo que hace falta para mostrar o imprimir un envío."""
    espera = max(0, int((timezone.now() - envio.creado_en).total_seconds() // 60))
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
        "espera": espera,
        "demorado": espera >= MINUTOS_DEMORA and envio.tipo == TipoEnvio.PEDIDO,
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


class PuestoView(PuestoBaseView):
    def get(self, request, pk):
        sector = self.sector(pk)
        contexto = {
            "sector": sector,
            "cola": [_vista(envio) for envio in servicio.cola(sector)],
            "listos": [_vista(envio) for envio in servicio.recientes_listos(sector)],
        }
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

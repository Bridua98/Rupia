import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from compras.reporte_gastos import liquidar_linea
from core.cantidad import formatear_cantidad, html_cantidad
from core.listado import (
    apply_filters,
    apply_search,
    filter_specs_for,
    filter_values,
    search_fields_for,
)
from core.mantenimiento import MantenimientoListView
from core.moneda import html_guaranies, mostrar_guaranies
from cuentas.models import Cuenta
from inventario.models import Item, ItemCategoria, Marca, TipoItem
from inventario.precios import redondear_guarani
from negocio.models import UnidadNegocio
from personas.models import Persona
from ventas.models import EstadoVenta, MedioPago, TipoComprobante, VentaDetalle
from ventas.tablero import _netos_lineas
from ventas.tables import ReporteVentasAgrupadoTable, ReporteVentasDetalleTable

AGRUPAR_DETALLE = ""
AGRUPAR_CLIENTE = "cliente"
AGRUPAR_PRODUCTO = "producto"
AGRUPAR_CATEGORIA = "categoria"
AGRUPAR_MARCA = "marca"
AGRUPAR_UNIDAD = "unidad"
AGRUPAR_CAJA = "caja"
AGRUPAR_MEDIO = "medio"
AGRUPAR_USUARIO = "usuario"
AGRUPAR_TIPO = "tipo"

AGRUPAR_CHOICES = (
    (AGRUPAR_DETALLE, "Sin agrupar (cada línea)"),
    (AGRUPAR_CLIENTE, "Por cliente"),
    (AGRUPAR_PRODUCTO, "Por producto"),
    (AGRUPAR_CATEGORIA, "Por categoría"),
    (AGRUPAR_MARCA, "Por marca"),
    (AGRUPAR_UNIDAD, "Por unidad de negocio"),
    (AGRUPAR_CAJA, "Por caja"),
    (AGRUPAR_MEDIO, "Por medio de pago"),
    (AGRUPAR_USUARIO, "Por usuario"),
    (AGRUPAR_TIPO, "Por tipo de comprobante"),
)

AGRUPAR_LABELS = {
    AGRUPAR_CLIENTE: "Por cliente",
    AGRUPAR_PRODUCTO: "Por producto",
    AGRUPAR_CATEGORIA: "Por categoría",
    AGRUPAR_MARCA: "Por marca",
    AGRUPAR_UNIDAD: "Por unidad de negocio",
    AGRUPAR_CAJA: "Por caja",
    AGRUPAR_MEDIO: "Por medio de pago",
    AGRUPAR_USUARIO: "Por usuario",
    AGRUPAR_TIPO: "Por tipo de comprobante",
}

CERO = Decimal("0")
CIEN = Decimal("100")
RADIO_ANILLO = 62
LARGO_ANILLO = 2 * math.pi * RADIO_ANILLO
DIAS_SERIE_DIARIA = 45
COLORES_MEDIO = {
    MedioPago.EFECTIVO: "#1e8a4c",
    MedioPago.TRANSFERENCIA: "#3b6fd8",
    MedioPago.TARJETA: "#e08a2f",
    MedioPago.QR: "#7b5ea7",
}


@dataclass
class FilaVenta:
    pk: int
    venta_id: int
    fecha: object
    comprobante: str
    tipo_comprobante: str
    tipo_comprobante_id: str
    cliente: str
    cliente_id: int
    cliente_detalle: str
    timbrado: str
    caja: str
    caja_id: int
    caja_corto: str
    cuenta_cobro: str
    medio: str
    medio_id: str
    producto: str
    producto_id: int
    categoria: str
    categoria_id: int
    marca: str
    marca_id: int
    unidad_negocio: str
    unidad_negocio_id: int
    unidad_abreviado: str
    usuario: str
    usuario_id: int
    usuario_detalle: str
    cantidad: Decimal
    tasa_iva: int
    gravado: Decimal
    iva: Decimal
    subtotal: Decimal


@dataclass
class FilaVentaAgrupada:
    pk: object
    etiqueta: str
    detalle: str
    lineas: int
    cantidad: Decimal
    gravado: Decimal
    iva: Decimal
    subtotal: Decimal


@dataclass
class VariacionPanel:
    texto: str
    sentido: str


@dataclass
class SeriePanel:
    puntos: str
    area: str
    vacia: bool


@dataclass
class IndicadorPanel:
    etiqueta: str
    valor_txt: str
    meta: str = ""
    serie: SeriePanel | None = None
    periodo: VariacionPanel | None = None
    tono: str = ""


@dataclass
class PorcionPanel:
    nombre: str
    importe: Decimal
    importe_txt: str
    porcentaje: int
    color: str
    trazo: str = ""
    offset: str = "0"


@dataclass
class PanelVentas:
    desde: str
    hasta: str
    total: IndicadorPanel
    gravado: IndicadorPanel
    iva: IndicadorPanel
    comprobantes: IndicadorPanel
    medios: list
    hay_medios: bool
    evolucion: dict


def _parse_fecha(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _texto_fecha(value) -> str:
    dia = _parse_fecha(value)
    return dia.strftime("%d/%m/%Y") if dia else ""


def _variacion(actual: Decimal, anterior: Decimal) -> VariacionPanel:
    if anterior == 0 and actual == 0:
        return VariacionPanel(texto="—", sentido="neutral")
    if anterior == 0:
        return VariacionPanel(texto="Nuevo", sentido="up" if actual > 0 else "down")
    porcentaje = redondear_guarani(((actual - anterior) / anterior) * CIEN)
    sentido = "up" if porcentaje > 0 else "down" if porcentaje < 0 else "neutral"
    signo = "+" if porcentaje > 0 else ""
    return VariacionPanel(texto=f"{signo}{int(porcentaje)}%", sentido=sentido)


def _serie_spark(valores: list[Decimal]) -> SeriePanel:
    if not any(valores):
        return SeriePanel(puntos="", area="", vacia=True)
    alto = 42
    ancho = 140
    n = len(valores)
    mx = max(valores)
    mn = min(valores)
    span = mx - mn if mx != mn else (mx or Decimal("1"))
    coords = []
    for i, valor in enumerate(valores):
        x = 0 if n == 1 else round(i * (ancho / (n - 1)), 2)
        y = round(alto - 3 - float((valor - mn) / span) * (alto - 6), 2)
        coords.append((x, y))
    puntos = " ".join(f"{x},{y}" for x, y in coords)
    area = f"0,{alto} {puntos} {coords[-1][0]},{alto}"
    return SeriePanel(puntos=puntos, area=area, vacia=False)


def _parte(valor: Decimal, total: Decimal) -> int:
    if total <= 0 or valor <= 0:
        return 0
    return int(redondear_guarani((valor / total) * CIEN))


def _trazar_anillo(porciones: list[PorcionPanel]) -> None:
    visibles = [porcion for porcion in porciones if porcion.porcentaje]
    separacion = 4 if len(visibles) > 1 else 0
    acumulado = 0.0
    for porcion in porciones:
        if not porcion.porcentaje:
            porcion.trazo = f"0 {LARGO_ANILLO:.3f}"
            porcion.offset = "0"
            continue
        largo = LARGO_ANILLO * porcion.porcentaje / 100
        dibujo = max(largo - separacion, 1)
        porcion.trazo = f"{dibujo:.3f} {LARGO_ANILLO:.3f}"
        porcion.offset = f"{-(acumulado + separacion / 2):.3f}"
        acumulado += largo


def _medios_dona(filas) -> list[PorcionPanel]:
    totales = {clave: CERO for clave, _nombre in MedioPago.choices}
    for fila in filas:
        if fila.medio_id in totales:
            totales[fila.medio_id] += fila.subtotal
    total = redondear_guarani(sum(totales.values(), CERO))
    porciones = []
    for clave, nombre in MedioPago.choices:
        importe = redondear_guarani(totales[clave])
        porciones.append(
            PorcionPanel(
                nombre,
                importe,
                mostrar_guaranies(importe),
                _parte(importe, total),
                COLORES_MEDIO[clave],
            )
        )
    ajuste = 100 - sum(porcion.porcentaje for porcion in porciones)
    if total > 0 and ajuste:
        mayor = max(porciones, key=lambda porcion: porcion.importe)
        mayor.porcentaje += ajuste
    _trazar_anillo(porciones)
    return porciones


def _mapa_importe(filas, getter) -> dict:
    acumulado = defaultdict(lambda: CERO)
    for fila in filas:
        acumulado[fila.fecha] += getter(fila)
    return dict(acumulado)


def _mapa_comprobantes(filas) -> dict:
    ids = defaultdict(set)
    for fila in filas:
        ids[fila.fecha].add(fila.venta_id)
    return {fecha: Decimal(len(ventas)) for fecha, ventas in ids.items()}


def _usar_semanas(desde: date, hasta: date) -> bool:
    return (hasta - desde).days + 1 > DIAS_SERIE_DIARIA


def _buckets(desde: date, hasta: date):
    if not _usar_semanas(desde, hasta):
        dia = desde
        while dia <= hasta:
            yield dia, dia, dia.strftime("%d/%m")
            dia += timedelta(days=1)
        return
    inicio = desde
    while inicio <= hasta:
        fin = min(inicio + timedelta(days=6), hasta)
        yield inicio, fin, inicio.strftime("%d/%m")
        inicio = fin + timedelta(days=1)


def _valores_rango(desde: date, hasta: date, por_fecha: dict) -> list[Decimal]:
    valores = []
    for inicio, fin, _etiqueta in _buckets(desde, hasta):
        total = CERO
        dia = inicio
        while dia <= fin:
            total += por_fecha.get(dia, CERO)
            dia += timedelta(days=1)
        valores.append(total)
    return valores


def _puntos_evolucion(desde: date, hasta: date, por_fecha: dict) -> list[dict]:
    puntos = []
    for inicio, fin, etiqueta in _buckets(desde, hasta):
        total = CERO
        dia = inicio
        while dia <= fin:
            total += por_fecha.get(dia, CERO)
            dia += timedelta(days=1)
        puntos.append({"e": etiqueta, "v": int(total), "vt": mostrar_guaranies(total)})
    return puntos


def _totales_filas(filas) -> dict:
    return {
        "cantidad": sum((fila.cantidad for fila in filas), CERO),
        "gravado": sum((fila.gravado for fila in filas), CERO),
        "iva": sum((fila.iva for fila in filas), CERO),
        "subtotal": sum((fila.subtotal for fila in filas), CERO),
        "comprobantes": Decimal(len({fila.venta_id for fila in filas})),
    }


def _indicador(etiqueta, valor, anterior, serie, formatear) -> IndicadorPanel:
    return IndicadorPanel(
        etiqueta=etiqueta,
        valor_txt=formatear(valor),
        serie=serie,
        periodo=_variacion(valor, anterior),
    )


def _nombre_usuario(usuario) -> tuple[str, int, str]:
    if usuario is None:
        return "Sin usuario", 0, ""
    nombre = (usuario.get_full_name() or "").strip() or usuario.username
    detalle = usuario.username if nombre != usuario.username else ""
    return nombre, usuario.pk, detalle


def _specs_detalle(view):
    return [spec for spec in filter_specs_for(view) if spec.get("kind") != "skip"]


def _grupo(fila: FilaVenta, modo: str):
    if modo == AGRUPAR_CLIENTE:
        etiqueta = fila.cliente if fila.cliente_id else "Sin cliente"
        return fila.cliente_id, etiqueta, fila.cliente_detalle
    if modo == AGRUPAR_PRODUCTO:
        return fila.producto_id, fila.producto, fila.categoria
    if modo == AGRUPAR_CATEGORIA:
        return fila.categoria_id, fila.categoria, ""
    if modo == AGRUPAR_MARCA:
        return fila.marca_id, fila.marca, ""
    if modo == AGRUPAR_UNIDAD:
        etiqueta = fila.unidad_negocio if fila.unidad_negocio_id else "Sin unidad de negocio"
        return fila.unidad_negocio_id, etiqueta, fila.unidad_abreviado
    if modo == AGRUPAR_CAJA:
        etiqueta = fila.caja if fila.caja_id else "Sin caja"
        return fila.caja_id, etiqueta, fila.caja_corto
    if modo == AGRUPAR_MEDIO:
        return fila.medio_id, fila.medio, ""
    if modo == AGRUPAR_USUARIO:
        return fila.usuario_id, fila.usuario, fila.usuario_detalle
    return fila.tipo_comprobante_id, fila.tipo_comprobante, ""


class ReporteVentasListView(MantenimientoListView):
    template_name = "ventas/reporte_ventas_list.html"
    model = VentaDetalle
    permiso_formulario = "reporte_ventas"
    page_title = "Informe de ventas"
    eyebrow = "Gestión"
    title = "Informe de ventas"
    create_label = ""
    show_create = False
    list_hint = (
        "Líneas de ventas cobradas. El descuento de la venta se reparte entre sus productos. "
        "El IVA está incluido en el total."
    )
    search_label = "Buscar"
    search_placeholder = "Buscar por producto, cliente, comprobante, caja o categoría..."
    search_fields = (
        "item__descripcion",
        "venta__numero_completo",
        "venta__cliente__razon_social",
        "venta__caja__descripcion",
        "item__categoria__descripcion",
        "item__marca__descripcion",
        "venta__usuario__username",
    )
    filters = (
        {
            "name": "fecha_desde",
            "label": "Desde",
            "kind": "date",
            "field": "venta__fecha",
            "lookup": "gte",
            "default": "month_start",
        },
        {
            "name": "fecha_hasta",
            "label": "Hasta",
            "kind": "date",
            "field": "venta__fecha",
            "lookup": "lte",
            "default": "today",
        },
        {
            "name": "venta__tipo_comprobante",
            "label": "Tipo de comprobante",
            "kind": "choice",
            "choices": TipoComprobante.choices,
        },
        {
            "name": "venta__medio",
            "label": "Medio de pago",
            "kind": "choice",
            "choices": MedioPago.choices,
        },
        {
            "name": "venta__caja",
            "label": "Caja",
            "kind": "fk",
            "queryset": lambda: Cuenta.objects.order_by("descripcion"),
        },
        {
            "name": "venta__cuenta_cobro",
            "label": "Cuenta de cobro",
            "kind": "fk",
            "queryset": lambda: Cuenta.objects.order_by("descripcion"),
        },
        {
            "name": "venta__cliente",
            "label": "Cliente",
            "kind": "fk",
            "queryset": lambda: Persona.objects.filter(es_cliente=True).order_by("razon_social"),
        },
        {
            "name": "item",
            "label": "Producto",
            "kind": "fk",
            "queryset": lambda: Item.objects.filter(tipo=TipoItem.PRODUCTO).order_by("descripcion"),
        },
        {
            "name": "item__categoria",
            "label": "Categoría",
            "kind": "fk",
            "queryset": lambda: ItemCategoria.objects.order_by("descripcion"),
        },
        {
            "name": "item__marca",
            "label": "Marca",
            "kind": "fk",
            "queryset": lambda: Marca.objects.order_by("descripcion"),
        },
        {
            "name": "item__unidad_negocio",
            "label": "Unidad de negocio",
            "kind": "fk",
            "queryset": lambda: UnidadNegocio.objects.order_by("descripcion"),
        },
        {
            "name": "venta__usuario",
            "label": "Usuario",
            "kind": "fk",
            "queryset": lambda: get_user_model().objects.order_by("username"),
        },
        {
            "name": "agrupar",
            "label": "Agrupar por",
            "kind": "skip",
            "choices": AGRUPAR_CHOICES,
        },
    )
    record_noun = "línea"
    order_by = ("-venta__fecha", "-venta_id", "id")
    list_url_name = "reporte_ventas"
    per_page = 15
    back_url_name = "home"
    print_url_name = "reporte_ventas_print"
    export_xlsx_url_name = "reporte_ventas_export_xlsx"
    export_pdf_url_name = "reporte_ventas_export_pdf"
    export_basename = "informe-ventas"
    export_totals = True
    selection_param = "reporte_sel"

    def agrupar(self):
        return filter_values(self.request, filter_specs_for(self)).get("agrupar", AGRUPAR_DETALLE)

    def detalles_queryset(self, valores=None):
        queryset = (
            VentaDetalle.objects.filter(venta__estado=EstadoVenta.COBRADA)
            .select_related(
                "venta",
                "venta__cliente",
                "venta__caja",
                "venta__cuenta_cobro",
                "venta__usuario",
                "item",
                "item__categoria",
                "item__marca",
                "item__unidad_negocio",
                "unidad_medida",
            )
            .order_by(*self.order_by)
        )
        queryset = apply_search(queryset, self.query(), search_fields_for(self))
        specs = _specs_detalle(self)
        if valores is None:
            valores = filter_values(self.request, specs)
        return apply_filters(queryset, valores, specs)

    def _detalle(self):
        if not hasattr(self, "_detalle_cache"):
            self._detalle_cache = self._armar_detalle()
        return self._detalle_cache

    def _armar_detalle(self, valores=None):
        filtrados = list(self.detalles_queryset(valores))
        if not filtrados:
            return []
        venta_ids = {detalle.venta_id for detalle in filtrados}
        hermanos = VentaDetalle.objects.filter(venta_id__in=venta_ids).select_related("venta")
        por_venta = defaultdict(list)
        for detalle in hermanos:
            por_venta[detalle.venta_id].append(detalle)
        netos = {}
        for lineas in por_venta.values():
            netos.update(_netos_lineas(lineas[0].venta, lineas))
        filas = []
        for detalle in filtrados:
            venta = detalle.venta
            item = detalle.item
            negocio = item.unidad_negocio
            caja = venta.caja
            cuenta = venta.cuenta_cobro
            cliente = venta.cliente
            usuario_nombre, usuario_id, usuario_detalle = _nombre_usuario(venta.usuario)
            neto = netos.get(detalle.pk, detalle.subtotal)
            gravado, iva = liquidar_linea(neto, detalle.tasa_iva)
            filas.append(
                FilaVenta(
                    pk=detalle.pk,
                    venta_id=venta.pk,
                    fecha=venta.fecha,
                    comprobante=venta.numero_completo or f"Venta {venta.pk}",
                    tipo_comprobante=venta.get_tipo_comprobante_display(),
                    tipo_comprobante_id=venta.tipo_comprobante,
                    cliente=cliente.razon_social if venta.cliente_id else "Sin cliente",
                    cliente_id=venta.cliente_id or 0,
                    cliente_detalle=cliente.documento if cliente else "",
                    timbrado=venta.timbrado or "—",
                    caja=caja.descripcion if caja else "Sin caja",
                    caja_id=venta.caja_id or 0,
                    caja_corto=caja.nombre_corto if caja else "",
                    cuenta_cobro=cuenta.descripcion if cuenta else "—",
                    medio=venta.get_medio_display(),
                    medio_id=venta.medio,
                    producto=item.descripcion,
                    producto_id=item.pk,
                    categoria=item.categoria.descripcion,
                    categoria_id=item.categoria_id,
                    marca=item.marca.descripcion,
                    marca_id=item.marca_id,
                    unidad_negocio=negocio.descripcion if negocio else "Sin unidad de negocio",
                    unidad_negocio_id=item.unidad_negocio_id or 0,
                    unidad_abreviado=negocio.abreviado if negocio else "",
                    usuario=usuario_nombre,
                    usuario_id=usuario_id,
                    usuario_detalle=usuario_detalle,
                    cantidad=detalle.cantidad,
                    tasa_iva=int(detalle.tasa_iva),
                    gravado=gravado,
                    iva=iva,
                    subtotal=neto,
                )
            )
        return filas

    def _filas_agrupadas(self, filas, modo):
        grupos = {}
        for fila in filas:
            clave, etiqueta, detalle = _grupo(fila, modo)
            grupo = grupos.get(clave)
            if grupo is None:
                grupo = FilaVentaAgrupada(
                    pk=clave or 0,
                    etiqueta=etiqueta,
                    detalle=detalle,
                    lineas=0,
                    cantidad=CERO,
                    gravado=CERO,
                    iva=CERO,
                    subtotal=CERO,
                )
                grupos[clave] = grupo
            grupo.lineas += 1
            grupo.cantidad += fila.cantidad
            grupo.gravado += fila.gravado
            grupo.iva += fila.iva
            grupo.subtotal += fila.subtotal
        return sorted(grupos.values(), key=lambda fila: fila.etiqueta.lower())

    def get_queryset(self):
        filas = self._detalle()
        modo = self.agrupar()
        if modo and modo != AGRUPAR_DETALLE:
            return self._filas_agrupadas(filas, modo)
        return filas

    @property
    def table_class(self):
        modo = self.agrupar()
        if modo and modo != AGRUPAR_DETALLE:
            return ReporteVentasAgrupadoTable
        return ReporteVentasDetalleTable

    def creating(self):
        return False

    def panel_pk(self):
        return None

    def get_table_kwargs(self):
        return {}

    def totales_raw(self):
        return _totales_filas(self._detalle())

    def _rango_actual(self):
        valores = filter_values(self.request, _specs_detalle(self))
        desde = _parse_fecha(valores.get("fecha_desde"))
        hasta = _parse_fecha(valores.get("fecha_hasta"))
        hoy = timezone.localdate()
        if desde is None:
            desde = hoy.replace(day=1)
        if hasta is None:
            hasta = hoy
        if hasta < desde:
            desde, hasta = hasta, desde
        return desde, hasta, valores

    def _detalle_anterior(self, desde, hasta, valores):
        dias = (hasta - desde).days + 1
        prev_hasta = desde - timedelta(days=1)
        prev_desde = prev_hasta - timedelta(days=dias - 1)
        anteriores = dict(valores)
        anteriores["fecha_desde"] = prev_desde.isoformat()
        anteriores["fecha_hasta"] = prev_hasta.isoformat()
        return self._armar_detalle(anteriores)

    def _panel(self):
        filas = self._detalle()
        desde, hasta, valores = self._rango_actual()
        actual = _totales_filas(filas)
        anterior = _totales_filas(self._detalle_anterior(desde, hasta, valores))
        por_total = _mapa_importe(filas, lambda fila: fila.subtotal)
        por_gravado = _mapa_importe(filas, lambda fila: fila.gravado)
        por_iva = _mapa_importe(filas, lambda fila: fila.iva)
        por_comp = _mapa_comprobantes(filas)
        medios = _medios_dona(filas)
        puntos = _puntos_evolucion(desde, hasta, por_total)
        return PanelVentas(
            desde=_texto_fecha(desde),
            hasta=_texto_fecha(hasta),
            total=_indicador(
                "Total ventas",
                actual["subtotal"],
                anterior["subtotal"],
                _serie_spark(_valores_rango(desde, hasta, por_total)),
                mostrar_guaranies,
            ),
            gravado=_indicador(
                "Gravado",
                actual["gravado"],
                anterior["gravado"],
                _serie_spark(_valores_rango(desde, hasta, por_gravado)),
                mostrar_guaranies,
            ),
            iva=_indicador(
                "IVA",
                actual["iva"],
                anterior["iva"],
                _serie_spark(_valores_rango(desde, hasta, por_iva)),
                mostrar_guaranies,
            ),
            comprobantes=_indicador(
                "Comprobantes",
                actual["comprobantes"],
                anterior["comprobantes"],
                _serie_spark(_valores_rango(desde, hasta, por_comp)),
                lambda valor: str(int(valor)),
            ),
            medios=medios,
            hay_medios=any(porcion.porcentaje for porcion in medios),
            evolucion={"ventas": True, "lineas": {"7": puntos}},
        )

    def totales_formateados(self):
        datos = self.totales_raw()
        return {
            "cantidad": formatear_cantidad(datos["cantidad"]),
            "gravado": mostrar_guaranies(datos["gravado"]),
            "iva": mostrar_guaranies(datos["iva"]),
            "subtotal": mostrar_guaranies(datos["subtotal"]),
            "cantidad_html": html_cantidad(datos["cantidad"]),
            "gravado_html": html_guaranies(datos["gravado"]),
            "iva_html": html_guaranies(datos["iva"]),
            "subtotal_html": html_guaranies(datos["subtotal"]),
        }

    def get_table(self, **kwargs):
        table = super().get_table(**kwargs)
        table.reporte_totales = self.totales_formateados()
        table.modo_agrupado = bool(self.agrupar() and self.agrupar() != AGRUPAR_DETALLE)
        return table

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        modo = self.agrupar()
        agrupado = bool(modo and modo != AGRUPAR_DETALLE)
        context["reporte_agrupado"] = modo if agrupado else ""
        context["reporte_agrupado_label"] = AGRUPAR_LABELS.get(modo, "")
        context["reporte_resumen_filtros"] = self.resumen_filtros()
        context["reporte_totales"] = self.totales_formateados()
        context["reporte_panel"] = self._panel()
        context["record_noun"] = "fila" if agrupado else self.record_noun
        return context

    def resumen_filtros(self):
        partes = []
        valores = filter_values(self.request, filter_specs_for(self))
        for spec in filter_specs_for(self):
            name = spec["name"]
            value = valores.get(name)
            if not value:
                continue
            label = spec["label"]
            kind = spec.get("kind", "choice")
            if kind == "fk":
                for option in (
                    spec["queryset"]() if callable(spec["queryset"]) else spec["queryset"]
                ):
                    if str(option.pk) == value:
                        partes.append(f"{label}: {option}")
                        break
            elif kind in ("choice", "skip"):
                for val, texto in spec.get("choices", ()):
                    if val == value:
                        partes.append(f"{label}: {texto}")
                        break
            elif kind == "date":
                partes.append(f"{label}: {value}")
        query = self.query()
        if query:
            partes.insert(0, f"Búsqueda: {query}")
        return partes

    def salida_extra_context(self):
        return {
            "reporte_resumen_filtros": self.resumen_filtros(),
            "reporte_agrupado_label": AGRUPAR_LABELS.get(self.agrupar(), ""),
            "reporte_totales": self.totales_formateados(),
        }

    def _salida_context(self):
        context = super()._salida_context()
        if self.export_totals and context["rows"]:
            context["record_count"] = max(0, len(context["rows"]) - 1)
        return context

    def export_dataset(self):
        from core.mantenimiento import _skip_export

        table_class = self.table_class
        queryset = self.get_queryset()
        table = table_class([])
        columns = [column for column in table.columns if not _skip_export(column)]
        headers = [str(column.header) for column in columns]
        rows = []
        for record in queryset:
            row = []
            for column in columns:
                row.append(self._celda_export(column, record))
            rows.append(row)
        if self.export_totals:
            total_row = self.export_totals_row(columns)
            if total_row is not None:
                rows.append(total_row)
        return headers, rows

    def export_totals_row(self, columns):
        totales = self.totales_formateados()
        modo = self.agrupar()
        agrupado = bool(modo and modo != AGRUPAR_DETALLE)
        row = []
        for column in columns:
            name = column.name
            if name in ("cantidad", "gravado", "iva", "subtotal"):
                row.append(totales[name])
            elif name == "etiqueta" and agrupado:
                row.append("Total")
            elif name == "fecha" and not agrupado:
                row.append("Total")
            else:
                row.append("")
        if row and not any(cell == "Total" for cell in row):
            row[0] = "Total"
        return row

    def _celda_export(self, column, record):
        value = column.accessor.resolve(record)
        if value is None or value == "":
            return ""
        name = column.name
        if name in ("gravado", "iva", "subtotal"):
            return mostrar_guaranies(value)
        if name == "cantidad":
            return formatear_cantidad(value)
        if name == "fecha" and hasattr(value, "strftime"):
            return value.strftime("%d/%m/%Y")
        if name == "tasa_iva":
            return f"{value}%"
        return value

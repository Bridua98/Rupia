from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from core.cantidad import formatear_cantidad
from core.moneda import formatear_guaranies
from cuentas.models import Cuenta
from inventario.models import Item, ItemMovimiento, TipoItem, TipoMovimiento
from inventario.precios import redondear_guarani
from inventario.reporte_stock import stock_desde_movimientos
from inventario.unidades import convertir_a_base, redondear_cantidad
from personas.consulta import buscar as buscar_padron
from personas.consulta import consultar_ruc
from personas.models import Genero, Persona, TipoDocumento
from ventas.models import (
    CondicionVenta,
    EstadoVenta,
    MedioPago,
    PuntoExpedicion,
    TipoComprobante,
    Venta,
    VentaDetalle,
    formatear_numero_comprobante,
)

UNO = Decimal("1")
CERO = Decimal("0")
CIEN = Decimal("100")
ONCE = Decimal("11")
VEINTIUNO = Decimal("21")


@dataclass
class LiquidacionIva:
    gravadas_10: Decimal = CERO
    iva_10: Decimal = CERO
    gravadas_5: Decimal = CERO
    iva_5: Decimal = CERO
    exentas: Decimal = CERO
    subtotal: Decimal = CERO
    descuento: Decimal = CERO
    total: Decimal = CERO
    unidades: int = 0


@dataclass
class LineaVista:
    pk: int
    descripcion: str
    codigo: str
    unidad_id: int
    unidad: str
    unidades: list
    cantidad: Decimal
    cantidad_txt: str
    precio: Decimal
    precio_txt: str
    subtotal: Decimal
    subtotal_txt: str
    tasa: int
    imagen: str
    descuento_porcentaje: Decimal
    descuento_txt: str


def formatear_porcentaje(valor) -> str:
    numero = Decimal(valor or 0)
    if numero == numero.to_integral_value():
        return str(int(numero))
    texto = format(numero.normalize(), "f")
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return texto.replace(".", ",")


def importe_linea(precio, cantidad, descuento_porcentaje=CERO) -> Decimal:
    porcentaje = Decimal(descuento_porcentaje or 0)
    if porcentaje < 0 or porcentaje > CIEN:
        raise ValidationError(
            "El descuento de la línea tiene que estar entre 0 y 100.",
            code="descuento",
        )
    bruto = Decimal(precio) * Decimal(cantidad)
    descuento = redondear_guarani(bruto * porcentaje / CIEN)
    return redondear_guarani(bruto - descuento)


def precio_en_unidad(item, unidad) -> Decimal:
    if item.precio is None:
        raise ValidationError("Ese ítem no tiene precio.", code="sin_precio")
    base = convertir_a_base(item, unidad, UNO)
    return redondear_guarani(item.precio * base)


def unidades_del_item(item):
    vistas = [{"id": item.unidad_medida_id, "simbolo": item.unidad_medida.simbolo}]
    for relacion in item.unidades.all():
        vistas.append({"id": relacion.unidad_medida_id, "simbolo": relacion.unidad_medida.simbolo})
    return vistas


def cajas():
    return Cuenta.objects.filter(es_banco=False).order_by("descripcion")


def cuentas_para_medio(medio, caja=None):
    if medio == MedioPago.EFECTIVO:
        if caja is None:
            return Cuenta.objects.none()
        return Cuenta.objects.filter(pk=caja.pk)
    if medio == MedioPago.TARJETA:
        return Cuenta.objects.filter(es_tarjeta=True).order_by("descripcion")
    if medio in (MedioPago.TRANSFERENCIA, MedioPago.QR):
        return Cuenta.objects.filter(es_banco=True, es_tarjeta=False).order_by("descripcion")
    return Cuenta.objects.none()


def medios_disponibles(medio_actual=None):
    opciones = []
    if cajas().exists():
        opciones.append((MedioPago.EFECTIVO, "Efectivo"))
    if cuentas_para_medio(MedioPago.TARJETA).exists():
        opciones.append((MedioPago.TARJETA, "Tarjeta"))
    if cuentas_para_medio(MedioPago.TRANSFERENCIA).exists():
        opciones.append((MedioPago.TRANSFERENCIA, "Transferencia"))
    vistos = {valor for valor, _etiqueta in opciones}
    if medio_actual and medio_actual not in vistos:
        etiqueta = dict(MedioPago.choices).get(medio_actual, medio_actual)
        opciones.append((medio_actual, etiqueta))
    return opciones


def caja_por_defecto():
    qs = cajas()
    if qs.count() == 1:
        return qs.first()
    return None


def cliente_ocasional():
    return (
        Persona.objects.filter(
            activo=True,
            es_cliente=True,
            razon_social__icontains="ocasional",
        )
        .order_by("razon_social")
        .first()
    )


def borrador(usuario) -> Venta:
    venta = (
        Venta.objects.filter(usuario=usuario, estado=EstadoVenta.EN_CURSO)
        .select_related("cliente", "caja", "cuenta_cobro")
        .first()
    )
    if venta:
        return venta
    caja = caja_por_defecto()
    venta = Venta.objects.create(
        fecha=timezone.localdate(),
        estado=EstadoVenta.EN_CURSO,
        usuario=usuario,
        caja=caja,
        cuenta_cobro=caja,
        medio=MedioPago.EFECTIVO,
        tipo_comprobante=TipoComprobante.TICKET,
        condicion_venta=CondicionVenta.CONTADO,
        cliente=cliente_ocasional(),
    )
    return venta


def cancelar(venta):
    if venta.estado != EstadoVenta.EN_CURSO:
        raise ValidationError("Esa venta ya está cobrada.", code="cobrada")
    venta.delete()


def punto_de(tipo) -> PuntoExpedicion | None:
    return PuntoExpedicion.objects.filter(tipo=tipo).first()


def _estado_emision(punto, fecha=None):
    fecha = fecha or timezone.localdate()
    if punto is None:
        return False, "No hay un timbrado registrado para ese comprobante.", "punto"
    if not punto.habilitado:
        return False, "El timbrado no está habilitado.", "habilitado"
    if not (punto.vigencia_desde <= fecha <= punto.vigencia_hasta):
        return False, "El timbrado no está vigente.", "timbrado"
    if not (punto.numero_desde <= punto.numero_proximo <= punto.numero_hasta):
        return False, "Se acabó el rango de números de ese comprobante.", "rango"
    return True, "", ""


def puede_emitir(punto, fecha=None) -> bool:
    return _estado_emision(punto, fecha)[0]


def motivo_emision(punto, fecha=None) -> str:
    return _estado_emision(punto, fecha)[1]


def exigir_emision(punto, fecha=None) -> PuntoExpedicion:
    ok, mensaje, code = _estado_emision(punto, fecha)
    if not ok:
        raise ValidationError(mensaje, code=code)
    return punto


def punto_para(tipo) -> PuntoExpedicion | None:
    punto = punto_de(tipo)
    if not puede_emitir(punto):
        return None
    return punto


def comprobantes_emitibles():
    return [
        (tipo, etiqueta)
        for tipo, etiqueta in TipoComprobante.choices
        if puede_emitir(punto_de(tipo))
    ]


def proximo_numero(tipo) -> str:
    punto = punto_para(tipo)
    if punto is None:
        return ""
    return punto.numero_completo()


def subtotal_venta(venta) -> Decimal:
    total = venta.detalles.aggregate(total=Sum("subtotal"))["total"]
    return redondear_guarani(total or CERO)


def total_venta(venta) -> Decimal:
    return redondear_guarani(subtotal_venta(venta) - (venta.descuento or CERO))


def vuelto_venta(venta) -> Decimal:
    total = total_venta(venta)
    recibido = venta.importe_recibido or CERO
    if venta.medio != MedioPago.EFECTIVO:
        return CERO
    resto = recibido - total
    return redondear_guarani(resto) if resto > 0 else CERO


def importes_rapidos(total: Decimal) -> list[Decimal]:
    total = redondear_guarani(total)
    opciones = [total]
    for salto in (Decimal("5000"), Decimal("10000"), Decimal("50000")):
        if total <= 0:
            break
        arriba = ((total + salto - UNO) // salto) * salto
        if arriba > total and arriba not in opciones:
            opciones.append(arriba)
        if len(opciones) == 3:
            break
    return opciones[:3]


def liquidar_iva(venta) -> LiquidacionIva:
    importes = {10: CERO, 5: CERO, 0: CERO}
    unidades = 0
    for detalle in venta.detalles.all():
        tasa = int(detalle.tasa_iva)
        importes[tasa] = importes.get(tasa, CERO) + detalle.subtotal
        unidades += int(detalle.cantidad) if detalle.cantidad == int(detalle.cantidad) else 1
    subtotal = redondear_guarani(sum(importes.values(), CERO))
    descuento = redondear_guarani(venta.descuento or CERO)
    netos = _prorratear_descuento(importes, descuento, subtotal)
    importe_10 = netos.get(10, CERO)
    importe_5 = netos.get(5, CERO)
    exentas = netos.get(0, CERO)
    iva_10 = redondear_guarani(importe_10 / ONCE) if importe_10 else CERO
    iva_5 = redondear_guarani(importe_5 / VEINTIUNO) if importe_5 else CERO
    return LiquidacionIva(
        gravadas_10=importe_10 - iva_10,
        iva_10=iva_10,
        gravadas_5=importe_5 - iva_5,
        iva_5=iva_5,
        exentas=exentas,
        subtotal=subtotal,
        descuento=descuento,
        total=redondear_guarani(importe_10 + importe_5 + exentas),
        unidades=unidades,
    )


def _prorratear_descuento(importes: dict, descuento: Decimal, subtotal: Decimal) -> dict:
    if subtotal <= 0 or descuento <= 0:
        return {tasa: redondear_guarani(monto) for tasa, monto in importes.items()}
    partes = {}
    for tasa, monto in importes.items():
        partes[tasa] = redondear_guarani(descuento * monto / subtotal)
    diferencia = descuento - sum(partes.values(), CERO)
    if diferencia:
        mayor = max(importes, key=lambda tasa: importes[tasa])
        partes[mayor] += diferencia
    return {
        tasa: redondear_guarani(monto - partes.get(tasa, CERO)) for tasa, monto in importes.items()
    }


def buscar_productos(query: str, *, limite=12):
    query = (query or "").strip()
    productos = Item.objects.filter(activo=True, tipo=TipoItem.PRODUCTO).select_related(
        "marca",
        "categoria",
        "unidad_medida",
    )
    if not query:
        return productos.none()
    exacto = list(productos.filter(codigo_barra__iexact=query)[:2])
    if len(exacto) == 1:
        return exacto
    return list(
        productos.filter(
            Q(descripcion__icontains=query)
            | Q(codigo_barra__icontains=query)
            | Q(marca__descripcion__icontains=query)
            | Q(categoria__descripcion__icontains=query)
        ).order_by("descripcion")[:limite]
    )


def buscar_clientes(query: str, *, limite=12):
    query = (query or "").strip()
    clientes = Persona.objects.filter(activo=True, es_cliente=True)
    if not query:
        return list(clientes.order_by("razon_social")[:limite])
    return list(
        clientes.filter(Q(razon_social__icontains=query) | Q(documento__icontains=query)).order_by(
            "razon_social"
        )[:limite]
    )


def _resultado_cliente(persona, *, origen="local"):
    return {
        "id": persona.pk,
        "label": str(persona),
        "origen": origen,
        "ruc": persona.documento,
        "documento": persona.documento,
    }


def buscar_clientes_pos(query: str, *, limite=12):
    query = (query or "").strip()
    locales = buscar_clientes(query, limite=limite)
    resultados = [_resultado_cliente(persona) for persona in locales]
    if not query:
        return resultados
    vistos = {persona.documento for persona in locales}
    for ficha in buscar_padron(query):
        documento = ficha.get("documento") or ""
        if documento in vistos:
            continue
        existente = Persona.objects.filter(documento=documento).first() if documento else None
        if existente:
            resultados.append(_resultado_cliente(existente))
            vistos.add(existente.documento)
        else:
            resultados.append(
                {
                    "id": None,
                    "label": ficha.get("label") or documento,
                    "origen": "padron",
                    "ruc": ficha.get("ruc") or "",
                    "documento": documento,
                }
            )
            vistos.add(documento)
        if len(resultados) >= limite:
            break
    return resultados


def asegurar_cliente_desde_ficha(ficha) -> Persona:
    documento = str((ficha or {}).get("documento") or "").strip()
    if not documento:
        raise ValidationError("No encontré esa persona en el padrón.", code="padron")
    persona = Persona.objects.filter(documento=documento).first()
    if persona:
        campos = []
        if not persona.es_cliente:
            persona.es_cliente = True
            campos.append("es_cliente")
        if not persona.activo:
            persona.activo = True
            campos.append("activo")
        if campos:
            persona.save(update_fields=campos)
        return persona
    fecha = None
    texto_fecha = (ficha or {}).get("fecha_nacimiento")
    if texto_fecha:
        try:
            fecha = datetime.strptime(str(texto_fecha), "%Y-%m-%d").date()
        except ValueError:
            fecha = None
    return Persona.objects.create(
        tipo_documento=ficha.get("tipo_documento") or TipoDocumento.CEDULA,
        documento=documento,
        razon_social=(ficha.get("razon_social") or documento).strip(),
        fecha_nacimiento=fecha,
        genero=Genero.SIN_DEFINIR,
        direccion="Sin dirección",
        es_cliente=True,
    )


def asegurar_cliente_desde_consulta(*, ruc="", query="") -> Persona:
    ficha = consultar_ruc(ruc) if ruc else None
    if ficha is None and query:
        hallados = buscar_padron(query)
        ficha = hallados[0] if hallados else None
    if ficha is None and ruc:
        hallados = buscar_padron(ruc)
        ficha = hallados[0] if hallados else None
    if ficha is None:
        raise ValidationError("No encontré esa persona en el padrón.", code="padron")
    return asegurar_cliente_desde_ficha(ficha)


def agregar_producto(venta, *, item=None, query=""):
    _exige_borrador(venta)
    if item is None:
        hallados = buscar_productos(query)
        if not hallados:
            raise ValidationError("No encontré ese producto.", code="sin_producto")
        if len(hallados) > 1:
            return hallados
        item = hallados[0]
    _validar_item_venta(item)
    unidad = item.unidad_medida
    precio = precio_en_unidad(item, unidad)
    linea = venta.detalles.filter(item=item, unidad_medida=unidad).first()
    if linea:
        linea.cantidad = redondear_cantidad(linea.cantidad + UNO)
        linea.precio = precio
        linea.subtotal = importe_linea(linea.precio, linea.cantidad, linea.descuento_porcentaje)
        linea.save(update_fields=["cantidad", "precio", "subtotal"])
        return linea
    return VentaDetalle.objects.create(
        venta=venta,
        item=item,
        unidad_medida=unidad,
        cantidad=UNO,
        precio=precio,
        tasa_iva=item.tasa_iva,
        descuento_porcentaje=CERO,
        subtotal=importe_linea(precio, UNO, CERO),
    )


def cambiar_cantidad(detalle, cantidad):
    _exige_borrador(detalle.venta)
    cantidad = redondear_cantidad(Decimal(cantidad))
    if cantidad <= 0:
        detalle.delete()
        return None
    detalle.cantidad = cantidad
    detalle.precio = precio_en_unidad(detalle.item, detalle.unidad_medida)
    detalle.subtotal = importe_linea(
        detalle.precio, detalle.cantidad, detalle.descuento_porcentaje
    )
    detalle.save(update_fields=["cantidad", "precio", "subtotal"])
    return detalle


def cambiar_unidad(detalle, unidad):
    _exige_borrador(detalle.venta)
    item = detalle.item
    permitidas = {item.unidad_medida_id, *[rel.unidad_medida_id for rel in item.unidades.all()]}
    if unidad.pk not in permitidas:
        raise ValidationError("Esa unidad no está relacionada con el ítem.", code="unidad")
    otra = (
        detalle.venta.detalles.filter(item=item, unidad_medida=unidad)
        .exclude(pk=detalle.pk)
        .first()
    )
    if otra:
        otra.cantidad = redondear_cantidad(otra.cantidad + detalle.cantidad)
        otra.precio = precio_en_unidad(item, unidad)
        otra.subtotal = importe_linea(otra.precio, otra.cantidad, otra.descuento_porcentaje)
        otra.save(update_fields=["cantidad", "precio", "subtotal"])
        detalle.delete()
        return otra
    detalle.unidad_medida = unidad
    detalle.precio = precio_en_unidad(item, unidad)
    detalle.subtotal = importe_linea(
        detalle.precio, detalle.cantidad, detalle.descuento_porcentaje
    )
    detalle.save(update_fields=["unidad_medida", "precio", "subtotal"])
    return detalle


def cambiar_descuento(detalle, porcentaje):
    _exige_borrador(detalle.venta)
    try:
        porcentaje = Decimal(str(porcentaje).replace(",", ".").strip() or "0")
    except InvalidOperation as exc:
        raise ValidationError("Escribí un descuento en porcentaje.", code="descuento") from exc
    detalle.descuento_porcentaje = porcentaje.quantize(Decimal("0.01"))
    detalle.precio = precio_en_unidad(detalle.item, detalle.unidad_medida)
    detalle.subtotal = importe_linea(
        detalle.precio, detalle.cantidad, detalle.descuento_porcentaje
    )
    detalle.save(update_fields=["descuento_porcentaje", "precio", "subtotal"])
    return detalle


def quitar_linea(detalle):
    _exige_borrador(detalle.venta)
    detalle.delete()


def actualizar_cabecera(
    venta,
    *,
    caja=None,
    tipo_comprobante=None,
    medio=None,
    cuenta_cobro=None,
    descuento=None,
    cliente=None,
    consumidor_final=False,
    observacion=None,
    importe_recibido=None,
):
    _exige_borrador(venta)
    campos = []
    if caja is not None:
        if caja.es_banco:
            raise ValidationError("Elegí una caja.", code="caja")
        venta.caja = caja
        campos.append("caja")
    if tipo_comprobante is not None:
        venta.tipo_comprobante = tipo_comprobante
        campos.append("tipo_comprobante")
    if medio is not None:
        venta.medio = medio
        campos.append("medio")
        if medio == MedioPago.EFECTIVO and venta.caja_id:
            venta.cuenta_cobro = venta.caja
            campos.append("cuenta_cobro")
        elif venta.cuenta_cobro_id:
            permitidas = set(cuentas_para_medio(medio, venta.caja).values_list("pk", flat=True))
            if venta.cuenta_cobro_id not in permitidas:
                opciones = list(cuentas_para_medio(medio, venta.caja)[:2])
                venta.cuenta_cobro = opciones[0] if len(opciones) == 1 else None
                campos.append("cuenta_cobro")
    if cuenta_cobro is not None:
        permitidas = set(cuentas_para_medio(venta.medio, venta.caja).values_list("pk", flat=True))
        if cuenta_cobro.pk in permitidas:
            venta.cuenta_cobro = cuenta_cobro
            campos.append("cuenta_cobro")
        elif medio is None:
            raise ValidationError("Elegí la cuenta de cobro.", code="cuenta")
    if descuento is not None:
        descuento = redondear_guarani(Decimal(descuento))
        if descuento < 0:
            raise ValidationError("El descuento no puede ser negativo.", code="descuento")
        if descuento > subtotal_venta(venta):
            raise ValidationError(
                "El descuento no puede ser mayor que el subtotal.",
                code="descuento",
            )
        venta.descuento = descuento
        campos.append("descuento")
    if consumidor_final:
        venta.cliente = None
        campos.append("cliente")
    elif cliente is not None:
        if not cliente.es_cliente:
            raise ValidationError("Esa persona no es cliente.", code="cliente")
        venta.cliente = cliente
        campos.append("cliente")
    if observacion is not None:
        venta.observacion = observacion
        campos.append("observacion")
    if importe_recibido is not None:
        venta.importe_recibido = redondear_guarani(Decimal(importe_recibido))
        campos.append("importe_recibido")
    if venta.medio != MedioPago.EFECTIVO:
        venta.importe_recibido = total_venta(venta)
        if "importe_recibido" not in campos:
            campos.append("importe_recibido")
    if campos:
        venta.save(update_fields=campos)
    return venta


def confirmar(venta) -> Venta:
    _exige_borrador(venta)
    if not venta.detalles.exists():
        raise ValidationError("Agregá un producto.", code="vacia")
    if venta.caja_id is None:
        raise ValidationError("Elegí una caja.", code="caja")
    if venta.cuenta_cobro_id is None:
        raise ValidationError("Elegí la cuenta de cobro.", code="cuenta")
    if venta.tipo_comprobante == TipoComprobante.FACTURA and venta.cliente_id is None:
        raise ValidationError("La factura pide un cliente.", code="cliente")
    descuento = redondear_guarani(venta.descuento or CERO)
    subtotal = subtotal_venta(venta)
    if descuento > subtotal:
        raise ValidationError("El descuento no puede ser mayor que el subtotal.", code="descuento")
    total = redondear_guarani(subtotal - descuento)
    if venta.medio != MedioPago.EFECTIVO:
        recibido = total
    else:
        recibido = redondear_guarani(venta.importe_recibido or CERO)
        if recibido <= 0:
            recibido = total
        elif recibido < total:
            raise ValidationError(
                "En efectivo el importe recibido tiene que cubrir el total.",
                code="recibido",
            )
    with transaction.atomic():
        venta = Venta.objects.select_for_update().get(pk=venta.pk)
        _exige_borrador(venta)
        fecha = timezone.localdate()
        punto = exigir_emision(
            PuntoExpedicion.objects.select_for_update()
            .filter(tipo=venta.tipo_comprobante)
            .first(),
            fecha,
        )
        _validar_stock(venta)
        secuencial = punto.numero_proximo
        numero = formatear_numero_comprobante(punto.establecimiento, punto.codigo, secuencial)
        punto.numero_proximo = secuencial + 1
        punto.save(update_fields=["numero_proximo"])
        venta.fecha = fecha
        venta.estado = EstadoVenta.COBRADA
        venta.punto = punto
        venta.timbrado = punto.timbrado
        venta.vigencia_desde = punto.vigencia_desde
        venta.vigencia_hasta = punto.vigencia_hasta
        venta.establecimiento = punto.establecimiento
        venta.punto_codigo = punto.codigo
        venta.secuencial = secuencial
        venta.numero_completo = numero
        venta.emisor_razon_social = punto.emisor_razon_social
        venta.emisor_ruc = punto.emisor_ruc
        venta.emisor_direccion = punto.emisor_direccion
        venta.emisor_telefono = punto.emisor_telefono
        venta.emisor_actividad = punto.emisor_actividad
        venta.condicion_venta = CondicionVenta.CONTADO
        venta.importe_recibido = recibido
        venta.save()
        _registrar_movimientos(venta)
    return venta


def lineas_vista(venta) -> list[LineaVista]:
    lineas = []
    detalles = venta.detalles.select_related(
        "item",
        "item__unidad_medida",
        "unidad_medida",
    ).prefetch_related("item__unidades__unidad_medida")
    for detalle in detalles:
        lineas.append(
            LineaVista(
                pk=detalle.pk,
                descripcion=detalle.item.descripcion,
                codigo=detalle.item.codigo_barra or "",
                unidad_id=detalle.unidad_medida_id,
                unidad=detalle.unidad_medida.simbolo,
                unidades=unidades_del_item(detalle.item),
                cantidad=detalle.cantidad,
                cantidad_txt=formatear_cantidad(detalle.cantidad),
                precio=detalle.precio,
                precio_txt=formatear_guaranies(detalle.precio),
                subtotal=detalle.subtotal,
                subtotal_txt=formatear_guaranies(detalle.subtotal),
                tasa=detalle.tasa_iva,
                imagen=detalle.item.imagen or "",
                descuento_porcentaje=detalle.descuento_porcentaje or CERO,
                descuento_txt=formatear_porcentaje(detalle.descuento_porcentaje or CERO),
            )
        )
    return lineas


def _exige_borrador(venta):
    if venta.estado != EstadoVenta.EN_CURSO:
        raise ValidationError("Esa venta ya está cobrada.", code="cobrada")


def _validar_item_venta(item):
    if item.tipo != TipoItem.PRODUCTO or not item.activo:
        raise ValidationError("Ese ítem no está a la venta.", code="item")
    if item.precio is None:
        raise ValidationError("Ese ítem no tiene precio.", code="sin_precio")


def _validar_stock(venta):
    pedidos = {}
    for detalle in venta.detalles.select_related("item", "unidad_medida", "item__unidad_medida"):
        _validar_item_venta(detalle.item)
        item = detalle.item
        try:
            cantidad_base = convertir_a_base(item, detalle.unidad_medida, detalle.cantidad)
        except ValidationError as exc:
            raise ValidationError(exc.messages[0], code="unidad") from exc
        pedidos[item.pk] = pedidos.get(item.pk, CERO) + cantidad_base
    if not pedidos:
        return
    items = Item.objects.filter(pk__in=pedidos).prefetch_related(
        "unidades",
        "movimientos",
    )
    for item in items:
        vigentes = item.movimientos.filter(es_vigente=True).select_related("unidad_medida")
        stock, _omitidos = stock_desde_movimientos(item, vigentes)
        if pedidos[item.pk] > stock:
            raise ValidationError(
                f"No hay stock suficiente de {item.descripcion}.",
                code="stock",
            )


def _siguiente_movimiento_id():
    ultimo = (
        ItemMovimiento.objects.select_for_update()
        .order_by("-id")
        .values_list("id", flat=True)
        .first()
    )
    return (ultimo or 0) + 1


def _registrar_movimientos(venta):
    siguiente = _siguiente_movimiento_id()
    for orden, detalle in enumerate(venta.detalles.select_related("item"), start=1):
        costo = detalle.item.ultimo_costo if detalle.item.ultimo_costo is not None else CERO
        ItemMovimiento.objects.create(
            id=siguiente,
            item=detalle.item,
            unidad_medida=detalle.unidad_medida,
            tipo=TipoMovimiento.VENTA,
            fecha_movimiento=venta.fecha,
            cantidad=detalle.cantidad,
            precio=detalle.precio,
            costo=costo,
            subtotal=detalle.subtotal,
            secuencia_origen=venta.numero_completo,
            secuencia_detalle_origen=orden,
            es_vigente=True,
        )
        siguiente += 1

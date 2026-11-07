from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from compras.cuotas import compra_tiene_pagos, limpiar_cuotas, validar_cuotas_credito
from compras.models import (
    Compra,
    CompraDetalle,
    EstadoCompra,
    TipoCompra,
    formatear_numero_factura,
)
from core.cantidad import formatear_cantidad
from core.moneda import formatear_guaranies
from core.timbrado import interpretar_timbrado
from cuentas.models import Cuenta
from inventario.models import (
    Item,
    ItemMovimiento,
    ItemPrecioHistorial,
    OrigenPrecio,
    TasaIva,
    TipoItem,
    TipoMovimiento,
)
from inventario.precios import redondear_guarani
from inventario.stock import siguiente_movimiento_id
from inventario.unidades import convertir_a_base, redondear_cantidad
from negocio.models import UnidadNegocio
from personas.consulta import buscar as buscar_padron
from personas.consulta import consultar_ruc
from personas.models import Genero, Persona, TipoDocumento

UNO = Decimal("1")
CERO = Decimal("0")
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
    total: Decimal = CERO


@dataclass
class LineaVista:
    pk: int
    descripcion: str
    marca: str
    codigo: str
    es_gasto: bool
    unidad_id: int
    unidad: str
    unidades: list
    unidad_negocio_id: int | None
    unidad_negocio: str
    cantidad: Decimal
    cantidad_txt: str
    costo: Decimal
    costo_txt: str
    subtotal: Decimal
    subtotal_txt: str
    tasa: int
    imagen: str
    segun_costo: bool


@dataclass(frozen=True)
class PrecioPendiente:
    item_id: int
    descripcion: str
    costo_anterior: Decimal | None
    costo_nuevo: Decimal
    precio_anterior: Decimal | None
    precio_nuevo: Decimal


def importe_linea(costo, cantidad) -> Decimal:
    return redondear_guarani(Decimal(costo) * Decimal(cantidad))


def costo_en_unidad(item, unidad) -> Decimal:
    if item.ultimo_costo is None:
        return CERO
    base = convertir_a_base(item, unidad, UNO)
    return redondear_guarani(item.ultimo_costo * base)


def costo_en_base(item, unidad, costo) -> Decimal:
    base = convertir_a_base(item, unidad, UNO)
    if base <= 0:
        raise ValidationError("La unidad no se puede convertir.", code="unidad")
    return redondear_guarani(Decimal(costo) / base)


def unidades_del_item(item):
    vistas = [{"id": item.unidad_medida_id, "simbolo": item.unidad_medida.simbolo}]
    vistos = {item.unidad_medida_id}
    for relacion in item.unidades.all():
        if relacion.unidad_medida_id in vistos:
            continue
        vistos.add(relacion.unidad_medida_id)
        vistas.append({"id": relacion.unidad_medida_id, "simbolo": relacion.unidad_medida.simbolo})
    return vistas


def cuentas():
    return Cuenta.objects.order_by("descripcion")


def cuenta_por_defecto():
    qs = cuentas()
    if qs.count() == 1:
        return qs.first()
    return None


def unidades_negocio():
    return list(UnidadNegocio.objects.order_by("descripcion"))


def tasas_iva():
    return [{"id": valor, "label": etiqueta} for valor, etiqueta in TasaIva.choices]


def borrador(usuario) -> Compra:
    compra = (
        Compra.objects.filter(usuario=usuario, estado=EstadoCompra.EN_CURSO)
        .select_related("proveedor", "cuenta")
        .first()
    )
    if compra:
        return compra
    return Compra.objects.create(
        fecha=timezone.localdate(),
        estado=EstadoCompra.EN_CURSO,
        tipo=TipoCompra.FACTURA_CONTADO,
        usuario=usuario,
        cuenta=cuenta_por_defecto(),
    )


def cancelar(compra):
    if compra.estado != EstadoCompra.EN_CURSO:
        raise ValidationError("Esa compra ya está confirmada.", code="confirmada")
    compra.delete()


def anular(compra, usuario=None):
    with transaction.atomic():
        compra = Compra.objects.select_for_update().get(pk=compra.pk)
        if compra.estado == EstadoCompra.ANULADA:
            raise ValidationError("Esa compra ya está anulada.", code="anulada")
        if compra.estado != EstadoCompra.CONFIRMADA:
            raise ValidationError("Solo se puede anular una compra confirmada.", code="estado")
        if compra.es_credito and compra_tiene_pagos(compra):
            raise ValidationError(
                "Hay pagos confirmados sobre las cuotas. Anulá los pagos primero.",
                code="pagos",
            )
        ItemMovimiento.objects.filter(
            tipo=TipoMovimiento.COMPRA,
            secuencia_origen=_secuencia(compra),
            es_vigente=True,
        ).update(es_vigente=False)
        compra.estado = EstadoCompra.ANULADA
        compra.anulado_en = timezone.now()
        compra.anulado_por = usuario
        compra.save(update_fields=["estado", "anulado_en", "anulado_por"])
    return compra


def subtotal_compra(compra) -> Decimal:
    total = compra.detalles.aggregate(total=Sum("subtotal"))["total"]
    return redondear_guarani(total or CERO)


def liquidar_iva(compra) -> LiquidacionIva:
    importes = {10: CERO, 5: CERO, 0: CERO}
    for detalle in compra.detalles.all():
        tasa = int(detalle.tasa_iva)
        importes[tasa] = importes.get(tasa, CERO) + detalle.subtotal
    subtotal = redondear_guarani(sum(importes.values(), CERO))
    importe_10 = importes.get(10, CERO)
    importe_5 = importes.get(5, CERO)
    exentas = importes.get(0, CERO)
    iva_10 = redondear_guarani(importe_10 / ONCE) if importe_10 else CERO
    iva_5 = redondear_guarani(importe_5 / VEINTIUNO) if importe_5 else CERO
    return LiquidacionIva(
        gravadas_10=importe_10 - iva_10,
        iva_10=iva_10,
        gravadas_5=importe_5 - iva_5,
        iva_5=iva_5,
        exentas=exentas,
        subtotal=subtotal,
        total=subtotal,
    )


def buscar_items(query: str, *, limite=12, offset=0, catalogo=False):
    query = (query or "").strip()
    offset = max(0, int(offset or 0))
    limite = max(1, int(limite or 12))
    items = Item.objects.filter(activo=True).select_related(
        "marca",
        "categoria",
        "unidad_medida",
        "unidad_negocio",
    )
    if not query:
        if catalogo:
            return list(items.order_by("tipo", "descripcion")[offset : offset + limite])
        return list(items.none())
    exacto = list(items.filter(codigo_barra__iexact=query)[:2])
    if len(exacto) == 1 and offset == 0:
        return exacto
    return list(
        items.filter(
            Q(descripcion__icontains=query)
            | Q(codigo_barra__icontains=query)
            | Q(marca__descripcion__icontains=query)
            | Q(categoria__descripcion__icontains=query)
        ).order_by("tipo", "descripcion")[offset : offset + limite]
    )


def buscar_proveedores(query: str, *, limite=12):
    query = (query or "").strip()
    proveedores = Persona.objects.filter(activo=True, es_proveedor=True)
    if not query:
        return list(proveedores.order_by("razon_social")[:limite])
    return list(
        proveedores.filter(
            Q(razon_social__icontains=query) | Q(documento__icontains=query)
        ).order_by("razon_social")[:limite]
    )


def _resultado_proveedor(persona, *, origen="local"):
    return {
        "id": persona.pk,
        "label": str(persona),
        "origen": origen,
        "ruc": persona.documento,
        "documento": persona.documento,
    }


def buscar_proveedores_pos(query: str, *, limite=12):
    query = (query or "").strip()
    locales = buscar_proveedores(query, limite=limite)
    resultados = [_resultado_proveedor(persona) for persona in locales]
    if not query:
        return resultados
    vistos = {persona.documento for persona in locales}
    for ficha in buscar_padron(query):
        documento = ficha.get("documento") or ""
        if documento in vistos:
            continue
        existente = Persona.objects.filter(documento=documento).first() if documento else None
        if existente:
            resultados.append(_resultado_proveedor(existente))
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


def asegurar_proveedor_desde_ficha(ficha) -> Persona:
    documento = str((ficha or {}).get("documento") or "").strip()
    if not documento:
        raise ValidationError("No encontré esa persona en el padrón.", code="padron")
    persona = Persona.objects.filter(documento=documento).first()
    if persona:
        campos = []
        if not persona.es_proveedor:
            persona.es_proveedor = True
            campos.append("es_proveedor")
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
        es_proveedor=True,
    )


def asegurar_proveedor_desde_consulta(*, ruc="", query="") -> Persona:
    ficha = consultar_ruc(ruc) if ruc else None
    if ficha is None and query:
        hallados = buscar_padron(query)
        ficha = hallados[0] if hallados else None
    if ficha is None and ruc:
        hallados = buscar_padron(ruc)
        ficha = hallados[0] if hallados else None
    if ficha is None:
        raise ValidationError("No encontré esa persona en el padrón.", code="padron")
    return asegurar_proveedor_desde_ficha(ficha)


def agregar_item(compra, *, item=None, query=""):
    _exige_borrador(compra)
    if item is None:
        hallados = buscar_items(query)
        if not hallados:
            raise ValidationError("No encontré ese ítem.", code="sin_item")
        if len(hallados) > 1:
            return hallados
        item = hallados[0]
    _validar_item_compra(item)
    unidad = item.unidad_medida
    costo = costo_en_unidad(item, unidad) if item.tipo == TipoItem.PRODUCTO else CERO
    tasa = item.tasa_iva
    negocio = item.unidad_negocio
    linea = compra.detalles.filter(item=item, unidad_medida=unidad).first()
    if linea:
        linea.cantidad = redondear_cantidad(linea.cantidad + UNO)
        linea.subtotal = importe_linea(linea.costo, linea.cantidad)
        linea.save(update_fields=["cantidad", "subtotal"])
        return linea
    return CompraDetalle.objects.create(
        compra=compra,
        item=item,
        unidad_medida=unidad,
        unidad_negocio=negocio,
        cantidad=UNO,
        costo=costo,
        tasa_iva=tasa,
        subtotal=importe_linea(costo, UNO),
    )


def cambiar_cantidad(detalle, cantidad):
    _exige_borrador(detalle.compra)
    cantidad = redondear_cantidad(Decimal(cantidad))
    if cantidad <= 0:
        detalle.delete()
        return None
    detalle.cantidad = cantidad
    detalle.subtotal = importe_linea(detalle.costo, detalle.cantidad)
    detalle.save(update_fields=["cantidad", "subtotal"])
    return detalle


def cambiar_costo(detalle, costo):
    _exige_borrador(detalle.compra)
    costo = redondear_guarani(Decimal(costo))
    if costo < 0:
        raise ValidationError("El costo no puede ser negativo.", code="costo")
    detalle.costo = costo
    detalle.subtotal = importe_linea(detalle.costo, detalle.cantidad)
    detalle.save(update_fields=["costo", "subtotal"])
    return detalle


def cambiar_unidad(detalle, unidad):
    _exige_borrador(detalle.compra)
    item = detalle.item
    if item.tipo == TipoItem.GASTO:
        raise ValidationError("El gasto no cambia de unidad.", code="unidad")
    permitidas = {item.unidad_medida_id, *[rel.unidad_medida_id for rel in item.unidades.all()]}
    if unidad.pk not in permitidas:
        raise ValidationError("Esa unidad no está relacionada con el ítem.", code="unidad")
    costo_base = costo_en_base(item, detalle.unidad_medida, detalle.costo)
    otra = (
        detalle.compra.detalles.filter(item=item, unidad_medida=unidad)
        .exclude(pk=detalle.pk)
        .first()
    )
    costo = redondear_guarani(costo_base * convertir_a_base(item, unidad, UNO))
    if otra:
        otra.cantidad = redondear_cantidad(otra.cantidad + detalle.cantidad)
        otra.costo = costo
        otra.subtotal = importe_linea(otra.costo, otra.cantidad)
        otra.save(update_fields=["cantidad", "costo", "subtotal"])
        detalle.delete()
        return otra
    detalle.unidad_medida = unidad
    detalle.costo = costo
    detalle.subtotal = importe_linea(detalle.costo, detalle.cantidad)
    detalle.save(update_fields=["unidad_medida", "costo", "subtotal"])
    return detalle


def cambiar_tasa(detalle, tasa):
    _exige_borrador(detalle.compra)
    if detalle.item.tipo != TipoItem.GASTO:
        raise ValidationError("La tasa del producto sale de la ficha.", code="tasa")
    try:
        tasa = int(tasa)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Elegí una tasa de IVA.", code="tasa") from exc
    if tasa not in TasaIva.values:
        raise ValidationError("Elegí una tasa de IVA válida.", code="tasa")
    detalle.tasa_iva = tasa
    detalle.save(update_fields=["tasa_iva"])
    return detalle


def cambiar_unidad_negocio(detalle, unidad_negocio):
    _exige_borrador(detalle.compra)
    if detalle.item.tipo != TipoItem.GASTO:
        raise ValidationError("La unidad de negocio del producto sale de la ficha.", code="negocio")
    detalle.unidad_negocio = unidad_negocio
    detalle.save(update_fields=["unidad_negocio"])
    return detalle


def quitar_linea(detalle):
    _exige_borrador(detalle.compra)
    detalle.delete()


def actualizar_cabecera(
    compra,
    *,
    cuenta=None,
    tipo=None,
    proveedor=None,
    sin_proveedor=False,
    observacion=None,
    timbrado=None,
    establecimiento=None,
    punto_codigo=None,
    secuencial=None,
):
    _exige_borrador(compra)
    campos = []
    if cuenta is not None:
        compra.cuenta = cuenta
        campos.append("cuenta")
    if tipo is not None:
        if tipo not in TipoCompra.values:
            raise ValidationError("Elegí el tipo de compra.", code="tipo")
        compra.tipo = tipo
        campos.append("tipo")
        if tipo != TipoCompra.FACTURA_CREDITO:
            limpiar_cuotas(compra)
        if tipo == TipoCompra.FACTURA_CREDITO:
            compra.cuenta = None
            campos.append("cuenta")
        if tipo == TipoCompra.EGRESO:
            compra.timbrado = ""
            compra.establecimiento = ""
            compra.punto_codigo = ""
            compra.secuencial = None
            compra.numero_completo = None
            campos.extend(
                [
                    "timbrado",
                    "establecimiento",
                    "punto_codigo",
                    "secuencial",
                    "numero_completo",
                ]
            )
    if sin_proveedor:
        compra.proveedor = None
        campos.append("proveedor")
    elif proveedor is not None:
        if not proveedor.es_proveedor:
            raise ValidationError("Esa persona no es proveedor.", code="proveedor")
        compra.proveedor = proveedor
        campos.append("proveedor")
    if observacion is not None:
        compra.observacion = observacion
        campos.append("observacion")
    if compra.es_factura:
        if timbrado is not None:
            texto = str(timbrado).strip()
            if texto and (not texto.isdigit() or len(texto) > 8):
                interpretar_timbrado(texto)
            compra.timbrado = texto
            campos.append("timbrado")
        if establecimiento is not None and str(establecimiento).strip():
            compra.establecimiento = _serie(establecimiento, "establecimiento")
            campos.append("establecimiento")
        if punto_codigo is not None and str(punto_codigo).strip():
            compra.punto_codigo = _serie(punto_codigo, "punto")
            campos.append("punto_codigo")
        if secuencial is not None and str(secuencial).strip():
            compra.secuencial = _secuencial(secuencial)
            campos.append("secuencial")
        if compra.establecimiento and compra.punto_codigo and compra.secuencial:
            compra.numero_completo = formatear_numero_factura(
                compra.establecimiento,
                compra.punto_codigo,
                compra.secuencial,
            )
            if "numero_completo" not in campos:
                campos.append("numero_completo")
    if campos:
        compra.save(update_fields=campos)
    return compra


def interpretar_serie_compra(valor, etiqueta: str) -> str:
    return _serie(valor, etiqueta)


def interpretar_secuencial_compra(valor) -> int:
    return _secuencial(valor)


def _serie(valor, etiqueta: str) -> str:
    texto = str(valor or "").strip()
    if not texto:
        raise ValidationError(f"Escribí el {etiqueta}.", code="numero")
    if not texto.isdigit():
        raise ValidationError(f"El {etiqueta} solo admite dígitos.", code="numero")
    if len(texto) > 3:
        raise ValidationError(f"El {etiqueta} tiene tres dígitos.", code="numero")
    return texto.zfill(3)


def _secuencial(valor) -> int:
    texto = str(valor if valor is not None else "").strip()
    if not texto:
        raise ValidationError("Escribí el número de factura.", code="numero")
    if not texto.isdigit():
        raise ValidationError("El número de factura solo admite dígitos.", code="numero")
    if len(texto) > 7:
        raise ValidationError("El número de factura admite hasta 7 dígitos.", code="numero")
    return int(texto)


def numero_ya_usado(proveedor_id, timbrado: str, numero: str, *, excluir=None) -> bool:
    if not proveedor_id or not timbrado or not numero:
        return False
    qs = Compra.objects.filter(
        estado=EstadoCompra.CONFIRMADA,
        proveedor_id=proveedor_id,
        timbrado=timbrado,
        numero_completo=numero,
        tipo__in=(TipoCompra.FACTURA_CONTADO, TipoCompra.FACTURA_CREDITO),
    )
    if excluir:
        qs = qs.exclude(pk=excluir)
    return qs.exists()


def precios_pendientes(compra) -> list[PrecioPendiente]:
    pendientes = []
    vistos = set()
    detalles = compra.detalles.select_related("item", "unidad_medida", "item__unidad_medida")
    for detalle in detalles:
        item = detalle.item
        if item.tipo != TipoItem.PRODUCTO or not item.precio_segun_costo:
            continue
        if item.pk in vistos:
            continue
        vistos.add(item.pk)
        costo_nuevo = costo_en_base(item, detalle.unidad_medida, detalle.costo)
        propuesto = _precio_propuesto(item, costo_nuevo)
        if (
            item.precio is not None
            and propuesto == item.precio
            and item.ultimo_costo == costo_nuevo
        ):
            continue
        pendientes.append(
            PrecioPendiente(
                item_id=item.pk,
                descripcion=item.descripcion,
                costo_anterior=item.ultimo_costo,
                costo_nuevo=costo_nuevo,
                precio_anterior=item.precio,
                precio_nuevo=propuesto,
            )
        )
    return pendientes


def _precio_propuesto(item, costo_nuevo: Decimal) -> Decimal:
    if item.precio is not None and item.ultimo_costo and item.ultimo_costo > 0:
        return redondear_guarani(item.precio * costo_nuevo / item.ultimo_costo)
    return redondear_guarani(costo_nuevo)


def confirmar(compra, *, afectar_precios=False) -> Compra:
    _exige_borrador(compra)
    if not compra.detalles.exists():
        raise ValidationError("Agregá un ítem.", code="vacia")
    if compra.tipo != TipoCompra.FACTURA_CREDITO and compra.cuenta_id is None:
        raise ValidationError("Elegí una cuenta.", code="cuenta")
    if compra.proveedor_id is None:
        raise ValidationError("Elegí un proveedor.", code="proveedor")
    _validar_documento(compra)
    _validar_lineas(compra)
    validar_cuotas_credito(compra, subtotal_compra(compra))
    with transaction.atomic():
        compra = Compra.objects.select_for_update().get(pk=compra.pk)
        _exige_borrador(compra)
        if compra.es_factura and numero_ya_usado(
            compra.proveedor_id,
            compra.timbrado,
            compra.numero_completo,
            excluir=compra.pk,
        ):
            raise ValidationError(
                "Ya hay una factura de ese proveedor con ese timbrado y número.",
                code="numero",
            )
        pendientes = precios_pendientes(compra) if afectar_precios else []
        compra.fecha = timezone.localdate()
        compra.estado = EstadoCompra.CONFIRMADA
        compra.afectar_precios = bool(afectar_precios)
        if not compra.es_factura:
            compra.timbrado = ""
            compra.establecimiento = ""
            compra.punto_codigo = ""
            compra.secuencial = None
            compra.numero_completo = None
        try:
            compra.save()
        except IntegrityError as exc:
            raise ValidationError(
                "Ya hay una factura de ese proveedor con ese timbrado y número.",
                code="numero",
            ) from exc
        _registrar_movimientos(compra)
        _actualizar_costos(compra, pendientes if afectar_precios else [])
    return compra


def lineas_vista(compra) -> list[LineaVista]:
    lineas = []
    detalles = compra.detalles.select_related(
        "item",
        "item__marca",
        "item__unidad_medida",
        "unidad_medida",
        "unidad_negocio",
    ).prefetch_related("item__unidades__unidad_medida")
    for detalle in detalles:
        es_gasto = detalle.item.tipo == TipoItem.GASTO
        lineas.append(
            LineaVista(
                pk=detalle.pk,
                descripcion=detalle.item.descripcion,
                marca=detalle.item.marca.descripcion if detalle.item.marca_id else "",
                codigo=detalle.item.codigo_barra or "",
                es_gasto=es_gasto,
                unidad_id=detalle.unidad_medida_id,
                unidad=detalle.unidad_medida.simbolo,
                unidades=unidades_del_item(detalle.item) if not es_gasto else [],
                unidad_negocio_id=detalle.unidad_negocio_id,
                unidad_negocio=(
                    detalle.unidad_negocio.abreviado if detalle.unidad_negocio_id else ""
                ),
                cantidad=detalle.cantidad,
                cantidad_txt=formatear_cantidad(detalle.cantidad),
                costo=detalle.costo,
                costo_txt=formatear_guaranies(detalle.costo),
                subtotal=detalle.subtotal,
                subtotal_txt=formatear_guaranies(detalle.subtotal),
                tasa=detalle.tasa_iva,
                imagen=detalle.item.imagen or "",
                segun_costo=bool(detalle.item.precio_segun_costo),
            )
        )
    return lineas


def _exige_borrador(compra):
    if compra.estado != EstadoCompra.EN_CURSO:
        raise ValidationError("Esa compra ya está confirmada.", code="confirmada")


def _validar_item_compra(item):
    if not item.activo:
        raise ValidationError("Ese ítem no está activo.", code="item")
    if item.tipo not in (TipoItem.PRODUCTO, TipoItem.GASTO):
        raise ValidationError("Ese ítem no se puede comprar.", code="item")


def _validar_documento(compra):
    if not compra.es_factura:
        return
    compra.timbrado = interpretar_timbrado(compra.timbrado)
    if not compra.establecimiento or not compra.punto_codigo or compra.secuencial is None:
        raise ValidationError("Escribí el número de factura.", code="numero")
    compra.numero_completo = formatear_numero_factura(
        compra.establecimiento,
        compra.punto_codigo,
        compra.secuencial,
    )


def _validar_lineas(compra):
    for detalle in compra.detalles.select_related("item", "unidad_medida"):
        _validar_item_compra(detalle.item)
        if detalle.cantidad <= 0:
            raise ValidationError("La cantidad tiene que ser mayor a 0.", code="cantidad")
        if detalle.costo <= 0:
            raise ValidationError(
                f"Escribí el costo de {detalle.item.descripcion}.",
                code="costo",
            )
        if detalle.item.tipo == TipoItem.GASTO and not detalle.unidad_negocio_id:
            raise ValidationError(
                f"Elegí la unidad de negocio de {detalle.item.descripcion}.",
                code="negocio",
            )
        if detalle.item.tipo == TipoItem.PRODUCTO:
            if not detalle.unidad_negocio_id:
                detalle.unidad_negocio = detalle.item.unidad_negocio
            if detalle.tasa_iva != detalle.item.tasa_iva:
                detalle.tasa_iva = detalle.item.tasa_iva
            detalle.save(update_fields=["unidad_negocio", "tasa_iva"])
            try:
                convertir_a_base(detalle.item, detalle.unidad_medida, detalle.cantidad)
            except ValidationError as exc:
                raise ValidationError(exc.messages[0], code="unidad") from exc


def _secuencia(compra) -> str:
    return f"C{compra.pk}"


def _registrar_movimientos(compra):
    siguiente = siguiente_movimiento_id()
    origen = _secuencia(compra)
    for orden, detalle in enumerate(
        compra.detalles.select_related("item", "unidad_medida"),
        start=1,
    ):
        if detalle.item.tipo != TipoItem.PRODUCTO:
            continue
        ItemMovimiento.objects.create(
            id=siguiente,
            item=detalle.item,
            unidad_medida=detalle.unidad_medida,
            tipo=TipoMovimiento.COMPRA,
            fecha_movimiento=compra.fecha,
            cantidad=detalle.cantidad,
            precio=detalle.costo,
            costo=detalle.costo,
            subtotal=detalle.subtotal,
            secuencia_origen=origen,
            secuencia_detalle_origen=orden,
            es_vigente=True,
        )
        siguiente += 1


def _actualizar_costos(compra, pendientes: list[PrecioPendiente]):
    por_item = {pendiente.item_id: pendiente for pendiente in pendientes}
    ahora = timezone.now()
    usuario = compra.usuario
    vistos = set()
    for detalle in compra.detalles.select_related("item", "unidad_medida", "item__unidad_medida"):
        item = detalle.item
        if item.tipo != TipoItem.PRODUCTO or item.pk in vistos:
            continue
        vistos.add(item.pk)
        costo_nuevo = costo_en_base(item, detalle.unidad_medida, detalle.costo)
        campos = ["ultimo_costo"]
        item.ultimo_costo = costo_nuevo
        pendiente = por_item.get(item.pk)
        if pendiente:
            anterior = item.precio
            item.precio = pendiente.precio_nuevo
            campos.append("precio")
            ItemPrecioHistorial.objects.create(
                item=item,
                precio_anterior=anterior,
                precio_nuevo=pendiente.precio_nuevo,
                ultimo_costo=costo_nuevo,
                porcentaje=None,
                segun_costo=True,
                origen=OrigenPrecio.COMPRA,
                usuario=usuario,
                fecha=ahora,
                lote=_secuencia(compra),
            )
        item.save(update_fields=campos)

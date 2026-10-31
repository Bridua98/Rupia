import io
import re
from datetime import date
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from PIL import Image

from inventario.imagenes import resolver_imagen
from inventario.models import (
    Item,
    ItemCategoria,
    ItemMovimiento,
    Marca,
    TasaIva,
    TipoItem,
    TipoMovimiento,
    UnidadMedida,
)
from inventario.views import ItemImagenView


@pytest.fixture
def usuario(django_user_model):
    return django_user_model.objects.create_user(
        "ada",
        "ada@rupia.local",
        "Clave-inicial-Rupia-2026",
    )


@pytest.fixture
def ingresada(client, usuario):
    client.force_login(usuario)
    return client


def _foraneos():
    marca = Marca.objects.create(descripcion="Genérica")
    categoria = ItemCategoria.objects.create(descripcion="Alimentos")
    unidad = UnidadMedida.objects.create(descripcion="Unidad", simbolo="UND")
    return marca, categoria, unidad


def _datos(marca, categoria, unidad, **extra):
    datos = {
        "descripcion": "Arroz 1kg",
        "tipo": TipoItem.PRODUCTO,
        "marca": marca.pk,
        "categoria": categoria.pk,
        "unidad_medida": unidad.pk,
        "precio": "8500",
        "tasa_iva": TasaIva.DIEZ,
        "activo": "on",
        "accion": "guardar",
    }
    datos.update(extra)
    return datos


@pytest.mark.django_db
def test_selector_pide_ingreso(client):
    response = client.get("/selector/marca/")

    assert response.status_code == 302
    assert response.url.startswith("/login/")


@pytest.mark.django_db
def test_selector_desconocido_no_existe(ingresada):
    response = ingresada.get("/selector/no-existe/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_selector_filtra_por_descripcion(ingresada):
    Marca.objects.create(descripcion="Alfa")
    Marca.objects.create(descripcion="Beta")

    response = ingresada.get("/selector/marca/?q=Alf")

    labels = [row["label"] for row in response.json()["results"]]
    assert labels == ["Alfa"]


@pytest.mark.django_db
def test_selector_filtra_unidad_por_simbolo(ingresada):
    UnidadMedida.objects.create(descripcion="Kilogramo", simbolo="kg")
    UnidadMedida.objects.create(descripcion="Metro", simbolo="m")

    response = ingresada.get("/selector/unidad/?q=kg")

    assert response.json()["results"] == [
        {"id": UnidadMedida.objects.get(simbolo="kg").pk, "label": "Kilogramo (kg)"},
    ]


@pytest.mark.django_db
def test_selector_rechaza_alta_invalida(ingresada):
    response = ingresada.post("/selector/marca/nueva/", {"marca-descripcion": "   "})

    assert response.status_code == 400
    assert response.json()["errors"]["marca-descripcion"] == ["Escribí la descripción."]
    assert Marca.objects.count() == 0


@pytest.mark.django_db
def test_selector_no_repite_la_marca(ingresada):
    Marca.objects.create(descripcion="Colón")

    response = ingresada.post("/selector/marca/nueva/", {"marca-descripcion": "Colón"})

    assert response.status_code == 400
    assert response.json()["errors"]["marca-descripcion"] == [
        "Ya hay una marca con esa descripción.",
    ]
    assert Marca.objects.count() == 1


@pytest.mark.django_db
def test_selector_crea_y_devuelve_el_registro(ingresada):
    response = ingresada.post("/selector/marca/nueva/", {"marca-descripcion": "Colón"})

    assert response.status_code == 200
    data = response.json()
    marca = Marca.objects.get(descripcion="Colón")
    assert data == {"id": marca.pk, "label": "Colón"}


@pytest.mark.django_db
def test_ficha_ofrece_el_selector_con_alta(ingresada):
    response = ingresada.get("/inventario/items/nueva/")

    content = response.content.decode()
    assert response.status_code == 200
    assert 'data-rupia="selector"' in content
    assert 'data-search-url="/selector/marca/"' in content
    assert 'data-create-url="/selector/marca/nueva/"' in content
    assert 'class="selector-nueva"' in content
    assert 'aria-label="Nueva marca"' in content
    assert 'name="marca-descripcion"' in content
    assert "Nueva categoría" in content
    assert "Nueva unidad" in content
    assert 'value="PRODUCTO" selected' in content
    activo = _control(content, "activo")
    assert activo is not None
    assert "checked" in activo.group(0)
    assert 'class="moneda-simbolo"' in content
    assert ">Gs.<" in content
    assert 'data-moneda="guarani"' in content
    assert 'src="/static/js/rupia-moneda.js"' in content


@pytest.mark.django_db
def test_alta_de_item_con_foraneos_existentes(ingresada):
    marca, categoria, unidad = _foraneos()

    response = ingresada.post(
        "/inventario/items/nueva/",
        _datos(marca, categoria, unidad),
    )

    item = Item.objects.get(descripcion="Arroz 1kg")
    assert item.marca_id == marca.pk
    assert item.categoria_id == categoria.pk
    assert item.unidad_medida_id == unidad.pk
    assert item.tipo == TipoItem.PRODUCTO
    assert item.precio == Decimal("8500.000")
    assert item.tasa_iva == TasaIva.DIEZ
    assert item.activo is True
    assert response.status_code == 302
    assert response.url == "/inventario/items/"
    pagina = ingresada.get(response.url)
    contenido = pagina.content.decode()
    assert 'class="detail-panel"' not in contenido
    assert 'class="list-filters is-open"' not in contenido
    assert pagina.status_code == 200
    assert "Arroz 1kg" in contenido
    assert "Producto" in contenido
    assert "Genérica" in contenido


@pytest.mark.django_db
def test_la_ficha_ofrece_las_tasas_de_iva(ingresada):
    content = ingresada.get("/inventario/items/nueva/").content.decode()
    tasa = _select(content, "tasa_iva")

    assert tasa is not None
    assert 'value="10" selected' in tasa
    assert 'value="5"' in tasa
    assert 'value="0"' in tasa
    assert ">10%<" in tasa
    assert ">5%<" in tasa
    assert ">0%<" in tasa


@pytest.mark.django_db
def test_alta_guarda_la_tasa_de_iva_elegida(ingresada):
    marca, categoria, unidad = _foraneos()

    response = ingresada.post(
        "/inventario/items/nueva/",
        _datos(marca, categoria, unidad, tasa_iva=TasaIva.CINCO),
    )

    item = Item.objects.get(descripcion="Arroz 1kg")
    assert item.tasa_iva == TasaIva.CINCO
    assert response.status_code == 302
    ficha = ingresada.get(f"/inventario/items/{item.pk}/").content.decode()
    tasa = _select(ficha, "tasa_iva")
    assert tasa is not None
    assert 'value="5" selected' in tasa
    listado = ingresada.get("/inventario/items/").content.decode()
    assert ">5%<" in listado


@pytest.mark.django_db
def test_alta_guarda_la_tasa_iva_exenta(ingresada):
    marca, categoria, unidad = _foraneos()

    response = ingresada.post(
        "/inventario/items/nueva/",
        _datos(marca, categoria, unidad, tasa_iva=TasaIva.CERO),
    )

    item = Item.objects.get(descripcion="Arroz 1kg")
    assert item.tasa_iva == TasaIva.CERO
    assert response.status_code == 302


@pytest.mark.django_db
def test_tasa_iva_rechaza_un_valor_fuera_del_enum(ingresada):
    marca, categoria, unidad = _foraneos()

    response = ingresada.post(
        "/inventario/items/nueva/",
        _datos(marca, categoria, unidad, tasa_iva="15"),
    )

    assert response.status_code == 200
    assert "Elegí una tasa de IVA válida." in response.content.decode()
    assert Item.objects.count() == 0


@pytest.mark.django_db
def test_filtro_por_tasa_de_iva_restringe_el_listado(ingresada):
    marca, categoria, unidad = _foraneos()
    Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion="Arroz 1kg",
        tipo=TipoItem.PRODUCTO,
        tasa_iva=TasaIva.DIEZ,
    )
    Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion="Fideos",
        tipo=TipoItem.PRODUCTO,
        tasa_iva=TasaIva.CINCO,
    )

    response = ingresada.get(f"/inventario/items/?tasa_iva={TasaIva.CINCO}&filtros=1")

    content = response.content.decode()
    assert response.status_code == 200
    assert "Fideos" in content
    assert "Arroz 1kg" not in content
    assert 'value="5" selected' in content


@pytest.mark.django_db
def test_alta_guarda_el_precio_con_mascara_de_guaranies(ingresada):
    marca, categoria, unidad = _foraneos()

    response = ingresada.post(
        "/inventario/items/nueva/",
        _datos(marca, categoria, unidad, precio="Gs. 1.250.000"),
    )

    item = Item.objects.get(descripcion="Arroz 1kg")
    assert item.precio == Decimal("1250000.000")
    assert response.status_code == 302

    ficha = ingresada.get(f"/inventario/items/{item.pk}/").content.decode()
    precio = _control(ficha, "precio")
    assert precio is not None
    assert 'value="1.250.000"' in precio.group(0)


@pytest.mark.django_db
def test_precio_rechaza_decimales(ingresada):
    marca, categoria, unidad = _foraneos()

    response = ingresada.post(
        "/inventario/items/nueva/",
        _datos(marca, categoria, unidad, precio="8.500,50"),
    )

    assert response.status_code == 200
    assert "El guaraní no admite decimales." in response.content.decode()
    assert Item.objects.count() == 0


@pytest.mark.django_db
def test_edicion_mantiene_activo_si_estaba_apagado(ingresada):
    marca, categoria, unidad = _foraneos()
    item = Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion="Arroz 1kg",
        tipo=TipoItem.PRODUCTO,
        activo=False,
    )

    html = ingresada.get(f"/inventario/items/{item.pk}/").content.decode()
    activo = _control(html, "activo")
    assert activo is not None
    assert "checked" not in activo.group(0)


@pytest.mark.django_db
def test_no_repite_la_descripcion_del_item(ingresada):
    marca, categoria, unidad = _foraneos()
    Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion="Arroz 1kg",
        tipo=TipoItem.PRODUCTO,
    )

    response = ingresada.post(
        "/inventario/items/nueva/",
        _datos(marca, categoria, unidad),
    )

    assert response.status_code == 200
    assert "Ya hay un ítem con esa descripción." in response.content.decode()
    assert Item.objects.count() == 1


@pytest.mark.django_db
def test_alta_sin_marca_no_graba(ingresada):
    marca, categoria, unidad = _foraneos()
    datos = _datos(marca, categoria, unidad)
    datos["marca"] = ""

    response = ingresada.post("/inventario/items/nueva/", datos)

    assert response.status_code == 200
    assert "Elegí una marca." in response.content.decode()
    assert Item.objects.count() == 0


@pytest.mark.django_db
def test_alta_usa_la_marca_creada_en_el_selector(ingresada):
    marca, categoria, unidad = _foraneos()
    creada = ingresada.post("/selector/marca/nueva/", {"marca-descripcion": "Molinos"})
    marca_id = creada.json()["id"]
    datos = _datos(marca, categoria, unidad)
    datos["marca"] = marca_id

    response = ingresada.post("/inventario/items/nueva/", datos)

    item = Item.objects.get(descripcion="Arroz 1kg")
    assert item.marca.descripcion == "Molinos"
    assert response.status_code == 302
    assert response.url == "/inventario/items/"
    pagina = ingresada.get(response.url)
    assert 'class="detail-panel"' not in pagina.content.decode()


@pytest.mark.django_db
def test_guardar_desde_el_listado_no_abre_el_panel_ni_filtra(ingresada):
    marca, categoria, unidad = _foraneos()
    Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion="Flete mensual",
        tipo=TipoItem.GASTO,
    )

    response = ingresada.post(
        "/inventario/items/nueva/",
        _datos(marca, categoria, unidad, desde="listado", filtro_tipo=TipoItem.GASTO),
    )

    assert response.status_code == 302
    assert response.url == f"/inventario/items/?tipo={TipoItem.GASTO}"
    pagina = ingresada.get(response.url)
    contenido = pagina.content.decode()
    assert 'class="detail-panel"' not in contenido
    assert "Flete mensual" in contenido
    assert "Arroz 1kg" not in contenido


@pytest.mark.django_db
def test_modificar_desde_el_listado_no_abre_el_panel_ni_filtra(ingresada):
    marca, categoria, unidad = _foraneos()
    item = Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion="Arroz 1kg",
        tipo=TipoItem.PRODUCTO,
    )

    response = ingresada.post(
        f"/inventario/items/{item.pk}/",
        _datos(marca, categoria, unidad, desde="listado"),
    )

    assert response.status_code == 302
    assert response.url == "/inventario/items/"
    pagina = ingresada.get(response.url)
    contenido = pagina.content.decode()
    assert 'class="detail-panel"' not in contenido
    assert 'class="list-filters is-open"' not in contenido
    assert "Arroz 1kg" in contenido


@pytest.mark.django_db
def test_edicion_conserva_los_foraneos(ingresada):
    marca, categoria, unidad = _foraneos()
    item = Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion="Arroz 1kg",
        tipo=TipoItem.PRODUCTO,
        precio=Decimal("8500.000"),
    )

    response = ingresada.post(
        f"/inventario/items/{item.pk}/",
        _datos(marca, categoria, unidad, descripcion="Arroz 2kg"),
    )

    item.refresh_from_db()
    assert item.descripcion == "Arroz 2kg"
    assert item.marca_id == marca.pk
    assert item.categoria_id == categoria.pk
    assert item.unidad_medida_id == unidad.pk
    assert response.status_code == 302


@pytest.mark.django_db
def test_no_elimina_item_con_movimiento(ingresada):
    marca, categoria, unidad = _foraneos()
    item = Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion="Arroz 1kg",
        tipo=TipoItem.PRODUCTO,
    )
    ItemMovimiento.objects.create(
        id=1,
        item=item,
        unidad_medida=unidad,
        tipo=TipoMovimiento.COMPRA,
        fecha_movimiento=date(2026, 10, 30),
        cantidad=Decimal("1.000"),
        precio=Decimal("8500.000"),
        costo=Decimal("6000.000"),
        subtotal=Decimal("8500.000"),
    )

    response = ingresada.post(f"/inventario/items/{item.pk}/eliminar/")

    assert response.status_code == 302
    assert response.url == f"/inventario/items/{item.pk}/"
    assert Item.objects.filter(pk=item.pk).exists()
    ficha = ingresada.get(response.url)
    assert "está en uso y no se puede eliminar." in ficha.content.decode()


def _control(html, name):
    patron = rf'<(input|textarea)\b(?:(?!>).)*\bname="{name}"(?:(?!>).)*>'
    return re.search(patron, html)


def _select(html, name):
    patron = rf'<select\b(?:(?!>).)*\bname="{name}"(?:(?!>).)*>.*?</select>'
    encontrado = re.search(patron, html, re.DOTALL)
    return encontrado.group(0) if encontrado else None


def _png(nombre="arroz.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), (10, 20, 30)).save(buffer, format="PNG")
    return SimpleUploadedFile(nombre, buffer.getvalue(), content_type="image/png")


@pytest.fixture
def carpeta_imagenes(tmp_path, settings):
    settings.RUPIA_IMAGENES_DIR = tmp_path
    return tmp_path


@pytest.mark.django_db
def test_el_listado_muestra_solo_el_simbolo(ingresada):
    marca, categoria, unidad = _foraneos()
    Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion="Arroz 1kg",
        tipo=TipoItem.PRODUCTO,
    )

    html = ingresada.get("/inventario/items/").content.decode()
    inicio = html.index('class="sheet"')
    hoja = html[inicio : html.index("</table>", inicio)]
    assert ">UND<" in hoja
    assert "Unidad (UND)" not in hoja
    assert "autofocus" not in html

    impreso = ingresada.get("/inventario/items/imprimir/").content.decode()
    assert ">UND<" in impreso
    assert "Unidad (UND)" not in impreso


@pytest.mark.django_db
def test_el_alta_empieza_en_el_codigo_de_barra(ingresada):
    content = ingresada.get("/inventario/items/nueva/").content.decode()
    codigo = _control(content, "codigo_barra")
    descripcion = _control(content, "descripcion")

    assert codigo and descripcion
    assert codigo.start() < descripcion.start()
    assert codigo.group(1) == "input"
    assert "autofocus" in codigo.group(0)
    assert descripcion.group(1) == "textarea"
    assert "autofocus" not in descripcion.group(0)
    assert 'enctype="multipart/form-data"' in content
    assert "data-imagen-input" in content


@pytest.mark.django_db
def test_el_panel_nuevo_enfoca_el_codigo(ingresada):
    content = ingresada.get("/inventario/items/?nueva=1").content.decode()
    codigo = _control(content, "codigo_barra")
    descripcion = _control(content, "descripcion")

    assert codigo and descripcion
    assert "autofocus" in codigo.group(0)
    assert descripcion.group(1) == "textarea"


@pytest.mark.django_db
def test_la_edicion_enfoca_la_descripcion(ingresada):
    marca, categoria, unidad = _foraneos()
    item = Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion="Arroz 1kg",
        tipo=TipoItem.PRODUCTO,
    )

    content = ingresada.get(f"/inventario/items/{item.pk}/").content.decode()
    codigo = _control(content, "codigo_barra")
    descripcion = _control(content, "descripcion")

    assert codigo and descripcion
    assert codigo.start() < descripcion.start()
    assert descripcion.group(1) == "input"
    assert "autofocus" in descripcion.group(0)
    assert "autofocus" not in codigo.group(0)


@pytest.mark.django_db
def test_guarda_la_imagen_como_ruta_relativa(ingresada, carpeta_imagenes):
    marca, categoria, unidad = _foraneos()
    datos = _datos(marca, categoria, unidad)
    datos["imagen_archivo"] = _png()

    response = ingresada.post("/inventario/items/nueva/", datos)

    item = Item.objects.get(descripcion="Arroz 1kg")
    assert response.status_code == 302
    assert item.imagen == "arroz.png"
    assert (carpeta_imagenes / "arroz.png").is_file()
    ficha = ingresada.get(f"/inventario/items/{item.pk}/").content.decode()
    assert f"/inventario/items/imagen/{item.imagen}/" in ficha
    imagen = ingresada.get(f"/inventario/items/imagen/{item.imagen}/")
    assert imagen.status_code == 200
    assert b"".join(imagen.streaming_content) == (carpeta_imagenes / item.imagen).read_bytes()


@pytest.mark.django_db
def test_la_imagen_pide_ingreso(client, carpeta_imagenes):
    response = client.get("/inventario/items/imagen/arroz.png/")

    assert response.status_code == 302
    assert response.url.startswith("/login/")


@pytest.mark.django_db
def test_no_sirve_una_ruta_fuera_de_la_carpeta(ingresada, carpeta_imagenes):
    assert resolver_imagen("../secreto.png") is None
    assert resolver_imagen("..\\secreto.png") is None
    assert resolver_imagen("C:/Windows/secreto.png") is None
    fuera = carpeta_imagenes.parent / "secreto.png"
    fuera.write_bytes(b"secreto")
    pedido = ingresada.get("/")
    with pytest.raises(Http404):
        ItemImagenView.as_view()(pedido.wsgi_request, nombre=str(fuera))
    faltante = ingresada.get("/inventario/items/imagen/no-esta.png/")
    assert faltante.status_code == 404


@pytest.mark.django_db
def test_reemplazar_borra_la_imagen_anterior(ingresada, carpeta_imagenes):
    marca, categoria, unidad = _foraneos()
    item = Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion="Arroz 1kg",
        tipo=TipoItem.PRODUCTO,
        imagen="vieja.png",
    )
    (carpeta_imagenes / "vieja.png").write_bytes(b"vieja")
    datos = _datos(marca, categoria, unidad)
    datos["imagen_archivo"] = _png("nueva.png")

    ingresada.post(f"/inventario/items/{item.pk}/", datos)

    item.refresh_from_db()
    assert item.imagen == "nueva.png"
    assert (carpeta_imagenes / "nueva.png").is_file()
    assert not (carpeta_imagenes / "vieja.png").exists()


@pytest.mark.django_db
def test_no_borra_la_imagen_si_otro_item_la_usa(ingresada, carpeta_imagenes):
    marca, categoria, unidad = _foraneos()
    item = Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion="Arroz 1kg",
        tipo=TipoItem.PRODUCTO,
        imagen="vieja.png",
    )
    otro = Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion="Fideos",
        tipo=TipoItem.PRODUCTO,
        imagen="vieja.png",
    )
    (carpeta_imagenes / "vieja.png").write_bytes(b"vieja")
    datos = _datos(marca, categoria, unidad)
    datos["imagen_archivo"] = _png("nueva.png")

    ingresada.post(f"/inventario/items/{item.pk}/", datos)

    item.refresh_from_db()
    otro.refresh_from_db()
    assert item.imagen == "nueva.png"
    assert otro.imagen == "vieja.png"
    assert (carpeta_imagenes / "vieja.png").read_bytes() == b"vieja"


@pytest.mark.django_db
def test_quitar_imagen_borra_el_archivo(ingresada, carpeta_imagenes):
    marca, categoria, unidad = _foraneos()
    item = Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion="Arroz 1kg",
        tipo=TipoItem.PRODUCTO,
        imagen="arroz.png",
    )
    (carpeta_imagenes / "arroz.png").write_bytes(_png().read())
    datos = _datos(marca, categoria, unidad)
    datos["quitar_imagen"] = "on"

    ingresada.post(f"/inventario/items/{item.pk}/", datos)

    item.refresh_from_db()
    assert item.imagen is None
    assert not (carpeta_imagenes / "arroz.png").exists()


@pytest.mark.django_db
def test_si_el_nombre_esta_usado_agrega_sufijo(ingresada, carpeta_imagenes):
    marca, categoria, unidad = _foraneos()
    Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion="Fideos",
        tipo=TipoItem.PRODUCTO,
        imagen="arroz.png",
    )
    datos = _datos(marca, categoria, unidad)
    datos["imagen_archivo"] = _png("arroz.png")

    ingresada.post("/inventario/items/nueva/", datos)

    nuevo = Item.objects.get(descripcion="Arroz 1kg")
    assert nuevo.imagen == "arroz-2.png"
    assert (carpeta_imagenes / "arroz-2.png").is_file()


@pytest.mark.django_db
def test_rechaza_una_extension_que_no_es_imagen(ingresada, carpeta_imagenes):
    marca, categoria, unidad = _foraneos()
    datos = _datos(marca, categoria, unidad)
    datos["imagen_archivo"] = _png("foto.bmp")

    response = ingresada.post("/inventario/items/nueva/", datos)

    assert response.status_code == 200
    assert "JPG, PNG, WEBP o GIF" in response.content.decode()
    assert Item.objects.count() == 0
    assert list(carpeta_imagenes.iterdir()) == []


@pytest.mark.django_db
def test_busca_item_por_marca_vinculada(ingresada):
    marca, categoria, unidad = _foraneos()
    Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion="Arroz 1kg",
        tipo=TipoItem.PRODUCTO,
    )

    response = ingresada.get("/inventario/items/?q=Gen")

    content = response.content.decode()
    assert response.status_code == 200
    assert "Arroz 1kg" in content


@pytest.mark.django_db
def test_busca_item_por_codigo_de_barra(ingresada):
    marca, categoria, unidad = _foraneos()
    Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion="Arroz 1kg",
        tipo=TipoItem.PRODUCTO,
        codigo_barra="7790001112223",
    )

    response = ingresada.get("/inventario/items/?q=7790001112223")

    content = response.content.decode()
    assert response.status_code == 200
    assert "Arroz 1kg" in content


@pytest.mark.django_db
def test_filtro_por_tipo_restringe_el_listado(ingresada):
    marca, categoria, unidad = _foraneos()
    Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion="Arroz 1kg",
        tipo=TipoItem.PRODUCTO,
    )
    Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion="Flete mensual",
        tipo=TipoItem.GASTO,
    )

    response = ingresada.get(f"/inventario/items/?tipo={TipoItem.PRODUCTO}&filtros=1")

    content = response.content.decode()
    assert response.status_code == 200
    assert "Arroz 1kg" in content
    assert "Flete mensual" not in content


@pytest.mark.django_db
def test_exportacion_respeta_el_filtro_de_tipo(ingresada):
    from io import BytesIO

    from openpyxl import load_workbook

    marca, categoria, unidad = _foraneos()
    Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion="Arroz 1kg",
        tipo=TipoItem.PRODUCTO,
    )
    Item.objects.create(
        marca=marca,
        categoria=categoria,
        unidad_medida=unidad,
        descripcion="Flete mensual",
        tipo=TipoItem.GASTO,
    )

    response = ingresada.get(f"/inventario/items/exportar.xlsx?tipo={TipoItem.PRODUCTO}")

    filas = list(load_workbook(BytesIO(response.content)).active.values)
    descripciones = [fila[0] for fila in filas[1:]]
    assert "Arroz 1kg" in descripciones
    assert "Flete mensual" not in descripciones


@pytest.mark.django_db
def test_el_panel_nuevo_se_abre_como_lamina(ingresada):
    response = ingresada.get("/inventario/items/?nueva=1")

    content = response.content.decode()
    assert response.status_code == 200
    assert 'class="ledger is-overlay"' in content
    assert 'class="ledger-backdrop"' in content
    assert 'data-filters-toggle' in content


@pytest.mark.django_db
def test_el_menu_muestra_items(ingresada):
    response = ingresada.get("/")

    content = response.content.decode()
    assert 'href="/inventario/items/"' in content
    assert "Ítems" in content

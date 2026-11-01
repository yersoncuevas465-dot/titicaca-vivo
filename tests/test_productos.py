"""Productos y artesanías (v2.9, tabla 21 y rol residente): la página pública sale de la base,
el residente publica solo en su comunidad y solo lo suyo, el operador publica los de la agencia
y oculta lo que no corresponde, el admin solo mira, y nadie más ve nada del personal."""

import io
import re
from pathlib import Path

import pytest
from PIL import Image

from tests.conftest import consultar_valor, ejecutar_y_confirmar, iniciar_sesion, token_csrf
from tests.test_accesibilidad import problemas

# Lo que se ve en la página: publicado, de la agencia o de un residente activo, en Puno o en una
# comunidad activa (las mismas reglas de modelos/producto.py)
VISIBLES = """SELECT COUNT(*) AS n FROM producto p
              LEFT JOIN comunidad c ON c.id = p.comunidad_id
              LEFT JOIN usuario u ON u.id = p.residente_id
              WHERE p.estado = 'publicado' AND (p.residente_id IS NULL OR u.activo = 1)
                AND (p.comunidad_id IS NULL OR c.activa = 1)"""
PRODUCTO = {"nombre": "Ojotas de prueba", "categoria": "artesania", "precio": "22.50",
            "descripcion": "Sandalias de llanta reciclada, talla 38 a 42.",
            "lugar": "Mi casa, junto al muelle", "comunidad_id": "3"}


def tarjetas(html):
    return html.count('<li class="producto">')


def tiene_tarjeta(html, nombre):
    """La tarjeta del producto (el aviso «Listo: …» también lleva el nombre)."""
    return f'class="producto__nombre">{nombre}<' in html


def entrar(app, usuario):
    cliente = app.test_client()
    iniciar_sesion(cliente, usuario)
    return cliente


def publicar(cliente, **cambios):
    csrf = token_csrf(cliente.get("/panel/productos/nuevo"))
    return cliente.post("/panel/productos/nuevo", data={**PRODUCTO, **cambios, "csrf_token": csrf})


def cambiar_estado(cliente, producto_id, estado):
    csrf = token_csrf(cliente.get("/panel/productos"))
    return cliente.post(f"/panel/productos/{producto_id}/estado",
                        data={"csrf_token": csrf, "estado": estado})


def borrar_los_de_prueba(app):
    ejecutar_y_confirmar(app, "DELETE FROM bitacora WHERE tabla_afectada = 'producto' AND registro_id "
                              "IN (SELECT id FROM producto WHERE nombre = 'Ojotas de prueba')")
    ejecutar_y_confirmar(app, "DELETE FROM producto WHERE nombre = 'Ojotas de prueba'")


# --- Lo que ve el turista -----------------------------------------------------------------------

def test_la_pagina_de_productos_sale_de_la_base(app, cliente):
    html = cliente.get("/productos").get_data(True)
    assert tarjetas(html) == consultar_valor(app, VISIBLES)
    assert tiene_tarjeta(html, "Chullo tejido a mano")
    assert not tiene_tarjeta(html, "Quinua de Amantaní")                          # retirado
    assert "Juana Machaca Huatta, residente de Taquile" in html and "La agencia Titicaca Vivo" in html
    assert 'aria-current="page">Productos</a>' in html and problemas(html) == []


@pytest.mark.parametrize("filtro, donde", [
    ("lugar=taquile", "c.slug = 'taquile'"),
    ("lugar=puno", "p.comunidad_id IS NULL"),
    ("categoria=textil", "p.categoria = 'textil'"),
    ("lugar=amantani&categoria=artesania", "c.slug = 'amantani' AND p.categoria = 'artesania'"),
])
def test_los_filtros_de_lugar_y_tipo(app, cliente, filtro, donde):
    html = cliente.get(f"/productos?{filtro}").get_data(True)
    assert tarjetas(html) == consultar_valor(app, f"{VISIBLES} AND {donde}")
    assert 'aria-current="true"' in html


def test_un_filtro_desconocido_muestra_todo(app, cliente):
    html = cliente.get("/productos", query_string={"lugar": "<script>", "categoria": "x"}).get_data(True)
    assert tarjetas(html) == consultar_valor(app, VISIBLES) and "<script>" not in html


def test_la_portada_muestra_los_3_mas_nuevos(cliente):
    html = cliente.get("/").get_data(True)
    seccion = html.split('id="titulo-productos"', 1)[1]
    assert tarjetas(seccion) == 3 and 'href="/productos"' in seccion
    assert tiene_tarjeta(seccion, "Balsa de totora en miniatura")        # el más nuevo de la semilla


def test_productos_en_ingles(cliente):
    cliente.get("/idioma/en")
    html = cliente.get("/productos").get_data(True)
    assert "Products and crafts" in html and "Weaving and embroidery" in html and "Sold by" in html
    assert "in Spanish" in html and problemas(html) == []


# --- El residente -------------------------------------------------------------------------------

def test_el_residente_publica_solo_en_su_comunidad(app):
    juana = entrar(app, "residente.juana")
    formulario = juana.get("/panel/productos/nuevo").get_data(True)
    assert 'name="comunidad_id"' not in formulario and "Taquile" in formulario
    try:
        respuesta = publicar(juana, comunidad_id="3")                     # intenta Amantaní
        assert respuesta.status_code == 303 and respuesta.headers["Location"] == "/panel/productos"
        fila = consultar_valor(app, "SELECT CONCAT(residente_id, '-', comunidad_id) AS f FROM producto "
                                    "WHERE nombre = 'Ojotas de prueba'")
        assert fila == "7-2"                                            # Juana, en Taquile
        assert tiene_tarjeta(juana.get("/productos?lugar=taquile").get_data(True), "Ojotas de prueba")
        assert consultar_valor(app, "SELECT COUNT(*) AS n FROM bitacora WHERE accion = 'creacion' "
                                    "AND tabla_afectada = 'producto' AND usuario_id = 7") >= 1
    finally:
        borrar_los_de_prueba(app)


def test_el_residente_no_toca_lo_ajeno(app):
    juana = entrar(app, "residente.juana")
    lista = juana.get("/panel/productos").get_data(True)
    assert "Chullo tejido a mano" in lista and "Tapiz de lana de oveja" not in lista   # de Félix
    assert juana.get("/panel/productos/6/editar").status_code == 404
    assert juana.get("/panel/productos/1/editar").status_code == 404                  # de la agencia
    assert cambiar_estado(juana, 6, "retirado").status_code == 403
    assert consultar_valor(app, "SELECT estado FROM producto WHERE id = 6") == "publicado"


@pytest.mark.parametrize("url", ["/panel/salidas", "/panel/salidas/10/pasajeros", "/panel/pagos",
                                 "/panel/reservas", "/panel/abordaje", "/panel/usuarios",
                                 "/panel/bitacora", "/panel/catalogos", "/panel/reclamaciones",
                                 "/panel/alertas", "/panel/indicadores"])
def test_el_residente_no_ve_nada_del_personal(app, url):
    assert entrar(app, "residente.juana").get(url).status_code == 403


def test_el_resumen_y_el_menu_del_residente(app):
    juana = entrar(app, "residente.juana")
    html = juana.get("/panel").get_data(True)
    assert "Residente de Taquile" in html and "2 publicado(s)" in html
    menu = html.split('aria-label="Panel"', 1)[1].split("</nav>", 1)[0]
    assert re.findall(r'href="(/panel[^"]*)"', menu) == ["/panel", "/panel/productos", "/panel/mi-cuenta"]
    cuenta = juana.get("/panel/mi-cuenta").get_data(True)
    assert "Publica sus artesanías y productos" in cuenta and problemas(cuenta) == []


def test_retirar_y_volver_a_publicar(app):
    juana = entrar(app, "residente.juana")
    try:
        assert cambiar_estado(juana, 5, "retirado").status_code == 303
        assert not tiene_tarjeta(juana.get("/productos").get_data(True), "Chumpi: faja calendario")
        assert cambiar_estado(juana, 5, "oculto").status_code == 422      # eso es de la agencia
        assert cambiar_estado(juana, 5, "publicado").status_code == 303
        assert tiene_tarjeta(juana.get("/productos").get_data(True), "Chumpi: faja calendario")
        assert consultar_valor(app, "SELECT COUNT(*) AS n FROM bitacora WHERE accion = 'cambio_estado' "
                                    "AND tabla_afectada = 'producto' AND registro_id = 5") >= 2
    finally:
        ejecutar_y_confirmar(app, "UPDATE producto SET estado = 'publicado' WHERE id = 5")


# --- El operador y el admin ---------------------------------------------------------------------

def test_el_operador_oculta_y_solo_el_lo_vuelve_a_mostrar(app):
    operador, sonia = entrar(app, "operador"), entrar(app, "residente.sonia")
    try:
        assert cambiar_estado(operador, 9, "oculto").status_code == 303
        assert not tiene_tarjeta(operador.get("/productos").get_data(True), "Bordado de los Uros")
        lista = sonia.get("/panel/productos").get_data(True)
        assert "Oculto por la agencia" in lista and "Volver a publicar" not in lista.split("Bordado de los Uros", 1)[1].split("</tr>", 1)[0]
        otra = cambiar_estado(sonia, 9, "publicado")
        assert otra.status_code == 422 and "no se puede hacer" in otra.get_data(True)
        assert cambiar_estado(operador, 9, "publicado").status_code == 303
        assert tiene_tarjeta(operador.get("/productos").get_data(True), "Bordado de los Uros")
    finally:
        ejecutar_y_confirmar(app, "UPDATE producto SET estado = 'publicado' WHERE id = 9")


def test_el_operador_publica_los_de_la_agencia_en_puno(app):
    operador = entrar(app, "operador")
    assert operador.get("/panel/productos/4/editar").status_code == 404     # es de Juana
    try:
        assert publicar(operador, comunidad_id="0").status_code == 303
        fila = consultar_valor(app, "SELECT CONCAT(COALESCE(residente_id, 'agencia'), '-', "
                                    "COALESCE(comunidad_id, 'puno')) AS f FROM producto "
                                    "WHERE nombre = 'Ojotas de prueba'")
        assert fila == "agencia-puno"
        assert tiene_tarjeta(operador.get("/productos?lugar=puno").get_data(True), "Ojotas de prueba")
    finally:
        borrar_los_de_prueba(app)


def test_el_admin_solo_mira(app):
    admin = entrar(app, "admin")
    html = admin.get("/panel/productos").get_data(True)
    assert "Chullo tejido a mano" in html and 'href="/panel/productos/nuevo"' not in html
    assert admin.get("/panel/productos/nuevo").status_code == 403
    assert cambiar_estado(admin, 1, "retirado").status_code == 403


@pytest.mark.parametrize("cambios, campo", [
    ({"nombre": ""}, "nombre"),
    ({"precio": "gratis"}, "precio"),
    ({"precio": "0"}, "precio"),
    ({"precio": "20000"}, "precio"),
    ({"categoria": "piratas"}, "categoria"),
    ({"descripcion": "corta"}, "descripcion"),
    ({"lugar": ""}, "lugar"),
])
def test_un_producto_mal_llenado_da_422_junto_al_campo(app, cambios, campo):
    juana = entrar(app, "residente.juana")
    antes = consultar_valor(app, "SELECT COUNT(*) AS n FROM producto")
    respuesta = publicar(juana, **cambios)
    assert respuesta.status_code == 422 and f'id="{campo}-error"' in respuesta.get_data(True)
    assert consultar_valor(app, "SELECT COUNT(*) AS n FROM producto") == antes


def test_un_residente_desactivado_no_muestra_sus_productos(app, cliente):
    ejecutar_y_confirmar(app, "UPDATE usuario SET activo = 0 WHERE nombre_usuario = 'residente.sonia'")
    try:
        html = cliente.get("/productos").get_data(True)
        assert not tiene_tarjeta(html, "Bordado de los Uros")
        assert tarjetas(html) == consultar_valor(app, VISIBLES)
    finally:
        ejecutar_y_confirmar(app, "UPDATE usuario SET activo = 1 WHERE nombre_usuario = 'residente.sonia'")


# --- Las cuentas de los residentes --------------------------------------------------------------

def test_el_admin_crea_un_residente_con_su_comunidad(app):
    admin = entrar(app, "admin")
    csrf = token_csrf(admin.get("/panel/usuarios/nuevo"))
    datos = {"csrf_token": csrf, "nombre_usuario": "residente.prueba", "nombre_completo": "Rosa Prueba",
             "rol_id": "5", "comunidad_id": "0", "licencia_navegacion": "",
             "contrasena": "Clave-larga-26", "activo": "y"}
    malo = admin.post("/panel/usuarios/nuevo", data=datos)
    assert malo.status_code == 422 and "El residente necesita una comunidad activa." in malo.get_data(True)
    try:
        assert admin.post("/panel/usuarios/nuevo", data={**datos, "comunidad_id": "6"}).status_code == 303
        rosa = app.test_client()
        assert iniciar_sesion(rosa, "residente.prueba", "Clave-larga-26").status_code == 302
        assert "Residente de Ticonata" in rosa.get("/panel").get_data(True)
        assert rosa.get("/panel/salidas").status_code == 403
    finally:
        ejecutar_y_confirmar(app, "DELETE FROM bitacora WHERE usuario_id = "
                                  "(SELECT id FROM usuario WHERE nombre_usuario = 'residente.prueba')")
        ejecutar_y_confirmar(app, "DELETE FROM usuario WHERE nombre_usuario = 'residente.prueba'")


def test_un_residente_con_productos_no_cambia_de_rol_ni_de_comunidad(app):
    admin = entrar(app, "admin")
    csrf = token_csrf(admin.get("/panel/usuarios/7"))
    datos = {"csrf_token": csrf, "nombre_usuario": "residente.juana", "nombre_completo": "Juana Machaca Huatta",
             "rol_id": "5", "comunidad_id": "3", "licencia_navegacion": "", "telefono": "900000107",
             "contrasena": "", "activo": "y"}
    otra_comunidad = admin.post("/panel/usuarios/7", data=datos)
    assert otra_comunidad.status_code == 422 and "producto(s) publicados" in otra_comunidad.get_data(True)
    otro_rol = admin.post("/panel/usuarios/7", data={**datos, "rol_id": "3", "comunidad_id": "2"})
    assert otro_rol.status_code == 422 and "producto(s) publicados" in otro_rol.get_data(True)
    assert consultar_valor(app, "SELECT CONCAT(rol_id, '-', comunidad_id) AS f FROM usuario WHERE id = 7") == "5-2"


# --- Fotos (D-121) -------------------------------------------------------------------------------

def foto_de_celular(tamano=(1600, 1200)):
    """Un JPG en memoria con metadatos, como el de un celular (la marca del teléfono)."""
    memoria, exif = io.BytesIO(), Image.Exif()
    exif[0x010F] = "Celular de prueba"
    Image.new("RGB", tamano, (190, 40, 90)).save(memoria, "JPEG", exif=exif)
    memoria.seek(0)
    return memoria


def subidas(app):
    return set((Path(app.config["SUBIDAS_CARPETA"]) / "productos").glob("*.webp"))


def test_las_fotos_de_la_semilla_se_ven_con_su_credito(cliente):
    html = cliente.get("/productos").get_data(True)
    assert 'src="/estaticos/img/productos/chullo-taquile.webp?v=' in html
    assert 'alt="Chullo tejido a mano"' in html and "Foto: Thomas Quine · CC BY 2.0 · Wikimedia Commons" in html
    assert cliente.get("/estaticos/img/productos/chullo-taquile.webp").status_code == 200
    portada = cliente.get("/").get_data(True).split('id="titulo-productos"', 1)[1]
    assert portada.count('src="/estaticos/img/productos/') == 3                # los 3 de la portada


def test_el_residente_sube_la_foto_de_su_producto_sin_metadatos(app):
    juana, antes = entrar(app, "residente.juana"), subidas(app)
    try:
        assert publicar(juana, foto=(foto_de_celular(), "mi-foto.jpg")).status_code == 303
        foto = consultar_valor(app, "SELECT foto FROM producto WHERE nombre = 'Ojotas de prueba'")
        assert foto.startswith("subidas/productos/") and consultar_valor(
            app, "SELECT foto_credito FROM producto WHERE nombre = 'Ojotas de prueba'") is None
        url = "/fotos/productos/" + foto.rsplit("/", 1)[1]
        assert f'src="{url}"' in juana.get("/productos?lugar=taquile").get_data(True)
        respuesta = juana.get(url)
        datos = respuesta.get_data()
        respuesta.close()                                     # suelta el archivo (Windows)
        assert respuesta.status_code == 200 and respuesta.mimetype == "image/webp"
        assert b"Celular de prueba" not in datos                                  # sin metadatos
        with Image.open(io.BytesIO(datos)) as imagen:
            assert imagen.size == (640, 400) and not imagen.getexif()
        # Al cambiarla por otra, la anterior se borra
        producto_id = consultar_valor(app, "SELECT id FROM producto WHERE nombre = 'Ojotas de prueba'")
        csrf = token_csrf(juana.get(f"/panel/productos/{producto_id}/editar"))
        otra = juana.post(f"/panel/productos/{producto_id}/editar",
                          data={**PRODUCTO, "csrf_token": csrf, "foto": (foto_de_celular((900, 900)), "otra.png")})
        assert otra.status_code == 303 and len(subidas(app) - antes) == 1
        assert juana.get(url).status_code == 404
    finally:
        for archivo in subidas(app) - antes:
            archivo.unlink(missing_ok=True)      # la carpeta es la temporal del sistema
        borrar_los_de_prueba(app)


def test_editar_sin_foto_nueva_deja_la_que_tenia(app):
    juana = entrar(app, "residente.juana")
    csrf = token_csrf(juana.get("/panel/productos/4/editar"))
    datos = {**PRODUCTO, "nombre": "Chullo tejido a mano", "comunidad_id": "", "csrf_token": csrf}
    try:
        assert juana.post("/panel/productos/4/editar", data=datos).status_code == 303
        assert consultar_valor(app, "SELECT foto FROM producto WHERE id = 4") == "img/productos/chullo-taquile.webp"
    finally:
        ejecutar_y_confirmar(app, "UPDATE producto SET categoria = 'textil', precio = 60.00, "
                                  "descripcion = 'Gorro de lana de oveja teñida con plantas, tejido con agujas "
                                  "finas por los varones de la isla. Sus colores dicen si quien lo usa es soltero "
                                  "o casado.', lugar = 'Tienda comunal de la plaza principal (pregunta por Juana)' "
                                  "WHERE id = 4")


def test_lo_que_no_es_una_foto_da_422_y_no_deja_nada(app):
    juana, antes = entrar(app, "residente.juana"), subidas(app)
    cuantos = consultar_valor(app, "SELECT COUNT(*) AS n FROM producto")
    respuesta = publicar(juana, foto=(io.BytesIO(b"<script>no soy una foto</script>"), "foto.jpg"))
    assert respuesta.status_code == 422 and 'id="foto-error"' in respuesta.get_data(True)
    assert consultar_valor(app, "SELECT COUNT(*) AS n FROM producto") == cuantos and subidas(app) == antes


def test_una_foto_de_mas_de_8_mb_da_413_con_su_aviso(app):
    juana = entrar(app, "residente.juana")
    respuesta = publicar(juana, foto=(io.BytesIO(bytes(9 * 1024 * 1024)), "enorme.jpg"))
    assert respuesta.status_code == 413 and "La foto pesa demasiado" in respuesta.get_data(True)


@pytest.mark.parametrize("nombre", ["..%2F..%2F.env", "abc.webp", "0123456789abcdef0123.webp",
                                    "0123456789abcdef0123.svg"])
def test_la_ruta_de_fotos_solo_sirve_nombres_propios(cliente, nombre):
    assert cliente.get(f"/fotos/productos/{nombre}").status_code == 404

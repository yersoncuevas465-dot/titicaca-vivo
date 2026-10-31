"""Mejoras de la versión 2.1: reservas en el panel (buscar, ficha con historial y venta del
operador en el muelle o por WhatsApp), reservas sin pago que vencen solas y los mapas de cada
salida, comunidad y alerta. (El capitán y el guía en dos lanchas a la vez: test_reglas_salida.py.)
"""

import itertools
import json
import re
from datetime import date, timedelta

import pytest

from app import tareas
from tests.conftest import (
    consultar_valor,
    ejecutar_y_confirmar,
    iniciar_sesion,
    reservar_en,
    token_csrf,
)

_documentos = itertools.count(1)


def _formulario_y_datos(cliente, salida_id, **extra):
    """GET del formulario de reserva y los datos de un POST válido (documentos 7996xxxx)."""
    pagina = cliente.get(f"/salidas/{salida_id}/reservar")
    html = pagina.get_data(True)
    token = re.search(r'name="token_envio" type="hidden" value="([0-9a-f]{32})"', html).group(1)
    datos = {
        "csrf_token": token_csrf(pagina), "token_envio": token,
        "titular_nombres": "Rosa", "titular_apellidos": "Prueba Mejora",
        "titular_tipo_documento": "DNI", "titular_numero_documento": f"7996{next(_documentos):04d}",
        "titular_nacionalidad": "PE", "telefono": "912345678", "correo": "",
        "titular_viaja": "y", "titular_tipo_pasajero_id": "1", "metodo_pago": "muelle", **extra,
    }
    return html, datos


def _creacion(app, codigo):
    """(usuario_id, detalle) de la bitácora que anotó la creación de la reserva."""
    usuario_id = consultar_valor(
        app, "SELECT b.usuario_id FROM bitacora b JOIN reserva r ON r.id = b.registro_id "
             "WHERE b.tabla_afectada = 'reserva' AND b.accion = 'creacion' AND r.codigo = %s",
        (codigo,))
    detalle = consultar_valor(
        app, "SELECT b.detalle FROM bitacora b JOIN reserva r ON r.id = b.registro_id "
             "WHERE b.tabla_afectada = 'reserva' AND b.accion = 'creacion' AND r.codigo = %s",
        (codigo,))
    return usuario_id, json.loads(detalle)


# --- Reservas en el panel: permisos, búsqueda y ficha -------------------------------------------

@pytest.mark.parametrize("usuario, codigo", [("admin", 200), ("operador", 200),
                                             ("guia.elena", 403), ("capitan.teodoro", 403)])
def test_las_reservas_del_panel_son_solo_de_la_oficina(app, usuario, codigo):
    cliente = app.test_client()
    iniciar_sesion(cliente, usuario)
    for url in ("/panel/reservas", "/panel/reservas?q=TV-WWUQ", "/panel/reservas/TV-WWUQ"):
        respuesta = cliente.get(url)
        assert respuesta.status_code == codigo, (usuario, url)
        if codigo == 200:
            assert respuesta.headers["Cache-Control"] == "no-store"


def test_el_menu_lleva_a_reservas_solo_a_la_oficina(app):
    for usuario, ve in (("admin", True), ("operador", True), ("guia.elena", False)):
        cliente = app.test_client()
        iniciar_sesion(cliente, usuario)
        assert ('href="/panel/reservas"' in cliente.get("/panel").get_data(True)) is ve, usuario


def test_buscar_por_codigo_documento_y_nombre_del_titular_o_de_un_pasajero(app, cliente, salida_prueba):
    codigo = reservar_en(app, salida_prueba(), acompanantes=1)       # Ana y Leo «Prueba Panel»
    titular = consultar_valor(app, "SELECT t.numero_documento FROM reserva r "
                                   "JOIN turista t ON t.id = r.turista_id WHERE r.codigo = %s", (codigo,))
    acompanante = consultar_valor(app, "SELECT rp.numero_documento FROM reserva_pasajero rp "
                                       "JOIN reserva r ON r.id = rp.reserva_id "
                                       "WHERE r.codigo = %s AND rp.nombres = 'Leo'", (codigo,))
    iniciar_sesion(cliente, "operador")
    enlace = f'href="/panel/reservas/{codigo}"'
    for texto in (codigo, f" {codigo.lower()} ", titular, acompanante, "leo prueba", "Ana Prueba Panel"):
        html = cliente.get("/panel/reservas", query_string={"q": texto}).get_data(True)
        assert enlace in html, texto
    # Con menos de 3 letras no busca por nombre; % y _ son letras, no comodines de LIKE.
    for texto in ("An", "%%%", "___"):
        html = cliente.get("/panel/reservas", query_string={"q": texto}).get_data(True)
        assert enlace not in html and "Ninguna reserva coincide" in html, texto
    assert enlace in cliente.get("/panel/reservas").get_data(True)       # entre las últimas


def test_la_ficha_tiene_pasajeros_pagos_historial_y_el_mensaje_de_whatsapp(app, cliente, salida_prueba):
    codigo = reservar_en(app, salida_prueba(), acompanantes=1, metodo="yape")
    iniciar_sesion(cliente, "operador")
    html = cliente.get(f"/panel/reservas/{codigo}").get_data(True)
    assert f"<h1>Reserva {codigo}</h1>" in html and "Pendiente de pago" in html
    assert "Ana Prueba Panel" in html and "Leo Prueba Panel" in html
    assert "Creación" in html and "Turista o sistema" in html            # la bitácora de la reserva
    assert f'href="/panel/abordaje/{codigo}?via=manual"' in html          # cobrar y embarcar
    # WhatsApp al celular del titular, con el código y sin su documento
    enlace = re.search(r'href="(https://wa\.me/51987654321\?text=[^"]+)"', html)
    assert enlace and codigo in enlace.group(1)
    mensaje = re.search(r'<textarea[^>]*id="texto-whatsapp"[^>]*>([^<]*)</textarea>', html).group(1)
    documento = consultar_valor(app, "SELECT t.numero_documento FROM reserva r "
                                     "JOIN turista t ON t.id = r.turista_id WHERE r.codigo = %s", (codigo,))
    assert codigo in mensaje and f"/mi-reserva?codigo={codigo}" in mensaje and documento not in mensaje
    assert cliente.get("/panel/reservas/TV-0000").status_code == 404     # no tiene la forma TV-XXXX
    assert cliente.get("/panel/reservas/TV-ZZZZ").status_code == 404     # no existe


def test_el_admin_mira_la_ficha_sin_botones_de_operacion(app):
    cliente = app.test_client()
    iniciar_sesion(cliente, "admin")
    html = cliente.get("/panel/reservas/TV-WWUQ").get_data(True)
    assert "wa.me" not in html and "/panel/abordaje/" not in html
    assert 'href="/reservas/TV-WWUQ/boleto"' in html                     # el boleto sí lo mira


def test_la_oficina_ve_el_boleto_sin_pedir_el_documento(app):
    for usuario, codigo in (("operador", 200), ("admin", 200), ("guia.elena", 302)):
        cliente = app.test_client()
        iniciar_sesion(cliente, usuario)
        assert cliente.get("/reservas/TV-WWUQ/boleto").status_code == codigo, usuario
    assert app.test_client().get("/reservas/TV-WWUQ/boleto").status_code == 302   # turista: a «Mi reserva»


# --- Venta del operador en el muelle o por WhatsApp ----------------------------------------------

def test_el_operador_vende_por_whatsapp_y_la_venta_queda_a_su_nombre(app, salida_prueba):
    salida_id = salida_prueba()
    cliente = app.test_client()
    iniciar_sesion(cliente, "operador")
    html, datos = _formulario_y_datos(cliente, salida_id, canal="whatsapp")
    assert "Venta del operador" in html and '<select class="campo__control" id="canal" name="canal"' in html
    respuesta = cliente.post(f"/salidas/{salida_id}/reservar", data=datos)
    assert respuesta.status_code == 303
    codigo = respuesta.headers["Location"].rsplit("/", 1)[1]
    assert respuesta.headers["Location"] == f"/panel/reservas/{codigo}"  # sigue en el panel
    assert consultar_valor(app, "SELECT canal FROM reserva WHERE codigo = %s", (codigo,)) == "whatsapp"
    usuario_id, detalle = _creacion(app, codigo)
    assert usuario_id == 2 and detalle["canal"] == "whatsapp"            # 2: el operador de la semilla
    ficha = cliente.get(respuesta.headers["Location"]).get_data(True)
    assert f"Listo: la reserva {codigo} quedó registrada (WhatsApp)" in ficha
    assert "<dd>WhatsApp · registrada el" in ficha


def test_un_canal_que_no_existe_queda_como_muelle(app, salida_prueba):
    salida_id = salida_prueba()
    cliente = app.test_client()
    iniciar_sesion(cliente, "operador")
    _, datos = _formulario_y_datos(cliente, salida_id, canal="web' OR 1=1")
    codigo = cliente.post(f"/salidas/{salida_id}/reservar", data=datos).headers["Location"].rsplit("/", 1)[1]
    assert consultar_valor(app, "SELECT canal FROM reserva WHERE codigo = %s", (codigo,)) == "mostrador"


@pytest.mark.parametrize("usuario", [None, "admin", "guia.elena"])
def test_solo_el_operador_elige_el_canal(app, salida_prueba, usuario):
    salida_id = salida_prueba()
    cliente = app.test_client()
    if usuario:
        iniciar_sesion(cliente, usuario)
    html, datos = _formulario_y_datos(cliente, salida_id, canal="whatsapp")
    assert 'name="canal"' not in html
    respuesta = cliente.post(f"/salidas/{salida_id}/reservar", data=datos)
    codigo = respuesta.headers["Location"].rsplit("/", 1)[1]
    assert respuesta.headers["Location"] == f"/reservas/{codigo}"        # como cualquier turista
    assert consultar_valor(app, "SELECT canal FROM reserva WHERE codigo = %s", (codigo,)) == "web"
    assert _creacion(app, codigo)[0] is None


def test_el_boton_vender_aparece_solo_si_la_salida_recibe_reservas(app):
    cliente = app.test_client()
    iniciar_sesion(cliente, "operador")
    assert 'href="/salidas/10/reservar"' in cliente.get("/panel/salidas/10/pasajeros").get_data(True)
    assert "/reservar" not in cliente.get("/panel/salidas/9/pasajeros").get_data(True)    # suspendida
    cliente = app.test_client()
    iniciar_sesion(cliente, "admin")
    assert "/reservar" not in cliente.get("/panel/salidas/10/pasajeros").get_data(True)   # el admin mira


def test_en_la_pagina_de_reservar_el_menu_marca_salidas(cliente):
    html = cliente.get("/salidas/10/reservar").get_data(True)
    assert 'href="/salidas" aria-current="page"' in html
    assert 'href="/mi-reserva" aria-current="page"' not in html
    assert 'href="/mi-reserva" aria-current="page"' in cliente.get("/mi-reserva").get_data(True)


def test_el_boton_de_zarpe_aparece_recien_60_minutos_antes(app, salida_cerca):
    cliente = app.test_client()
    iniciar_sesion(cliente, "operador")
    # Bien separadas en la misma lancha (400 y 20 min): si se pegaran, el NOW() de la segunda
    # podría ir un segundo después y la base las vería cruzadas.
    temprano = cliente.get(f"/panel/salidas/{salida_cerca(minutos=400)}/pasajeros").get_data(True)
    assert ">Marcar zarpe</button>" not in temprano and "El zarpe se podrá marcar desde el" in temprano
    listo = cliente.get(f"/panel/salidas/{salida_cerca(minutos=20)}/pasajeros").get_data(True)
    assert ">Marcar zarpe</button>" in listo and "se podrá marcar" not in listo


# --- Reservas sin pago a tiempo (RN-05) ---------------------------------------------------------

def test_la_reserva_sin_pago_a_tiempo_se_ve_vencida_y_la_tarea_la_marca(app, cliente, salida_prueba):
    codigo = reservar_en(app, salida_prueba(), metodo="yape")
    ejecutar_y_confirmar(app, "UPDATE reserva SET vence_en = NOW() - INTERVAL 1 MINUTE WHERE codigo = %s",
                         (codigo,))
    # Antes de que pase la tarea la base aún dice «pendiente», pero nadie ve una reserva viva.
    assert "Vencida" in cliente.get(f"/reservas/{codigo}").get_data(True)
    iniciar_sesion(cliente, "operador")
    html = cliente.get(f"/panel/reservas/{codigo}").get_data(True)
    assert "Vencida" in html and f'href="/panel/abordaje/{codigo}' not in html and "wa.me" not in html
    tareas.hacer(app, revisar_respaldo=False)
    assert consultar_valor(app, "SELECT estado FROM reserva WHERE codigo = %s", (codigo,)) == "vencida"
    detalle = consultar_valor(app, "SELECT b.detalle FROM bitacora b JOIN reserva r ON r.id = b.registro_id "
                                   "WHERE b.tabla_afectada = 'reserva' AND b.accion = 'cambio_estado' "
                                   "AND r.codigo = %s", (codigo,))
    assert json.loads(detalle) == {"de": "pendiente_pago", "a": "vencida", "origen": "automático (servidor)"}


# --- Mapas: el recorrido de la salida, dónde queda la comunidad y dónde rige la alerta ----------

def test_la_salida_muestra_su_recorrido_numerado(cliente):
    html = cliente.get("/salidas/10").get_data(True)
    assert 'aria-labelledby="mapa-salida-titulo"' in html and 'class="mapa__numero"' in html


def test_la_comunidad_tiene_un_halo_en_el_mapa(cliente):
    html = cliente.get("/comunidades/amantani").get_data(True)
    assert "Dónde queda" in html and html.count('r="17"') == 1 and 'class="mapa__numero"' not in html


def test_la_alerta_muestra_donde_rige(app):
    cliente = app.test_client()
    iniciar_sesion(cliente, "operador")
    de_amantani = cliente.get("/panel/alertas/1").get_data(True)          # alerta de una comunidad
    assert "Dónde rige" in de_amantani and de_amantani.count('r="17"') == 1
    de_todo_el_lago = cliente.get("/panel/alertas/2").get_data(True)      # alerta sin comunidad
    assert 'fill-opacity="0.22"' in de_todo_el_lago and 'r="17"' not in de_todo_el_lago


# --- Portada con foto, buscador y servicios (v2.3) ---------------------------------------------

def test_la_portada_tiene_foto_buscador_y_servicios(cliente):
    html = cliente.get("/").get_data(True)
    # La foto de la portada sale de la base (nombre y crédito), sin datos fijos en la plantilla
    assert re.search(r'<img src="/estaticos/img/comunidades/uros\.webp\?v=[^"]+" alt="Vista de Uros"', html)
    assert 'fetchpriority="high"' in html and "Entropy1963" in html
    # El buscador lleva a /salidas con el día y la ruta, con sus etiquetas
    assert '<form class="tarjeta buscador" method="get" action="/salidas"' in html
    assert '<label class="campo__etiqueta" for="buscar-fecha">' in html and 'name="fecha"' in html
    assert '<label class="campo__etiqueta" for="buscar-ruta">' in html and 'value="URO-TAQ"' in html
    assert html.count('class="servicio"') == 6 and html.count('class="servicio__icono"') == 6


def test_el_buscador_de_la_portada_lleva_a_las_salidas_del_dia(cliente):
    manana = (date.today() + timedelta(days=1)).isoformat()
    respuesta = cliente.get("/salidas", query_string={"fecha": manana, "ruta": ""})
    assert respuesta.status_code == 200 and f'value="{manana}"' in respuesta.get_data(True)


def test_la_portada_en_ingles(cliente):
    cliente.get("/idioma/en")
    html = cliente.get("/").get_data(True)
    assert "Find your trip" in html and "Travel with peace of mind" in html and "Search trips" in html


# --- Rutas como tarjetas (v2.4) ----------------------------------------------------------------

def test_las_rutas_de_la_portada_son_tarjetas_con_foto_recorrido_y_precio(app, cliente):
    html = cliente.get("/").get_data(True)
    activas = consultar_valor(app, "SELECT COUNT(*) AS n FROM ruta WHERE activa = 1")
    assert html.count('class="ruta-tarjeta"') == activas
    assert 'class="enlace-tarjeta" href="/salidas?ruta=URO-TAQ"' in html     # toda la tarjeta lleva
    assert "Uros → Taquile" in html and "por persona" in html                # recorrido y precio
    tarjetas = html[html.index('class="lista-limpia rutas-tarjetas"'):html.index('class="mapa"')]
    assert tarjetas.count("/estaticos/img/comunidades/") >= activas - 1      # casi todas con foto
    assert 'class="foto__credito"' in tarjetas                               # con su crédito


def test_las_tarjetas_de_rutas_no_agregan_consultas(cliente, monkeypatch):
    import pymysql

    contador = {"n": 0}
    original = pymysql.cursors.Cursor.execute

    def contar(self, consulta, args=None):
        if consulta.lstrip().upper().startswith("SELECT"):
            contador["n"] += 1
        return original(self, consulta, args)

    monkeypatch.setattr(pymysql.cursors.Cursor, "execute", contar)
    assert cliente.get("/").status_code == 200
    assert contador["n"] <= 6                       # las 5 de antes (paradas, una vez) + productos


# --- Galería (v2.5) -----------------------------------------------------------------------------

def test_la_galeria_muestra_las_fotos_con_su_credito_y_el_visor(cliente):
    from tests.test_accesibilidad import problemas

    html = cliente.get("/galeria").get_data(True)
    assert html.count('class="galeria__item"') == 6 and html.count('class="galeria__credito"') == 6
    for slug in ("uros", "taquile", "amantani"):
        assert f'href="/comunidades/{slug}"' in html and f'/img/comunidades/{slug}.webp' in html
    assert '<dialog id="visor" class="visor" aria-labelledby="visor-titulo">' in html
    assert re.search(r'<script src="/estaticos/js/galeria\.js\?v=[^"]+" defer>', html)
    assert 'aria-current="page">Galería</a>' in html                       # el menú la marca
    assert problemas(html) == []


def test_la_galeria_se_filtra_por_idioma_y_lo_raro_se_ignora(app, cliente):
    aimara = consultar_valor(app, "SELECT COUNT(*) AS n FROM comunidad "
                                  "WHERE activa = 1 AND idioma_originario = 'aimara'")
    html = cliente.get("/galeria?idioma=aimara").get_data(True)
    assert html.count('class="galeria__item"') == aimara and 'aria-current="true">Aimara (' in html
    raro = cliente.get("/galeria", query_string={"idioma": "<script>"}).get_data(True)
    assert raro.count('class="galeria__item"') == 6 and "<script>alert" not in raro


def test_la_galeria_en_ingles_y_la_portada_la_enlaza(cliente):
    assert 'href="/galeria"' in cliente.get("/").get_data(True)
    cliente.get("/idioma/en")
    html = cliente.get("/galeria").get_data(True)
    assert "Lake gallery" in html and ">Gallery</a>" in html and "Next" in html

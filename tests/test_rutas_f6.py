"""F6 por las rutas: permisos de las páginas nuevas, alertas, reprogramar, devolución, reseña,
indicadores y el turista en inglés (8.9)."""

import datetime as dt
import re
from pathlib import Path

import pytest

from app.servicios.textos_en import EN
from tests.conftest import (
    consultar_valor,
    ejecutar_y_confirmar,
    iniciar_sesion,
    reservar_en,
    token_csrf,
)

PLANTILLAS = Path(__file__).resolve().parent.parent / "app" / "plantillas"
USUARIOS = ["admin", "operador", "guia.elena", "capitan.teodoro"]
MATRIZ_F6 = [
    ("/panel/alertas", (200, 200, 403, 403)),
    ("/panel/alertas/nueva", (403, 200, 403, 403)),
    ("/panel/alertas/1", (200, 200, 403, 403)),
    ("/panel/hospedajes", (200, 200, 403, 403)),
    ("/panel/hospedajes/transparencia", (200, 200, 403, 403)),
    ("/panel/resenas", (200, 200, 403, 403)),
    ("/panel/indicadores", (200, 200, 403, 403)),
]


@pytest.mark.parametrize("url, codigos", MATRIZ_F6, ids=[m[0] for m in MATRIZ_F6])
def test_matriz_de_permisos_f6(app, url, codigos):
    for usuario, codigo in zip(USUARIOS, codigos, strict=True):
        cliente = app.test_client()
        iniciar_sesion(cliente, usuario)
        respuesta = cliente.get(url)
        assert respuesta.status_code == codigo, f"{usuario} en {url}"


def test_menu_del_operador_con_las_paginas_f6(cliente):
    iniciar_sesion(cliente, "operador")
    html = cliente.get("/panel").get_data(True)
    for enlace in ("/panel/alertas", "/panel/hospedajes", "/panel/resenas", "/panel/indicadores"):
        assert f'href="{enlace}"' in html


# --- Alertas ----------------------------------------------------------------------------------------

def test_registrar_alerta_y_suspender_por_formulario(app, cliente, salida_prueba):
    salida_id = salida_prueba(ruta_id=1, dias=33)
    hoy = consultar_valor(app, "SELECT CURDATE()")
    desde = dt.datetime.combine(hoy + dt.timedelta(days=33), dt.time(0, 0))
    iniciar_sesion(cliente, "operador")
    csrf = token_csrf(cliente.get("/panel/alertas/nueva"))
    datos = {"csrf_token": csrf, "titulo": "Tormenta de prueba", "tipo": "tormenta", "nivel": "rojo",
             "fuente": "Capitania", "comunidad_id": "0", "descripcion": "",
             "vigente_desde": desde.strftime("%Y-%m-%dT%H:%M"),
             "vigente_hasta": (desde - dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")}
    malo = cliente.post("/panel/alertas/nueva", data=datos)
    assert malo.status_code == 422 and "Tiene que terminar después de empezar." in malo.get_data(True)
    datos["vigente_hasta"] = (desde + dt.timedelta(hours=20)).strftime("%Y-%m-%dT%H:%M")
    bueno = cliente.post("/panel/alertas/nueva", data=datos)
    assert bueno.status_code == 303
    alerta_id = int(bueno.headers["Location"].rsplit("/", 1)[1])
    try:
        pagina = cliente.get(bueno.headers["Location"]).get_data(True)
        assert "en un solo paso" in pagina                      # botón para suspender
        suspendida = cliente.post(f"/panel/alertas/{alerta_id}/suspender", data={"csrf_token": csrf})
        assert suspendida.status_code == 303
        assert consultar_valor(app, "SELECT estado FROM salida WHERE id = %s", (salida_id,)) == "suspendida"
        otra_vez = cliente.post(f"/panel/alertas/{alerta_id}/suspender", data={"csrf_token": csrf})
        assert otra_vez.status_code == 422 and "No hay salidas por suspender" in otra_vez.get_data(True)
    finally:
        ejecutar_y_confirmar(app, "DELETE FROM alerta_lago WHERE id = %s", (alerta_id,))


# --- El turista: reprogramar, devolución y reseña ------------------------------------------------

def dar_acceso(cliente, codigo):
    """Pasa por "Mi reserva" con el documento del titular (7997xxxx de reservar_en)."""
    documento = consultar_valor(cliente.application, "SELECT t.numero_documento FROM reserva r "
                                                     "JOIN turista t ON t.id = r.turista_id WHERE r.codigo = %s",
                                (codigo,))
    csrf = token_csrf(cliente.get("/mi-reserva"))
    respuesta = cliente.post("/mi-reserva", data={"csrf_token": csrf, "codigo": codigo,
                                                  "numero_documento": documento})
    assert respuesta.status_code == 303


def test_reprogramar_por_formulario(app, cliente, salida_prueba):
    vieja, nueva = salida_prueba(ruta_id=1, dias=20), salida_prueba(ruta_id=1, dias=21)
    codigo = reservar_en(app, vieja)
    assert cliente.get(f"/reservas/{codigo}/reprogramar").status_code == 302      # sin acceso
    dar_acceso(cliente, codigo)
    assert cliente.get(f"/reservas/{codigo}/reprogramar").status_code == 302      # no está suspendida
    ejecutar_y_confirmar(app, "UPDATE salida SET estado = 'suspendida', motivo_estado = 'Oleaje' "
                              "WHERE id = %s", (vieja,))
    ver = cliente.get(f"/reservas/{codigo}").get_data(True)
    assert f'href="/reservas/{codigo}/reprogramar"' in ver
    pagina = cliente.get(f"/reservas/{codigo}/reprogramar")
    assert pagina.status_code == 200 and f'value="{nueva}"' in pagina.get_data(True)
    csrf = token_csrf(pagina)
    vacio = cliente.post(f"/reservas/{codigo}/reprogramar", data={"csrf_token": csrf})
    assert vacio.status_code == 422
    hecho = cliente.post(f"/reservas/{codigo}/reprogramar", data={"csrf_token": csrf, "salida_id": nueva})
    assert hecho.status_code == 303
    assert consultar_valor(app, "SELECT salida_id FROM reserva WHERE codigo = %s", (codigo,)) == nueva


def test_devolucion_por_formulario(app, cliente, salida_prueba):
    salida_id = salida_prueba(ruta_id=1, dias=20)
    codigo = reservar_en(app, salida_id)
    ejecutar_y_confirmar(app, "UPDATE salida SET estado = 'suspendida', motivo_estado = 'Helada' "
                              "WHERE id = %s", (salida_id,))
    dar_acceso(cliente, codigo)
    csrf = token_csrf(cliente.get(f"/reservas/{codigo}/reprogramar"))
    respuesta = cliente.post(f"/reservas/{codigo}/devolucion", data={"csrf_token": csrf})
    assert respuesta.status_code == 303
    assert "quedó cancelada" in cliente.get(respuesta.headers["Location"]).get_data(True)
    assert consultar_valor(app, "SELECT estado FROM reserva WHERE codigo = %s", (codigo,)) == "cancelada"
    operador = app.test_client()
    iniciar_sesion(operador, "operador")
    assert codigo in operador.get("/panel/pagos").get_data(True)                   # por atender


def test_resena_por_formulario(app, cliente, salida_prueba):
    salida_id = salida_prueba(ruta_id=1, dias=20)
    codigo = reservar_en(app, salida_id)
    ejecutar_y_confirmar(app, "UPDATE reserva SET estado = 'abordada' WHERE codigo = %s", (codigo,))
    ejecutar_y_confirmar(app, "UPDATE salida SET fecha_hora_zarpe = NOW() - INTERVAL 2 DAY, "
                              "fecha_hora_retorno = NOW() - INTERVAL 44 HOUR WHERE id = %s", (salida_id,))
    dar_acceso(cliente, codigo)
    assert f'href="/reservas/{codigo}/resena"' in cliente.get(f"/reservas/{codigo}").get_data(True)
    pagina = cliente.get(f"/reservas/{codigo}/resena")
    csrf = token_csrf(pagina)
    assert cliente.post(f"/reservas/{codigo}/resena", data={"csrf_token": csrf}).status_code == 422
    hecho = cliente.post(f"/reservas/{codigo}/resena", data={"csrf_token": csrf, "puntuacion": "4",
                                                             "comentario": "Muy lindo, volveremos."})
    assert hecho.status_code == 303
    assert "Ya dejaste tu opinión" in cliente.get(f"/reservas/{codigo}/resena").get_data(True)
    ejecutar_y_confirmar(app, "DELETE FROM resena WHERE reserva_id = (SELECT id FROM reserva WHERE codigo = %s)",
                         (codigo,))


def test_las_resenas_publicadas_se_ven_en_la_salida(cliente):
    html = cliente.get("/salidas/10").get_data(True)                   # ruta 2: 2 publicadas en la semilla
    assert "Opiniones de quienes hicieron esta ruta" in html
    assert "Taquile es precioso" in html
    assert "Turista de" in html and "Milagros" not in html             # sin nombres


# --- Indicadores y transparencia ---------------------------------------------------------------

def test_indicadores_y_periodo_en_lista_blanca(cliente):
    iniciar_sesion(cliente, "admin")
    html = cliente.get("/panel/indicadores?dias=365").get_data(True)
    assert "Ocupación por ruta" in html and '<svg class="barra"' in html
    assert 'style="' not in html                                       # CSP: sin estilos en línea
    assert cliente.get("/panel/indicadores?dias=DROP").status_code == 200   # vuelve a 30 días


def test_transparencia_imprimible(cliente):
    iniciar_sesion(cliente, "operador")
    html = cliente.get("/panel/hospedajes/transparencia?mes=9999-99").get_data(True)
    assert "Reporte de transparencia comunitaria" in html and "Amantaní" in html


# --- Inglés (8.9) ----------------------------------------------------------------------------------

def test_cambiar_a_ingles_y_volver(cliente):
    respuesta = cliente.get("/idioma/en?volver=/salidas")
    assert respuesta.status_code == 302 and respuesta.headers["Location"] == "/salidas"
    html = cliente.get("/salidas").get_data(True)
    assert '<html lang="en">' in html and "<h1>Departures</h1>" in html
    assert re.search(r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), "
                     r"(January|February|March|April|May|June|July|August|September|October|November|December)", html)
    assert 'hreflang="es">Español</a>' in html
    cliente.get("/idioma/es")
    assert "<h1>Salidas</h1>" in cliente.get("/salidas").get_data(True)


def test_el_idioma_solo_vuelve_a_paginas_internas(cliente):
    assert cliente.get("/idioma/en?volver=https://otro.example").headers["Location"] == "/"
    assert cliente.get("/idioma/fr").status_code == 404


def test_el_panel_queda_en_espanol(cliente):
    cliente.get("/idioma/en")
    iniciar_sesion(cliente, "operador")
    html = cliente.get("/panel").get_data(True)
    assert '<html lang="es">' in html and "Resumen del día" in html


def test_formulario_y_errores_del_modelo_en_ingles(cliente, salida_prueba):
    salida_id = salida_prueba(ruta_id=1, dias=20)
    cliente.get("/idioma/en")
    pagina = cliente.get(f"/salidas/{salida_id}/reservar")
    html = pagina.get_data(True)
    assert ">First names</label>" in html and "Confirm booking" in html
    token = re.search(r'name="token_envio" type="hidden" value="([0-9a-f]{32})"', html).group(1)
    respuesta = cliente.post(f"/salidas/{salida_id}/reservar", data={
        "csrf_token": token_csrf(pagina), "token_envio": token, "titular_nombres": "Ana",
        "titular_apellidos": "Prueba Inglés", "titular_tipo_documento": "DNI",
        "titular_numero_documento": "123", "titular_nacionalidad": "PE", "telefono": "987654321",
        "titular_viaja": "y", "titular_tipo_pasajero_id": "1", "metodo_pago": "muelle"})
    assert respuesta.status_code == 422
    assert "A DNI has 8 digits." in respuesta.get_data(True)          # mensaje del modelo traducido


def test_pagina_de_error_en_ingles(cliente):
    cliente.get("/idioma/en")
    respuesta = cliente.get("/no-existe")
    assert respuesta.status_code == 404 and "Page not found" in respuesta.get_data(True)


def test_cada_texto_del_turista_tiene_su_traduccion():
    """Todo t('…') de las plantillas del turista tiene su versión en inglés en textos_en.py."""
    faltan = []
    carpetas = [PLANTILLAS, PLANTILLAS / "publico", PLANTILLAS / "reservas", PLANTILLAS / "errores"]
    for carpeta in carpetas:
        for archivo in carpeta.glob("*.html"):
            texto = archivo.read_text(encoding="utf-8")
            for m in re.finditer(r"""\bt\(\s*'((?:[^'\\]|\\.)*)'""", texto):
                if m.group(1).replace("\\'", "'") not in EN:
                    faltan.append((archivo.name, m.group(1)))
    assert faltan == []

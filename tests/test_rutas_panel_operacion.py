"""Rutas del panel operativo (F5): permisos por rol, CSRF, POST → 303 → GET, 422 y formatos."""

import re
from pathlib import Path
from urllib.parse import quote

import pytest

from tests.conftest import (
    consultar_valor,
    ejecutar_y_confirmar,
    iniciar_sesion,
    limpiar_salida,
    reservar_en,
    token_csrf,
)

RUTAS = Path(__file__).resolve().parent.parent / "app" / "rutas"

# --- Matriz de permisos (docs/matriz-permisos.md) ----------------------------------------------

MATRIZ = [
    # (url, admin, operador, guía Elena, capitán Teodoro)
    ("/panel/salidas", (200, 200, 403, 403)),
    ("/panel/salidas/nueva", (403, 200, 403, 403)),
    ("/panel/salidas/10/editar", (403, 200, 403, 403)),
    ("/panel/salidas/10/suspender", (403, 200, 403, 403)),
    ("/panel/salidas/10/pasajeros", (200, 200, 403, 200)),         # 10: capitán Teodoro, guía Marco
    ("/panel/salidas/12/pasajeros", (200, 200, 200, 403)),         # 12: capitán Fermín, guía Elena
    ("/panel/salidas/10/pasajeros?formato=pdf", (200, 200, 403, 200)),
    ("/panel/abordaje", (403, 200, 200, 200)),
    ("/panel/abordaje/TV-33VR", (403, 200, 200, 403)),             # reserva de la salida 12
    ("/panel/pagos", (200, 200, 403, 403)),
    ("/panel/reservas", (200, 200, 403, 403)),                     # buscar y ver (F10)
    ("/panel/reservas/TV-33VR", (200, 200, 403, 403)),
    ("/panel/catalogos", (200, 200, 403, 403)),
    ("/panel/catalogos/familias/1", (200, 200, 403, 403)),
    ("/panel/usuarios", (200, 403, 403, 403)),
    ("/panel/usuarios/nuevo", (200, 403, 403, 403)),
    ("/panel/bitacora/exportar", (200, 403, 403, 403)),            # D-115
    ("/panel/mi-cuenta", (200, 200, 200, 200)),                    # D-113: cada uno, la suya
    ("/panel/respaldos", (200, 403, 403, 403)),                    # D-116: solo el admin
]
USUARIOS = ["admin", "operador", "guia.elena", "capitan.teodoro"]


@pytest.mark.parametrize("url, codigos", MATRIZ, ids=[m[0] for m in MATRIZ])
def test_matriz_de_permisos(app, url, codigos):
    for usuario, codigo in zip(USUARIOS, codigos, strict=True):
        cliente = app.test_client()                     # una sesión nueva por usuario
        iniciar_sesion(cliente, usuario)
        respuesta = cliente.get(url)
        assert respuesta.status_code == codigo, f"{usuario} en {url}"
        if codigo == 200:
            assert respuesta.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("url", ["/panel/salidas", "/panel/pagos", "/panel/catalogos/rutas",
                                 "/panel/abordaje/TV-WWUQ"])
def test_sin_sesion_va_a_entrar_y_vuelve(cliente, url):
    respuesta = cliente.get(url)
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/entrar?next=" + quote(url, safe="")


def test_el_menu_muestra_solo_lo_de_cada_rol(app, cliente):
    iniciar_sesion(cliente, "operador")
    html = cliente.get("/panel").get_data(True)
    for enlace in ("/panel/salidas", "/panel/abordaje", "/panel/pagos", "/panel/catalogos"):
        assert f'href="{enlace}"' in html
    assert 'href="/panel/usuarios"' not in html
    cliente = app.test_client()
    iniciar_sesion(cliente, "guia.elena")
    html = cliente.get("/panel").get_data(True)
    assert 'href="/panel/abordaje"' in html and 'href="/panel/pagos"' not in html


def test_ninguna_ruta_tiene_sql():
    """Arquitectura en capas (sección 11): el SQL vive en app/modelos, nunca en app/rutas."""
    sql = re.compile(r"\b(SELECT|INSERT INTO|UPDATE \w+ SET|DELETE FROM)\b")
    encontrados = [archivo.name for archivo in RUTAS.glob("*.py") if sql.search(archivo.read_text("utf-8"))]
    assert encontrados == []


# --- Salidas ----------------------------------------------------------------------------------------

def datos_salida(csrf, fecha, hora="08:00", lancha="3", cupo="10"):
    return {"csrf_token": csrf, "ruta_id": "1", "embarcacion_id": lancha, "capitan_id": "5",
            "guia_id": "0", "fecha": fecha, "hora": hora, "cupo": cupo}


def test_crear_salida_por_formulario(app, cliente):
    iniciar_sesion(cliente, "operador")
    csrf = token_csrf(cliente.get("/panel/salidas/nueva"))
    fecha = consultar_valor(app, "SELECT CURDATE() + INTERVAL 45 DAY").isoformat()
    malo = cliente.post("/panel/salidas/nueva", data=datos_salida(csrf, fecha, lancha="4"))
    assert malo.status_code == 422
    assert "La lancha está en mantenimiento" in malo.get_data(True)
    bueno = cliente.post("/panel/salidas/nueva", data=datos_salida(csrf, fecha))
    assert bueno.status_code == 303
    salida_id = int(re.search(r"/panel/salidas/(\d+)/pasajeros", bueno.headers["Location"]).group(1))
    try:
        pagina = cliente.get(bueno.headers["Location"]).get_data(True)
        assert "la salida quedó programada" in pagina
        csrf = token_csrf(cliente.get(f"/panel/salidas/{salida_id}/suspender"))
        vacio = cliente.post(f"/panel/salidas/{salida_id}/suspender",
                             data={"csrf_token": csrf, "motivo": ""})
        assert vacio.status_code == 422
        hecho = cliente.post(f"/panel/salidas/{salida_id}/suspender",
                             data={"csrf_token": csrf, "motivo": "Viento fuerte en la bahía"})
        assert hecho.status_code == 303
        assert consultar_valor(app, "SELECT estado FROM salida WHERE id = %s",
                               (salida_id,)) == "suspendida"
    finally:
        limpiar_salida(app, salida_id)


def test_post_sin_csrf_da_400(cliente):
    iniciar_sesion(cliente, "operador")
    assert cliente.post("/panel/salidas/10/suspender", data={"motivo": "Sin token"}).status_code == 400
    assert cliente.post("/panel/pagos/1/verificar").status_code == 400


def test_el_admin_mira_pero_no_actua(cliente):
    iniciar_sesion(cliente, "admin")
    csrf = token_csrf(cliente.get("/panel/salidas"))     # el token sale del botón "Salir"
    assert cliente.post("/panel/salidas/10/zarpe", data={"csrf_token": csrf}).status_code == 403
    pago_id = 1
    assert cliente.post(f"/panel/pagos/{pago_id}/verificar",
                        data={"csrf_token": csrf}).status_code == 403
    html = cliente.get("/panel/pagos").get_data(True)
    assert "Pagos por verificar" in html and ">Verificar</button>" not in html


def test_zarpe_por_el_capitan(app, cliente, salida_cerca):
    temprano, listo = salida_cerca(minutos=200), None
    iniciar_sesion(cliente, "capitan.teodoro")
    csrf = token_csrf(cliente.get(f"/panel/salidas/{temprano}/pasajeros"))
    respuesta = cliente.post(f"/panel/salidas/{temprano}/zarpe", data={"csrf_token": csrf})
    assert respuesta.status_code == 422 and "60 minutos" in respuesta.get_data(True)
    limpiar_salida(app, temprano)
    listo = salida_cerca(minutos=20)
    respuesta = cliente.post(f"/panel/salidas/{listo}/zarpe", data={"csrf_token": csrf})
    assert respuesta.status_code == 303
    assert "Zarpe registrado" in cliente.get(respuesta.headers["Location"]).get_data(True)


# --- Pasajeros: manifiesto, WhatsApp e impresión ---------------------------------------------------

def test_manifiesto_pdf(cliente):
    iniciar_sesion(cliente, "operador")
    respuesta = cliente.get("/panel/salidas/8/pasajeros?formato=pdf")
    assert respuesta.status_code == 200
    assert respuesta.mimetype == "application/pdf"
    assert respuesta.data.startswith(b"%PDF")
    assert 'filename="manifiesto-salida-8.pdf"' in respuesta.headers["Content-Disposition"]


def test_lista_para_whatsapp_sin_documentos(cliente):
    iniciar_sesion(cliente, "operador")
    html = cliente.get("/panel/salidas/8/pasajeros?formato=whatsapp").get_data(True)
    assert 'href="https://wa.me/?text=' in html
    texto = re.search(r'<textarea[^>]*>(.*?)</textarea>', html, re.S).group(1)
    assert "Islas flotantes de los Uros" in texto and "TV-WWUQ" in texto
    assert "47219034" not in texto and "900000210" not in texto       # ni documento ni teléfono


def test_lista_imprimible_y_lista_html(cliente):
    iniciar_sesion(cliente, "guia.elena")
    imprimir = cliente.get("/panel/salidas/12/pasajeros?formato=imprimir").get_data(True)
    assert "☐" in imprimir and "Luis Alberto" in imprimir
    html = cliente.get("/panel/salidas/12/pasajeros").get_data(True)
    assert "TV-33VR" in html and "Marcar zarpe" not in html            # la guía no marca el zarpe


# --- Abordaje -------------------------------------------------------------------------------------

def test_buscar_reserva_para_abordar(cliente):
    iniciar_sesion(cliente, "operador")
    respuesta = cliente.get("/panel/abordaje?codigo=tv-wwuq")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"] == "/panel/abordaje/TV-WWUQ?via=manual"
    assert cliente.get("/panel/abordaje?codigo=XX").status_code == 422
    assert cliente.get("/panel/abordaje/TV-0000").status_code == 404        # formato inválido
    assert cliente.get("/panel/abordaje/TV-ZZZZ").status_code == 404        # no existe


def test_abordaje_por_formulario(app, cliente, salida_cerca):
    codigo = reservar_en(app, salida_cerca(minutos=30), acompanantes=1)
    iniciar_sesion(cliente, "capitan.teodoro")
    pagina = cliente.get(f"/panel/abordaje/{codigo}")
    html = pagina.get_data(True)
    ids = re.findall(r'name="pasajero" value="(\d+)"', html)
    assert len(ids) == 2 and 'name="metodo" type="hidden" value="qr"' in html
    respuesta = cliente.post(f"/panel/abordaje/{codigo}",
                             data={"csrf_token": token_csrf(pagina), "metodo": "qr", "pasajero": ids})
    assert respuesta.status_code == 303
    assert "la reserva quedó «abordada»" in cliente.get(respuesta.headers["Location"]).get_data(True)
    otra_vez = cliente.post(f"/panel/abordaje/{codigo}",
                            data={"csrf_token": token_csrf(pagina), "metodo": "qr", "pasajero": ids})
    assert otra_vez.status_code == 422


def test_cobro_en_el_muelle_por_formulario(app, cliente, salida_cerca):
    codigo = reservar_en(app, salida_cerca(minutos=30))
    iniciar_sesion(cliente, "operador")
    pagina = cliente.get(f"/panel/abordaje/{codigo}?via=manual")
    assert "Falta pagar" in pagina.get_data(True)
    csrf = token_csrf(pagina)
    malo = cliente.post(f"/panel/abordaje/{codigo}/cobro",
                        data={"csrf_token": csrf, "metodo": "efectivo_muelle", "monto": "9999"})
    assert malo.status_code == 422 and "Falta pagar" in malo.get_data(True)
    total = consultar_valor(app, "SELECT total FROM reserva WHERE codigo = %s", (codigo,))
    bueno = cliente.post(f"/panel/abordaje/{codigo}/cobro",
                         data={"csrf_token": csrf, "metodo": "efectivo_muelle", "monto": str(total)})
    assert bueno.status_code == 303
    assert consultar_valor(app, "SELECT estado FROM reserva WHERE codigo = %s", (codigo,)) == "pagada"


def test_el_cobro_no_hace_que_un_abordaje_manual_quede_como_qr(app, cliente, salida_cerca):
    """Revisión del 29/10: después de cobrar en el muelle, el abordaje se registraba como «qr»
    aunque el operador había escrito el código. Ahora la página del cobro conserva «via=manual»."""
    codigo = reservar_en(app, salida_cerca(minutos=30))
    iniciar_sesion(cliente, "operador")
    pagina = cliente.get(f"/panel/abordaje/{codigo}?via=manual")
    assert f'action="/panel/abordaje/{codigo}/cobro?via=manual"' in pagina.get_data(True)
    total = consultar_valor(app, "SELECT total FROM reserva WHERE codigo = %s", (codigo,))
    cobro = cliente.post(f"/panel/abordaje/{codigo}/cobro?via=manual",
                         data={"csrf_token": token_csrf(pagina), "metodo": "efectivo_muelle",
                               "monto": str(total)})
    assert cobro.headers["Location"] == f"/panel/abordaje/{codigo}?via=manual"
    despues = cliente.get(cobro.headers["Location"]).get_data(True)
    assert 'name="metodo" type="hidden" value="manual"' in despues


# --- Pagos ----------------------------------------------------------------------------------------

def test_verificar_y_rechazar_por_formulario(app, cliente, salida_prueba):
    from app.modelos import reserva

    salida_id = salida_prueba()
    codigos = [reservar_en(app, salida_id, metodo="yape") for _ in range(2)]
    with app.app_context():
        for numero, codigo in enumerate(codigos):
            total = consultar_valor(app, "SELECT total FROM reserva WHERE codigo = %s", (codigo,))
            reserva.reportar_pago(codigo, "plin", total, f"PLIN-RUTA-{numero}-{codigo[3:]}")
    pagos = [consultar_valor(app, "SELECT p.id FROM pago p JOIN reserva r ON r.id = p.reserva_id "
                                  "WHERE r.codigo = %s", (c,)) for c in codigos]
    iniciar_sesion(cliente, "operador")
    pagina = cliente.get("/panel/pagos")
    assert f'id="pago-{pagos[0]}"' in pagina.get_data(True)
    csrf = token_csrf(pagina)
    verificado = cliente.post(f"/panel/pagos/{pagos[0]}/verificar", data={"csrf_token": csrf})
    assert verificado.status_code == 303
    assert "quedó PAGADA" in cliente.get("/panel/pagos").get_data(True)
    sin_motivo = cliente.post(f"/panel/pagos/{pagos[1]}/rechazar",
                              data={"csrf_token": csrf, "observacion": ""})
    assert sin_motivo.status_code == 422 and "por qué se rechaza" in sin_motivo.get_data(True)
    rechazado = cliente.post(f"/panel/pagos/{pagos[1]}/rechazar",
                             data={"csrf_token": csrf, "observacion": "Monto distinto en Plin"})
    assert rechazado.status_code == 303
    assert consultar_valor(app, "SELECT estado FROM pago WHERE id = %s", (pagos[1],)) == "rechazado"


# --- Catálogos y usuarios --------------------------------------------------------------------------

def test_catalogo_por_formulario(app, cliente):
    iniciar_sesion(cliente, "admin")
    pagina = cliente.get("/panel/catalogos/embarcaciones/nuevo")
    csrf = token_csrf(pagina)
    datos = {"csrf_token": csrf, "nombre": "Lancha Ruta Prueba", "matricula": "PUN-RT-0009",
             "capacidad_maxima": "50", "tipo": "lancha", "estado": "operativa"}
    malo = cliente.post("/panel/catalogos/embarcaciones/nuevo", data=datos)
    assert malo.status_code == 422 and "Va de 1 a 40." in malo.get_data(True)
    bueno = cliente.post("/panel/catalogos/embarcaciones/nuevo",
                         data={**datos, "capacidad_maxima": "12"})
    try:
        assert bueno.status_code == 303
        assert "Lancha Ruta Prueba" in cliente.get(bueno.headers["Location"]).get_data(True)
    finally:
        ejecutar_y_confirmar(app, "DELETE FROM embarcacion WHERE matricula = 'PUN-RT-0009'")
    assert cliente.get("/panel/catalogos/no-existe").status_code == 404
    assert cliente.get("/panel/catalogos/tipos-pasajero/nuevo").status_code == 404
    assert cliente.get("/panel/catalogos/rutas/999").status_code == 404


def test_paradas_por_formulario(app, cliente):
    iniciar_sesion(cliente, "operador")
    pagina = cliente.get("/panel/catalogos/rutas/1/paradas")
    assert pagina.status_code == 200 and "Uros" in pagina.get_data(True)
    csrf = token_csrf(pagina)
    agregada = cliente.post("/panel/catalogos/rutas/1/paradas", data={
        "csrf_token": csrf, "comunidad_id": "6", "orden": "2", "minutos_estadia": "30"})
    assert agregada.status_code == 303
    parada_id = consultar_valor(app, "SELECT id FROM ruta_parada WHERE ruta_id = 1 AND comunidad_id = 6")
    noche = cliente.post(f"/panel/catalogos/rutas/1/paradas/{parada_id}", data={
        "csrf_token": csrf, "comunidad_id": "6", "orden": "2", "minutos_estadia": "30",
        "es_pernocte": "y"})
    assert noche.status_code == 422 and "no incluye noche" in noche.get_data(True)
    quitada = cliente.post(f"/panel/catalogos/rutas/1/paradas/{parada_id}/borrar",
                           data={"csrf_token": csrf})
    assert quitada.status_code == 303
    assert consultar_valor(app, "SELECT COUNT(*) FROM ruta_parada WHERE ruta_id = 1") == 1


def test_usuario_nuevo_por_formulario_y_entra(app, cliente):
    iniciar_sesion(cliente, "admin")
    csrf = token_csrf(cliente.get("/panel/usuarios/nuevo"))
    datos = {"csrf_token": csrf, "nombre_usuario": "capitan.prueba", "nombre_completo": "Néstor Prueba",
             "rol_id": "4", "comunidad_id": "0", "licencia_navegacion": "", "contrasena": "Clave-larga-26",
             "activo": "y"}
    malo = cliente.post("/panel/usuarios/nuevo", data=datos)
    assert malo.status_code == 422 and "Escribe la licencia de navegación." in malo.get_data(True)
    bueno = cliente.post("/panel/usuarios/nuevo", data={**datos, "licencia_navegacion": "LIC-PRUEBA-1"})
    try:
        assert bueno.status_code == 303
        nuevo = app.test_client()
        assert iniciar_sesion(nuevo, "capitan.prueba", "Clave-larga-26").status_code == 302
        assert nuevo.get("/panel").status_code == 200
    finally:
        ejecutar_y_confirmar(app, "DELETE FROM bitacora WHERE usuario_id = "
                                  "(SELECT id FROM usuario WHERE nombre_usuario = 'capitan.prueba')")
        ejecutar_y_confirmar(app, "DELETE FROM usuario WHERE nombre_usuario = 'capitan.prueba'")

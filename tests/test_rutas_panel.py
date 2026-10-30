"""Panel: permisos de cada rol en la ruta (@requiere_rol) y otra vez en el modelo."""

import pytest

from app.modelos import PermisoDenegado
from app.modelos import bitacora as modelo_bitacora
from app.modelos import panel as modelo_panel
from app.modelos import usuario as modelo_usuario
from tests.conftest import iniciar_sesion

ROLES = ["admin", "operador", "guia.elena", "capitan.teodoro"]


def test_sin_sesion_el_panel_redirige_a_entrar(cliente):
    respuesta = cliente.get("/panel")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].startswith("/entrar?next=")


@pytest.mark.parametrize("usuario", ROLES)
def test_cada_rol_ve_su_resumen(cliente, usuario):
    iniciar_sesion(cliente, usuario)
    respuesta = cliente.get("/panel")
    assert respuesta.status_code == 200
    assert respuesta.headers["Cache-Control"] == "no-store"
    assert "Resumen del día" in respuesta.get_data(True)


def test_el_operador_ve_pendientes_y_salidas_de_hoy(cliente):
    iniciar_sesion(cliente, "operador")
    html = cliente.get("/panel").get_data(True)
    assert "Pagos por verificar" in html
    assert "Salidas de hoy" in html
    assert "Oleaje fuerte en el sector de Amantaní" in html        # alerta vigente de la semilla


def test_el_capitan_ve_solo_sus_salidas(cliente):
    iniciar_sesion(cliente, "capitan.teodoro")
    html = cliente.get("/panel").get_data(True)
    assert "Mis salidas" in html
    assert "Pagos por verificar" not in html
    assert "Uros y Luquina Chico" in html                         # salida 13: es suya
    assert "Uros, Amantaní y Taquile" not in html                 # salidas 9 y 12: son de Fermín


def test_la_guia_ve_solo_las_salidas_que_tiene_asignadas(cliente):
    iniciar_sesion(cliente, "guia.elena")
    html = cliente.get("/panel").get_data(True)
    assert "Mis salidas" in html
    assert "Uros, Amantaní y Taquile" in html                     # salidas 9 y 12
    assert "Uros y Luquina Chico" not in html                     # salida 13: sin guía


@pytest.mark.parametrize("usuario, codigo", [
    ("admin", 200), ("operador", 403), ("guia.elena", 403), ("capitan.teodoro", 403),
])
def test_bitacora_solo_para_admin(cliente, usuario, codigo):
    iniciar_sesion(cliente, usuario)
    respuesta = cliente.get("/panel/bitacora")
    assert respuesta.status_code == codigo
    if codigo == 403:
        assert "No tienes permiso" in respuesta.get_data(True)


def test_bitacora_muestra_inicios_de_sesion_y_filtra(cliente):
    iniciar_sesion(cliente, "admin")
    html = cliente.get("/panel/bitacora?accion=inicio_sesion").get_data(True)
    assert "<code>inicio_sesion</code>" in html
    assert "<code>cambio_estado</code>" not in html
    # Un filtro que no existe se ignora (lista blanca) y una página fuera de rango da 404.
    assert cliente.get("/panel/bitacora?accion=DROP%20TABLE").status_code == 200
    assert cliente.get("/panel/bitacora?pagina=999").status_code == 404
    assert cliente.get("/panel/bitacora?pagina=0").status_code == 404


def test_solo_el_admin_ve_el_enlace_a_la_bitacora(cliente):
    iniciar_sesion(cliente, "operador")
    assert 'href="/panel/bitacora"' not in cliente.get("/panel").get_data(True)


# --- Segunda verificación: en el modelo -------------------------------------

def test_el_modelo_tambien_niega_la_bitacora_al_operador(app):
    with app.test_request_context():
        operador = modelo_usuario.buscar_por_id(2)
        with pytest.raises(PermisoDenegado):
            modelo_bitacora.listar(operador)
        administrador = modelo_usuario.buscar_por_id(1)
        filas, total = modelo_bitacora.listar(administrador)
        assert total >= len(filas) > 0


def test_el_modelo_niega_el_resumen_sin_sesion(app):
    with app.test_request_context():
        with pytest.raises(PermisoDenegado):
            modelo_panel.resumen(None)


def test_un_usuario_desactivado_pierde_la_sesion(app, cliente):
    from tests.conftest import ejecutar_y_confirmar

    iniciar_sesion(cliente, "capitan.fermin")
    assert cliente.get("/panel").status_code == 200
    ejecutar_y_confirmar(app, "UPDATE usuario SET activo = 0 WHERE nombre_usuario = 'capitan.fermin'")
    try:
        assert cliente.get("/panel").status_code == 302              # vuelve a /entrar
    finally:
        ejecutar_y_confirmar(app, "UPDATE usuario SET activo = 1 WHERE nombre_usuario = 'capitan.fermin'")

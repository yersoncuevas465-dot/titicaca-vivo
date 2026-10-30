"""Catálogos y usuarios en el modelo (F5): validaciones, UNIQUE y reglas que protegen la operación."""

import datetime as dt
from decimal import Decimal

import pytest

from app.modelos import (
    ErrorValidacion,
    PermisoDenegado,
    comunidad,
    embarcacion,
    familia,
    ruta,
    tarifa,
    temporada,
    tipo_pasajero,
    usuario,
)
from tests.conftest import actor, consultar_valor, ejecutar_y_confirmar

ADMIN, OPERADOR, ELENA, TEODORO = 1, 2, 3, 5


def guardar(app, funcion, registro_id, datos, quien=OPERADOR):
    with app.app_context():
        return funcion(actor(quien), registro_id, datos)


def errores(app, funcion, registro_id, datos, quien=OPERADOR):
    with pytest.raises(ErrorValidacion) as excinfo:
        guardar(app, funcion, registro_id, datos, quien)
    return excinfo.value.errores


@pytest.fixture
def borrar(app):
    """Borra al final los registros que la prueba creó: borrar.append(("tabla", id))."""
    creados = []
    yield creados
    for tabla, registro_id in reversed(creados):
        # Los nombres de tabla son constantes de la prueba, no datos de un usuario.
        ejecutar_y_confirmar(app, f"DELETE FROM {tabla} WHERE id = %s", (registro_id,))  # noqa: S608


def hoy(app):
    return consultar_valor(app, "SELECT CURDATE()")


# --- Lanchas -------------------------------------------------------------------------------------

LANCHA = {"nombre": "Lancha Prueba", "matricula": "pun-pr-0001", "capacidad_maxima": 15,
          "tipo": "lancha", "estado": "operativa", "ultimo_mantenimiento": None}


def test_crear_lancha_y_matricula_repetida(app, borrar):
    lancha_id = guardar(app, embarcacion.guardar, None, LANCHA)
    borrar.append(("embarcacion", lancha_id))
    assert consultar_valor(app, "SELECT matricula FROM embarcacion WHERE id = %s",
                           (lancha_id,)) == "PUN-PR-0001"                # se guarda en mayúsculas
    assert "matricula" in errores(app, embarcacion.guardar, None, LANCHA)  # UNIQUE (1062)


def test_una_lancha_con_salidas_por_venir_no_sale_de_operacion(app):
    actual = {**LANCHA, "nombre": "Qhapaq Qocha", "matricula": "PUN-LT-0101",
              "capacidad_maxima": 30}                       # lancha 1: salidas 10 y 13 (cupo 25)
    e = errores(app, embarcacion.guardar, 1, {**actual, "estado": "mantenimiento"})
    assert "salidas por venir" in e["estado"]
    e = errores(app, embarcacion.guardar, 1, {**actual, "capacidad_maxima": 20})
    assert "cupo 25" in e["capacidad_maxima"]


@pytest.mark.parametrize("cambios, campo", [
    ({"matricula": "x"}, "matricula"), ({"capacidad_maxima": 41}, "capacidad_maxima"),
    ({"tipo": "yate"}, "tipo"), ({"nombre": ""}, "nombre"),
])
def test_lancha_datos_invalidos(app, cambios, campo):
    assert campo in errores(app, embarcacion.guardar, None, {**LANCHA, **cambios})


def test_el_mantenimiento_no_puede_ser_futuro(app):
    datos = {**LANCHA, "ultimo_mantenimiento": hoy(app) + dt.timedelta(days=1)}
    assert "ultimo_mantenimiento" in errores(app, embarcacion.guardar, None, datos)


# --- Temporadas y tarifas (RN-04) -------------------------------------------------------------------

def test_las_temporadas_no_se_solapan(app, borrar):
    lejos = hoy(app) + dt.timedelta(days=3000)
    datos = {"nombre": "Temporada de prueba", "fecha_inicio": lejos,
             "fecha_fin": lejos + dt.timedelta(days=10), "recargo_porcentaje": Decimal("5")}
    borrar.append(("temporada", guardar(app, temporada.guardar, None, datos)))
    cruzada = {**datos, "fecha_inicio": lejos + dt.timedelta(days=5),
               "fecha_fin": lejos + dt.timedelta(days=20)}
    assert "Se cruza con «Temporada de prueba»" in errores(app, temporada.guardar, None,
                                                            cruzada)["fecha_inicio"]
    al_reves = {**datos, "fecha_fin": lejos - dt.timedelta(days=1)}
    assert "fecha_fin" in errores(app, temporada.guardar, None, al_reves)


def test_una_tarifa_nueva_cambia_el_precio_de_las_salidas_siguientes(app, borrar):
    from app.modelos import tarifa as modelo_tarifa

    datos = {"ruta_id": 1, "tipo_pasajero_id": 1, "precio_base": Decimal("45.00"),
             "vigente_desde": hoy(app), "vigente_hasta": None}
    tarifa_id = guardar(app, tarifa.guardar, None, datos)
    borrar.append(("tarifa", tarifa_id))
    with app.app_context():                                # salida 11: Uros, mañana
        base = {p["tipo_pasajero_id"]: p["precio_base"]
                for p in modelo_tarifa.precios_para_salida(11)}
    assert base[1] == Decimal("45.00")                     # gana la vigente más reciente (S-13)
    assert "vigente_desde" in errores(app, tarifa.guardar, None, datos)   # UNIQUE repetido


@pytest.mark.parametrize("cambios, campo", [
    ({"precio_base": Decimal("0")}, "precio_base"), ({"ruta_id": 99}, "ruta_id"),
    ({"tipo_pasajero_id": 99}, "tipo_pasajero_id"),
])
def test_tarifa_invalida(app, cambios, campo):
    datos = {"ruta_id": 1, "tipo_pasajero_id": 1, "precio_base": Decimal("10"),
             "vigente_desde": dt.date(2030, 1, 1), "vigente_hasta": None, **cambios}
    assert campo in errores(app, tarifa.guardar, None, datos)


def test_los_tipos_de_pasajero_solo_se_editan(app):
    assert "general" in errores(app, tipo_pasajero.guardar, None, {"nombre": "Bebé"})
    datos = {"nombre": "Niño o niña", "edad_minima": 10, "edad_maxima": 5}
    assert "edad_maxima" in errores(app, tipo_pasajero.guardar, 4, datos)


# --- Rutas y paradas (S-16) --------------------------------------------------------------------------

RUTA = {"codigo": "pru-01", "nombre": "Ruta de prueba", "descripcion": "", "duracion_horas": 4,
        "incluye_pernocte": True, "muelle_salida": "Muelle de Puno", "activa": True}


def test_ruta_nueva_con_paradas_y_una_sola_noche(app, borrar):
    ruta_id = guardar(app, ruta.guardar, None, RUTA)
    borrar.append(("ruta", ruta_id))                       # CASCADE: también borra sus paradas
    assert "codigo" in errores(app, ruta.guardar, None, RUTA)        # código repetido
    with app.app_context():
        operador = actor(OPERADOR)
        ruta.guardar_parada(operador, ruta_id, None, {"comunidad_id": 1, "orden": 1,
                                                      "minutos_estadia": 60, "es_pernocte": False})
        ruta.guardar_parada(operador, ruta_id, None, {"comunidad_id": 3, "orden": 2,
                                                      "minutos_estadia": 900, "es_pernocte": True})
        casos = [
            ({"comunidad_id": 2, "orden": 3, "minutos_estadia": 60, "es_pernocte": True},
             "es_pernocte"),                               # ya hay una noche (S-16)
            ({"comunidad_id": 3, "orden": 3, "minutos_estadia": 60, "es_pernocte": False},
             "comunidad_id"),                              # UNIQUE (ruta, comunidad)
            ({"comunidad_id": 2, "orden": 2, "minutos_estadia": 60, "es_pernocte": False},
             "orden"),                                     # UNIQUE (ruta, orden)
        ]
        for datos, campo in casos:
            with pytest.raises(ErrorValidacion) as excinfo:
                ruta.guardar_parada(operador, ruta_id, None, datos)
            assert campo in excinfo.value.errores
        paradas = ruta.paradas_panel(operador, ruta_id)
        assert [p["comunidad"] for p in paradas] == ["Uros", "Amantaní"]
        ruta.borrar_parada(operador, ruta_id, paradas[1]["id"])
        assert len(ruta.paradas_panel(operador, ruta_id)) == 1


def test_ruta_con_noche_y_salidas_protegida(app):
    actual = {**RUTA, "codigo": "URO-AMA-TAQ", "nombre": "Uros, Amantaní y Taquile",
              "duracion_horas": Decimal("33.0")}
    assert "incluye_pernocte" in errores(app, ruta.guardar, 3, {**actual, "incluye_pernocte": False})
    assert "activa" in errores(app, ruta.guardar, 3, {**actual, "activa": False})


# --- Comunidades y familias --------------------------------------------------------------------------

COMUNIDAD = {"nombre": "Isla Prueba Ñandú", "slug": "", "distrito": "Puno", "provincia": "Puno",
             "idioma_originario": "aimara", "senal": "debil", "whatsapp_contacto": "",
             "descripcion": "", "foto_credito": "", "latitud": None, "longitud": None,
             "tiene_hospedaje": True, "activa": True}


def test_comunidad_nueva_arma_su_slug(app, borrar):
    comunidad_id = guardar(app, comunidad.guardar, None, COMUNIDAD)
    borrar.append(("comunidad", comunidad_id))
    assert consultar_valor(app, "SELECT slug FROM comunidad WHERE id = %s",
                           (comunidad_id,)) == "isla-prueba-nandu"
    assert "nombre" in errores(app, comunidad.guardar, None, COMUNIDAD)        # UNIQUE
    assert "longitud" in errores(app, comunidad.guardar, None,
                                 {**COMUNIDAD, "nombre": "Otra", "latitud": Decimal("-15.8")})


def test_una_comunidad_en_rutas_activas_no_se_desactiva(app):
    with app.app_context():
        datos = comunidad.buscar_panel(actor(OPERADOR), 3)                      # Amantaní
    e = errores(app, comunidad.guardar, 3, {**datos, "activa": False, "tiene_hospedaje": False})
    assert "ruta(s) activa(s)" in e["activa"] and "tiene_hospedaje" in e


def test_familia_con_noches_asignadas(app, borrar):
    with app.app_context():
        datos = familia.buscar_panel(actor(OPERADOR), 3)          # tiene una noche mañana (2 personas)
    assert "activa" in errores(app, familia.guardar, 3, {**datos, "activa": False})
    assert "capacidad_personas" in errores(app, familia.guardar, 3,
                                           {**datos, "capacidad_personas": 1})
    nueva = {**datos, "nombre_familia": "Familia Prueba", "servicios": ["cena", "desayuno"]}
    familia_id = guardar(app, familia.guardar, None, nueva)
    borrar.append(("familia_anfitriona", familia_id))
    assert consultar_valor(app, "SELECT servicios FROM familia_anfitriona WHERE id = %s",
                           (familia_id,)) == "desayuno,cena"
    assert "servicios" in errores(app, familia.guardar, None, {**nueva, "servicios": ["piscina"]})


# --- Permisos en el modelo ----------------------------------------------------------------------------

@pytest.mark.parametrize("funcion", [embarcacion.guardar, ruta.guardar, tarifa.guardar,
                                     temporada.guardar, comunidad.guardar, familia.guardar])
def test_la_guia_no_toca_los_catalogos(app, funcion):
    with pytest.raises(PermisoDenegado):
        guardar(app, funcion, None, {}, quien=ELENA)


# --- Usuarios (solo admin) ----------------------------------------------------------------------------

USUARIO = {"nombre_usuario": "Guia.Prueba", "nombre_completo": "Rosa Prueba Lago", "correo": "",
           "telefono": "", "rol_id": 3, "comunidad_id": 2, "licencia_navegacion": "",
           "contrasena": "Clave-de-prueba-1", "activo": True}


def test_crear_un_guia_que_puede_entrar(app, borrar):
    usuario_id = guardar(app, usuario.guardar, None, USUARIO, quien=ADMIN)
    borrar.append(("usuario", usuario_id))
    with app.app_context():
        sesion = usuario.verificar_credenciales("guia.prueba", "Clave-de-prueba-1")
    assert sesion and sesion.rol == "guia" and sesion.comunidad_id == 2
    detalle = consultar_valor(app, "SELECT detalle FROM bitacora WHERE tabla_afectada = 'usuario' "
                                   "AND registro_id = %s AND accion = 'creacion'", (usuario_id,))
    assert "Clave" not in detalle and '"contrasena_cambiada": true' in detalle
    # Editar sin contraseña conserva la anterior
    guardar(app, usuario.guardar, usuario_id, {**USUARIO, "contrasena": ""}, quien=ADMIN)
    with app.app_context():
        assert usuario.verificar_credenciales("guia.prueba", "Clave-de-prueba-1")
    assert "nombre_usuario" in errores(app, usuario.guardar, None, USUARIO, quien=ADMIN)


@pytest.mark.parametrize("cambios, campo", [
    ({"comunidad_id": 0}, "comunidad_id"),                         # guía sin comunidad
    ({"rol_id": 4}, "licencia_navegacion"),                        # capitán sin licencia
    ({"nombre_usuario": "Ñ ñ"}, "nombre_usuario"),
    ({"contrasena": "corta"}, "contrasena"),
    ({"correo": "no-es-correo"}, "correo"),
    ({"rol_id": 9}, "rol_id"),
])
def test_usuario_invalido(app, cambios, campo):
    assert campo in errores(app, usuario.guardar, None, {**USUARIO, **cambios}, quien=ADMIN)


def test_reglas_para_no_quedar_sin_admin_ni_sin_capitan(app):
    with app.app_context():
        admin = usuario.buscar_para_editar(actor(ADMIN), ADMIN)
        teodoro = usuario.buscar_para_editar(actor(ADMIN), TEODORO)
    e = errores(app, usuario.guardar, ADMIN, {**admin, "activo": False, "rol_id": 2}, quien=ADMIN)
    assert "propio usuario" in e["activo"] and "rol de admin" in e["rol_id"]
    e = errores(app, usuario.guardar, TEODORO, {**teodoro, "activo": False}, quien=ADMIN)
    assert "salida(s) por venir" in e["activo"]


def test_solo_el_admin_maneja_usuarios(app):
    with pytest.raises(PermisoDenegado):
        guardar(app, usuario.guardar, None, USUARIO, quien=OPERADOR)
    with app.app_context(), pytest.raises(PermisoDenegado):
        usuario.listar(actor(OPERADOR))

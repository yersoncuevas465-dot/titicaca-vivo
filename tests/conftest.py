"""Configuración común de las pruebas.

- Se usa SOLO la base titicaca_vivo_pruebas: se borra y se crea de nuevo con
  los scripts 01, 02 y 03 al empezar la sesión de pruebas.
- Cada prueba trabaja dentro de una transacción que se deshace (ROLLBACK)
  al final: así una prueba nunca ensucia a la siguiente.
"""

import itertools
import re

import pymysql
import pytest

from app import bd, crear_app, diagnostico
from app.config import ConfigPruebas
from app.seguridad import limitador

# Contraseñas de los usuarios demo (README)
CLAVES = {
    "admin": "Admin-Titicaca26",
    "operador": "Operador-Titicaca26",
    "guia.elena": "Guia-Titicaca26",
    "guia.marco": "Guia-Titicaca26",
    "capitan.teodoro": "Capitan-Titicaca26",
    "capitan.fermin": "Capitan-Titicaca26",
    "residente.juana": "Residente-Titicaca26",      # v2.9: Taquile
    "residente.felix": "Residente-Titicaca26",      # Amantaní
    "residente.sonia": "Residente-Titicaca26",      # Uros
}

# Códigos de error de MariaDB que se comprueban en las pruebas
ERROR_CHECK = 4025        # CONSTRAINT `...` failed
ERROR_DUPLICADO = 1062    # Duplicate entry (UNIQUE)
ERROR_FK_HIJO = 1452      # no existe el padre
ERROR_FK_PADRE = 1451     # el padre tiene hijos (RESTRICT)
ERROR_DATO_INVALIDO = 1265  # Data truncated (ENUM inválido en modo estricto)
ERROR_SIGNAL = 1644       # SIGNAL SQLSTATE '45000' lanzado por un trigger


@pytest.fixture(scope="session")
def app():
    aplicacion = crear_app(ConfigPruebas)
    nombre = aplicacion.config["BD_NOMBRE"]
    assert nombre.endswith("_pruebas"), "Las pruebas solo pueden correr sobre una base *_pruebas"
    try:
        bd.reiniciar_base(aplicacion.config)
    except pymysql.err.MySQLError as error:
        # Sin base no hay prueba que valga: se corta aquí con UNA explicación, en vez de 486 errores.
        pytest.exit(f"No se pudo preparar la base de pruebas '{nombre}'.\n"
                    f"{diagnostico.explicar(error, aplicacion.config)}", returncode=3)
    return aplicacion


@pytest.fixture
def con(app):
    """Conexión propia de la prueba; al terminar se hace ROLLBACK."""
    conexion = bd.conectar(app.config)
    yield conexion
    conexion.rollback()
    conexion.close()


@pytest.fixture
def cur(con):
    with con.cursor() as cursor:
        yield cursor


@pytest.fixture(autouse=True)
def limite_de_intentos_limpio(app):
    """El límite de /entrar vive en memoria: se vacía antes de cada prueba.

    Pide `app` porque el limitador recién tiene memoria cuando la app existe (sin esto, un
    archivo de pruebas que no usa la app falla si se corre solo)."""
    limitador.reset()
    yield


@pytest.fixture
def cliente(app):
    return app.test_client()


def token_csrf(respuesta):
    """Saca el token CSRF del HTML de un formulario."""
    # <input ... name="csrf_token" ... value="..."> (los atributos pueden venir en cualquier orden)
    encontrado = re.search(r'<input[^>]*name="csrf_token"[^>]*value="([^"]+)"', respuesta.get_data(True))
    assert encontrado, "El formulario no trae token CSRF"
    return encontrado.group(1)


def iniciar_sesion(cliente, usuario, clave=None, siguiente=None):
    """Hace GET /entrar (para el token) y POST /entrar. Devuelve la respuesta del POST."""
    url = "/entrar" + (f"?next={siguiente}" if siguiente else "")
    token = token_csrf(cliente.get(url))
    return cliente.post(url, data={"csrf_token": token, "nombre_usuario": usuario,
                                   "contrasena": clave if clave is not None else CLAVES[usuario]})


def ejecutar_y_confirmar(app, sql, parametros=None):
    """Cambia algo en la base de pruebas y lo confirma (para preparar un caso)."""
    conexion = bd.conectar(app.config)
    try:
        with conexion.cursor() as cursor:
            cursor.execute(sql, parametros)
        conexion.commit()
    finally:
        conexion.close()


def consultar_valor(app, sql, parametros=None):
    conexion = bd.conectar(app.config)
    try:
        with conexion.cursor() as cursor:
            cursor.execute(sql, parametros)
            fila = cursor.fetchone()
            return next(iter(fila.values())) if fila else None
    finally:
        conexion.close()


def limpiar_salida(app, salida_id):
    """Borra una salida de prueba con todo lo que se creó en ella (reservas, pagos, hospedajes)."""
    conexion = bd.conectar(app.config)
    try:
        with conexion.cursor() as cursor:
            # Una reserva reprogramada (F6) apunta a la salida vieja: se suelta antes de borrarla.
            cursor.execute("UPDATE reserva SET reprogramada_desde_salida_id = NULL "
                           "WHERE reprogramada_desde_salida_id = %s", (salida_id,))
            subconsulta = "(SELECT id FROM reserva WHERE salida_id = %s)"
            cursor.execute(f"DELETE FROM hospedaje WHERE reserva_id IN {subconsulta}", (salida_id,))
            cursor.execute(f"DELETE FROM pago WHERE reserva_id IN {subconsulta}", (salida_id,))
            cursor.execute("DELETE FROM abordaje WHERE salida_id = %s", (salida_id,))
            cursor.execute("DELETE FROM reserva WHERE salida_id = %s", (salida_id,))   # CASCADE: pasajeros
            cursor.execute("DELETE FROM salida WHERE id = %s", (salida_id,))
            # Turistas de prueba (documentos 799...) que ya no tienen reservas
            cursor.execute("DELETE FROM turista WHERE numero_documento LIKE '799%' "
                           "AND id NOT IN (SELECT turista_id FROM reserva)")
        conexion.commit()
    finally:
        conexion.close()


@pytest.fixture
def salida_prueba(app):
    """Crea salidas de prueba en la lancha 4 (sin otras salidas) y las borra al terminar.

    Uso: salida_id = salida_prueba(ruta_id=1, cupo=5, dias=20, hora=8)
    """
    creadas = []

    def crear(ruta_id=1, cupo=5, dias=20, hora=8, horas_duracion=3, estado="programada"):
        conexion = bd.conectar(app.config)
        try:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO salida (ruta_id, embarcacion_id, capitan_id, fecha_hora_zarpe,
                                        fecha_hora_retorno, cupo, estado, creada_por)
                    VALUES (%s, 4, 5, CURDATE() + INTERVAL %s DAY + INTERVAL %s HOUR,
                            CURDATE() + INTERVAL %s DAY + INTERVAL %s HOUR, %s, %s, 2)
                    """,
                    (ruta_id, dias, hora, dias, hora + horas_duracion, cupo, estado),
                )
                salida_id = cursor.lastrowid
            conexion.commit()
        finally:
            conexion.close()
        creadas.append(salida_id)
        return salida_id

    yield crear
    for salida_id in creadas:
        limpiar_salida(app, salida_id)


@pytest.fixture
def salida_cerca(app):
    """Salidas en la lancha 4 que zarpan dentro de `minutos` (para las ventanas de RN-12).

    Uso: salida_id = salida_cerca(minutos=30, guia_id=4)
    """
    creadas = []

    def crear(minutos=30, ruta_id=1, cupo=8, capitan_id=5, guia_id=None):
        conexion = bd.conectar(app.config)
        try:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO salida (ruta_id, embarcacion_id, capitan_id, guia_id, fecha_hora_zarpe,
                                        fecha_hora_retorno, cupo, estado, creada_por)
                    VALUES (%s, 4, %s, %s, NOW() + INTERVAL %s MINUTE,
                            NOW() + INTERVAL %s MINUTE, %s, 'programada', 2)
                    """,
                    (ruta_id, capitan_id, guia_id, minutos, minutos + 180, cupo),
                )
                salida_id = cursor.lastrowid
            conexion.commit()
        finally:
            conexion.close()
        creadas.append(salida_id)
        return salida_id

    yield crear
    for salida_id in creadas:
        limpiar_salida(app, salida_id)


_documentos_panel = itertools.count(1)


def reservar_en(app, salida_id, acompanantes=0, metodo="muelle"):
    """Crea una reserva con el modelo de la F4 (documentos 7997xxxx) y devuelve su código."""
    from app.modelos import reserva

    def persona(nombres, tipo):
        return reserva.Persona(nombres, "Prueba Panel", "DNI",
                               f"7997{next(_documentos_panel):04d}", "PE", tipo)

    solicitud = reserva.Solicitud(
        salida_id=salida_id, titular=persona("Ana", 1), telefono="987654321", correo=None,
        titular_viaja=True, metodo_pago=metodo,
        acompanantes=[persona("Leo", 4) for _ in range(acompanantes)])
    with app.app_context():
        return reserva.crear(solicitud, reserva.generar_token())[0]


def actor(usuario_id):
    """El usuario de la semilla como 'actor' de los modelos (1 admin, 2 operador, 3 Elena,
    4 Marco, 5 Teodoro, 6 Fermín). Se llama dentro de un app_context."""
    from app.modelos import usuario

    return usuario.buscar_por_id(usuario_id)


def codigo_error(excinfo):
    """Número de error de MariaDB dentro de una excepción de PyMySQL."""
    return excinfo.value.args[0]


def falla_con(cursor, sql, parametros=None):
    """Ejecuta una sentencia que DEBE fallar y devuelve (codigo, mensaje)."""
    with pytest.raises(pymysql.MySQLError) as excinfo:
        cursor.execute(sql, parametros)
    return codigo_error(excinfo), str(excinfo.value.args[1])


def precio_en_pagina(app, salida_id, precio_base):
    """«S/ 88.00»: la tarifa base con el recargo de la temporada de esa salida (RN-04), como la
    muestra la página. Las salidas de la semilla van relativas a hoy y las temporadas tienen fechas
    fijas: según el día en que se corran las pruebas, una salida puede caer en temporada (del 1 al 7
    de noviembre, la salida 10 cae en la Semana Jubilar de Puno)."""
    from app.modelos import tarifa
    from app.servicios import formato

    return formato.soles(tarifa.calcular_precio(precio_base, recargo_de_salida(app, salida_id)))


def recargo_de_salida(app, salida_id):
    """El recargo (%) de la temporada (ya guardada) en la que cae esa salida, o 0."""
    return consultar_valor(
        app, "SELECT COALESCE(MAX(te.recargo_porcentaje), 0) AS recargo FROM salida s "
             "JOIN temporada te ON DATE(s.fecha_hora_zarpe) BETWEEN te.fecha_inicio AND te.fecha_fin "
             "WHERE s.id = %s", (salida_id,))

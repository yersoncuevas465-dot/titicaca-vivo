"""Conexión a MariaDB con PyMySQL (sin ORM).

- Una conexión por petición, guardada en flask.g y cerrada al terminar la petición.
- autocommit apagado: los cambios solo quedan con un COMMIT explícito (transaccion()).
- Cada conexión fija la hora de Lima (RN-15) y el modo estricto de SQL.
"""

import re
from contextlib import contextmanager

import pymysql
from flask import current_app, g

# Se ejecuta al abrir cada conexión. XAMPP trae un sql_mode NO estricto (un ENUM
# inválido se guardaría como ''); aquí lo volvemos estricto para esta sesión.
COMANDO_INICIAL = (
    "SET time_zone = '-05:00', SESSION sql_mode = 'STRICT_TRANS_TABLES,"
    "ERROR_FOR_DIVISION_BY_ZERO,NO_ZERO_IN_DATE,NO_ZERO_DATE,NO_ENGINE_SUBSTITUTION'"
)

ORDEN_SCRIPTS = ("01_esquema.sql", "02_vistas_triggers.sql", "03_datos.sql")

TABLAS = (
    "rol", "usuario", "comunidad", "familia_anfitriona", "embarcacion", "ruta", "ruta_parada",
    "temporada", "tipo_pasajero", "tarifa", "salida", "turista", "reserva", "reserva_pasajero",
    "pago", "hospedaje", "abordaje", "alerta_lago", "resena", "bitacora",
)

_NOMBRE_BASE_VALIDO = re.compile(r"^[A-Za-z0-9_]{1,64}$")


def conectar(config, base=None, usar_base=True):
    """Abre una conexión nueva. `config` es app.config (o un dict con las claves BD_*)."""
    return pymysql.connect(
        host=config["BD_HOST"],
        port=int(config["BD_PUERTO"]),
        user=config["BD_USUARIO"],
        password=config["BD_CONTRASENA"],
        database=(base or config["BD_NOMBRE"]) if usar_base else None,
        charset="utf8mb4",
        collation="utf8mb4_spanish_ci",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
        init_command=COMANDO_INICIAL,
        connect_timeout=5,
    )


def obtener_conexion():
    """Devuelve la conexión de esta petición (la abre la primera vez)."""
    if "bd" not in g:
        g.bd = conectar(current_app.config)
    return g.bd


def cerrar_conexion(_error=None):
    """Al terminar la petición: deshace lo que no se confirmó y cierra."""
    conexion = g.pop("bd", None)
    if conexion is not None:
        try:
            conexion.rollback()
        finally:
            conexion.close()


@contextmanager
def transaccion(lectura_actual=False):
    """Bloque `with transaccion() as cur:` → COMMIT si todo sale bien, ROLLBACK si hay error.

    lectura_actual=True (D-50): descarta las lecturas previas de la petición y abre la
    transacción en READ COMMITTED, para que cada SELECT vea lo último confirmado por otras
    transacciones. Se usa junto con FOR UPDATE en las operaciones que cuentan cupos o cruces.
    """
    conexion = obtener_conexion()
    if lectura_actual:
        conexion.rollback()
        with conexion.cursor() as cur:
            cur.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
        conexion.begin()
    cursor = conexion.cursor()
    try:
        yield cursor
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        cursor.close()


def consultar(sql, parametros=None):
    """Ejecuta un SELECT con parámetros %s y devuelve todas las filas (lista de dict)."""
    with obtener_conexion().cursor() as cursor:
        cursor.execute(sql, parametros)
        return list(cursor.fetchall())


def consultar_uno(sql, parametros=None):
    """Ejecuta un SELECT y devuelve la primera fila (dict) o None."""
    with obtener_conexion().cursor() as cursor:
        cursor.execute(sql, parametros)
        return cursor.fetchone()


def init_app(app):
    app.teardown_appcontext(cerrar_conexion)


# ---------------------------------------------------------------------------
# Scripts SQL (los usa "flask bd reiniciar" y las pruebas)
# ---------------------------------------------------------------------------

def dividir_sentencias(texto):
    """Parte un script .sql en sentencias sueltas, como lo hace phpMyAdmin.

    PyMySQL ejecuta una sentencia a la vez y no entiende la directiva DELIMITER
    (que usamos para los triggers). Aquí se respeta DELIMITER, las comillas
    ('...', "...", `...`) y los comentarios (-- , # y /* */), para no cortar
    una sentencia en un ';' que esté dentro de un texto o de un trigger.
    """
    sentencias, actual = [], []
    delimitador = ";"
    i, n = 0, len(texto)
    inicio_de_linea = True

    while i < n:
        if inicio_de_linea:
            fin_linea = texto.find("\n", i)
            fin_linea = n if fin_linea == -1 else fin_linea
            linea = texto[i:fin_linea].strip()
            if linea.upper().startswith("DELIMITER ") and not "".join(actual).strip():
                delimitador = linea.split(None, 1)[1].strip()
                i = fin_linea + 1
                continue
            inicio_de_linea = False

        if texto.startswith(delimitador, i):
            sentencia = "".join(actual).strip()
            if sentencia:
                sentencias.append(sentencia)
            actual = []
            i += len(delimitador)
            continue

        caracter = texto[i]
        if caracter in "'\"`":
            j = i + 1
            while j < n:
                if texto[j] == "\\" and caracter != "`":
                    j += 2
                    continue
                if texto[j] == caracter:
                    if j + 1 < n and texto[j + 1] == caracter:  # comilla duplicada: ''
                        j += 2
                        continue
                    break
                j += 1
            actual.append(texto[i:j + 1])
            i = j + 1
            continue

        # "-- " solo es comentario si va seguido de espacio o fin de línea (regla de MariaDB)
        es_guion = texto.startswith("--", i) and (i + 2 >= n or texto[i + 2] in " \t\r\n")
        if es_guion or caracter == "#":
            fin_linea = texto.find("\n", i)
            i = n if fin_linea == -1 else fin_linea  # el \n se procesa: marca inicio de línea
            continue
        if texto.startswith("/*", i):
            fin = texto.find("*/", i + 2)
            i = n if fin == -1 else fin + 2
            continue

        actual.append(caracter)
        if caracter == "\n":
            inicio_de_linea = True
        i += 1

    resto = "".join(actual).strip()
    if resto:
        sentencias.append(resto)
    return sentencias


def ejecutar_script(conexion, ruta):
    """Ejecuta un archivo .sql completo y confirma. Devuelve cuántas sentencias corrió."""
    sentencias = dividir_sentencias(ruta.read_text(encoding="utf-8"))
    with conexion.cursor() as cursor:
        for sentencia in sentencias:
            cursor.execute(sentencia)  # sin parámetros: el texto del script va tal cual
    conexion.commit()
    return len(sentencias)


def reiniciar_base(config, nombre_base=None):
    """Borra la base, la vuelve a crear y ejecuta 01, 02 y 03. Devuelve {archivo: sentencias}."""
    nombre = nombre_base or config["BD_NOMBRE"]
    # Un nombre de base no puede ir como parámetro %s; por eso se valida con una lista blanca.
    if not _NOMBRE_BASE_VALIDO.match(nombre):
        raise ValueError(f"Nombre de base no válido: {nombre!r}")

    conexion = conectar(config, usar_base=False)
    resultado = {}
    try:
        with conexion.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS `{nombre}`")  # noqa: S608 (nombre validado)
            cursor.execute(
                f"CREATE DATABASE `{nombre}` CHARACTER SET utf8mb4 COLLATE utf8mb4_spanish_ci"
            )
            cursor.execute(f"USE `{nombre}`")
        for archivo in ORDEN_SCRIPTS:
            resultado[archivo] = ejecutar_script(conexion, config["CARPETA_SQL"] / archivo)
    finally:
        conexion.close()
    return resultado


def contar_filas(conexion):
    """Devuelve [(tabla, filas)] de las 20 tablas (evidencia del nivel Bronce)."""
    # Una sola consulta: cada SELECT cuenta una tabla y UNION ALL los junta en una lista.
    # Los nombres salen de la constante TABLAS, nunca de lo que escribe un usuario.
    consulta = " UNION ALL ".join(
        f"SELECT '{tabla}' AS tabla, COUNT(*) AS filas FROM {tabla}" for tabla in TABLAS  # noqa: S608
    )
    with conexion.cursor() as cursor:
        cursor.execute(consulta)
        return [(fila["tabla"], fila["filas"]) for fila in cursor.fetchall()]

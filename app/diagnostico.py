"""Diagnóstico de la base: convierte cada error de conexión en lo que hay que hacer.

Lo usan servidor.py (antes de arrancar), los comandos `flask bd ...`, la página de error y las
pruebas (conftest). Así, una PC con MySQL apagado muestra UNA explicación clara en español,
en vez de cientos de trazas iguales.
"""

import pymysql

from app import bd

# Errores que significan "no hay servidor": MySQL apagado, otro puerto o la conexión se cortó.
SIN_SERVIDOR = {2002, 2003, 2006, 2013}

# Lo que dejan 01_esquema.sql y 02_vistas_triggers.sql (las 21 tablas están en bd.TABLAS).
VISTAS, TRIGGERS, PROCEDIMIENTOS = 2, 4, 1

RECARGAR = "Qué hacer: cárgala con  flask bd reiniciar --si  (21 tablas con los datos de prueba)."
CREAR_BD = "Qué hacer (PASO 4 de INSTRUCCIONES.txt):  python scripts/crear_bd.py"


def codigo_de(error):
    """Número de error de MariaDB (2003, 1045...) o None si no lo trae."""
    argumentos = getattr(error, "args", ())
    return argumentos[0] if argumentos and isinstance(argumentos[0], int) else None


def sin_servidor(error):
    """True si el error dice que MySQL no responde (apagado o caído)."""
    return isinstance(error, pymysql.err.OperationalError) and codigo_de(error) in SIN_SERVIDOR


def explicar(error, config):
    """Causa y arreglo, en español, de un error de PyMySQL. La primera línea es la causa."""
    codigo = codigo_de(error)
    destino = f"{config['BD_HOST']}:{config['BD_PUERTO']}"
    usuario, base = config["BD_USUARIO"], config["BD_NOMBRE"]
    if codigo in SIN_SERVIDOR:
        return (f"MySQL no responde en {destino}.\n"
                "Qué hacer: abre XAMPP Control Panel y pulsa Start en MySQL (se pone en verde).\n"
                "Si XAMPP dice «Port 3306 in use», mira «Problemas comunes» en INSTRUCCIONES.txt.")
    if codigo == 1045:
        vacia = " (hoy BD_CONTRASENA está vacía)" if not config["BD_CONTRASENA"] else ""
        return (f"MySQL no aceptó al usuario '{usuario}' con la contraseña del .env{vacia}.\n"
                f"{CREAR_BD} Le pone al usuario la\n"
                "contraseña de BD_CONTRASENA del .env (y si está vacía, genera una).")
    if codigo in (1044, 1049):
        return (f"La base '{base}' no existe o '{usuario}' no tiene permiso sobre ella.\n"
                f"{CREAR_BD} Crea las 2 bases y el usuario.")
    if codigo == 1146:
        return f"A la base '{base}' le falta una tabla: está vacía o a medio cargar.\n{RECARGAR}"
    return f"MariaDB respondió con un error: {error}"


def revisar(config):
    """Revisa la base de la app. Devuelve (problema, estado).

    problema es None si la base está lista; si no, el texto con la causa y el arreglo.
    estado trae la versión del servidor, tablas, vistas, triggers, filas y salidas de hoy.
    """
    try:
        conexion = bd.conectar(config)
    except pymysql.err.MySQLError as error:
        return explicar(error, config), {}
    try:
        with conexion.cursor() as cur:
            # Devuelve la versión del servidor; cuántas tablas, vistas, triggers y procedimientos
            # tiene la base de la app (lo que crean 01_esquema.sql y 02_vistas_triggers.sql), y
            # cuándo se creó la tabla salida: la semilla pone sus fechas a partir de ESE día.
            cur.execute(
                """
                SELECT VERSION() AS version,
                  (SELECT COUNT(*) FROM information_schema.TABLES
                   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE') AS tablas,
                  (SELECT COUNT(*) FROM information_schema.VIEWS
                   WHERE TABLE_SCHEMA = DATABASE()) AS vistas,
                  (SELECT COUNT(*) FROM information_schema.TRIGGERS
                   WHERE TRIGGER_SCHEMA = DATABASE()) AS triggers,
                  (SELECT COUNT(*) FROM information_schema.ROUTINES
                   WHERE ROUTINE_SCHEMA = DATABASE()) AS procedimientos,
                  (SELECT CREATE_TIME FROM information_schema.TABLES
                   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'salida') AS cargada_en
                """
            )
            estado = cur.fetchone()
        if (estado["tablas"] < len(bd.TABLAS) or estado["vistas"] < VISTAS
                or estado["triggers"] < TRIGGERS or estado["procedimientos"] < PROCEDIMIENTOS):
            return (f"La base '{config['BD_NOMBRE']}' está vacía o incompleta: "
                    f"{estado['tablas']} de {len(bd.TABLAS)} tablas, {estado['vistas']} de "
                    f"{VISTAS} vistas y {estado['triggers']} de {TRIGGERS} triggers.\n{RECARGAR}"
                    ), estado
        filas = dict(bd.contar_filas(conexion))
        with conexion.cursor() as cur:
            # Devuelve cuántas salidas no canceladas hay hoy y de hoy en adelante
            # (la demostración necesita salidas por venir).
            cur.execute(
                """
                SELECT COALESCE(SUM(fecha_hora_zarpe < CURDATE() + INTERVAL 1 DAY), 0)
                         AS salidas_hoy,
                       COUNT(*) AS salidas_desde_hoy
                FROM salida
                WHERE fecha_hora_zarpe >= CURDATE() AND estado <> 'cancelada'
                """
            )
            salidas = cur.fetchone()
    except pymysql.err.MySQLError as error:
        return explicar(error, config), {}
    finally:
        conexion.close()
    estado.update(filas=sum(filas.values()), salidas_hoy=int(salidas["salidas_hoy"]),
                  salidas_desde_hoy=int(salidas["salidas_desde_hoy"]))
    if not filas.get("usuario"):
        return f"La base no tiene usuarios: nadie podrá entrar al panel.\n{RECARGAR}", estado
    return None, estado

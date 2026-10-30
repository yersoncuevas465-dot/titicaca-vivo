"""Respaldos de la base (D-116 a D-118): un archivo .sql con todo para dejar la base como estaba,
el respaldo automático y el reporte general para Excel.

Qué lleva un respaldo, en este orden (así se restaura en una base vacía o en una llena):
1. Borra las vistas y las tablas que hay (con FOREIGN_KEY_CHECKS = 0).
2. Crea cada tabla con su estructura real (SHOW CREATE TABLE: llaves, CHECK y AUTO_INCREMENT).
3. Carga los datos con INSERT, leídos todos en UNA foto consistente de la base
   (START TRANSACTION WITH CONSISTENT SNAPSHOT): nada queda a medias aunque alguien reserve.
4. Al final, las vistas, el procedimiento y los triggers de database/02_vistas_triggers.sql, la
   fuente oficial del proyecto. Van después de los datos, para que los triggers no frenen la carga,
   y salen del script (no de SHOW CREATE) para no arrastrar el DEFINER de nadie: así el respaldo se
   restaura con titicaca_app, con root o con phpMyAdmin.

Se restaura con `flask bd restaurar`, con phpMyAdmin (Importar) o con la consola de MariaDB.
Los archivos quedan en respaldos/: fuera del ZIP de entrega y de git, porque llevan datos
personales.
"""

import contextlib
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import current_app

from app import bd
from app.modelos import ErrorNegocio, bitacora, exigir_rol

CABECERA = "-- Respaldo de Titicaca Vivo"
FIN = "-- Fin del respaldo"
PATRON_NOMBRE = re.compile(
    r"^respaldo_\d{8}_\d{6}(?:_(auto|consola|antes-de-restaurar|antes-de-reiniciar))?\.sql$")
TIPOS = {None: "Manual", "auto": "Automático", "consola": "Consola",
         "antes-de-restaurar": "Antes de restaurar", "antes-de-reiniciar": "Antes de reiniciar"}
FILAS_POR_INSERT = 100
_candado = threading.Lock()        # un respaldo a la vez: el automático y el del panel no se pisan


def carpeta():
    ruta = Path(current_app.config["RESPALDOS_CARPETA"])
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def _ahora():
    return datetime.now(ZoneInfo(current_app.config["ZONA_HORARIA"])).replace(tzinfo=None)


def _fecha_de(ruta):
    zona = ZoneInfo(current_app.config["ZONA_HORARIA"])
    return datetime.fromtimestamp(ruta.stat().st_mtime, zona).replace(tzinfo=None)


def listar():
    """Los respaldos guardados, el más nuevo primero: [{nombre, tipo, kb, fecha}]."""
    respaldos = []
    for ruta in carpeta().glob("respaldo_*.sql"):
        encontrado = PATRON_NOMBRE.match(ruta.name)
        if encontrado:
            respaldos.append({"nombre": ruta.name, "tipo": TIPOS[encontrado.group(1)],
                              "kb": round(ruta.stat().st_size / 1024, 1), "fecha": _fecha_de(ruta)})
    return sorted(respaldos, key=lambda r: (r["fecha"], r["nombre"]), reverse=True)


def ultimo():
    """El respaldo más nuevo, o None (lo muestra «Tu trabajo de hoy» del admin)."""
    respaldos = listar()
    return respaldos[0] if respaldos else None


def _podar():
    """Deja solo los RESPALDOS_CONSERVAR más nuevos."""
    for viejo in listar()[current_app.config["RESPALDOS_CONSERVAR"]:]:
        # Si alguien lo tiene abierto, se borra la próxima vez.
        with contextlib.suppress(OSError):
            (carpeta() / viejo["nombre"]).unlink()


# --- Crear un respaldo -------------------------------------------------------------------------

def _valor(conexion, valor):
    if isinstance(valor, (set, frozenset)):        # una columna SET, por si llegara como conjunto
        valor = ",".join(sorted(valor))
    return conexion.escape(valor)


def _escribir(archivo, conexion):
    """Escribe el respaldo con su propia conexión, en una foto consistente.

    Devuelve (tablas, filas)."""
    with conexion.cursor() as cur:
        cur.execute("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        cur.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT")
        # Devuelve las tablas y las vistas de la base, cada una con su tipo.
        cur.execute("SHOW FULL TABLES")
        tipos = {next(iter(fila.values())): fila["Table_type"] for fila in cur.fetchall()}
        if any(not re.fullmatch(r"\w+", nombre, re.ASCII) for nombre in tipos):
            raise ErrorNegocio("La base tiene un nombre de tabla inesperado: no se respalda.")
        orden = {tabla: i for i, tabla in enumerate(bd.TABLAS)}       # primero los catálogos
        tablas = sorted((t for t, tipo in tipos.items() if tipo == "BASE TABLE"),
                        key=lambda t: (orden.get(t, len(orden)), t))
        if not tablas:
            raise ErrorNegocio("La base no tiene tablas: no hay nada que respaldar.")
        vistas = sorted(t for t, tipo in tipos.items() if tipo == "VIEW")
        if vistas:
            archivo.write("DROP VIEW IF EXISTS " + ", ".join(f"`{v}`" for v in vistas) + ";\n")
        archivo.write("DROP TABLE IF EXISTS " + ", ".join(f"`{t}`" for t in tablas) + ";\n")

        filas_totales = 0
        for tabla in tablas:
            # Devuelve la estructura exacta de la tabla (llaves, CHECK, AUTO_INCREMENT).
            cur.execute(f"SHOW CREATE TABLE `{tabla}`")  # noqa: S608 (nombre de la base, validado)
            estructura = cur.fetchone()["Create Table"]
            # Devuelve todas las filas de la tabla (dentro de la misma foto de la base).
            cur.execute(f"SELECT * FROM `{tabla}`")  # noqa: S608 (nombre de la base, validado)
            filas = cur.fetchall()
            columnas = ", ".join(f"`{d[0]}`" for d in cur.description)
            archivo.write(f"\n-- Tabla {tabla}: {len(filas)} fila(s)\n{estructura};\n")
            for inicio in range(0, len(filas), FILAS_POR_INSERT):
                lote = filas[inicio:inicio + FILAS_POR_INSERT]
                valores = ",\n".join("(" + ", ".join(_valor(conexion, v) for v in fila.values())
                                     + ")" for fila in lote)
                archivo.write(f"INSERT INTO `{tabla}` ({columnas}) VALUES\n{valores};\n")
            filas_totales += len(filas)
    conexion.commit()
    return len(tablas), filas_totales


def crear(tipo=None, usuario_id=None, ip=None):
    """Guarda un respaldo nuevo de la base y lo anota en la bitácora. Devuelve {nombre, tipo, kb,
    fecha, tablas, filas}. `tipo`: None (desde el panel), 'auto', 'consola', 'antes-de-…'."""
    config = current_app.config
    objetos = (config["CARPETA_SQL"] / "02_vistas_triggers.sql").read_text(encoding="utf-8")
    with _candado:
        nombre = f"respaldo_{_ahora():%Y%m%d_%H%M%S}{'_' + tipo if tipo else ''}.sql"
        while (carpeta() / nombre).exists():                       # dos en el mismo segundo
            time.sleep(1)
            nombre = f"respaldo_{_ahora():%Y%m%d_%H%M%S}{'_' + tipo if tipo else ''}.sql"
        destino = carpeta() / nombre
        parcial = destino.with_suffix(".parcial")
        listo = False
        conexion = bd.conectar(config)
        try:
            with parcial.open("w", encoding="utf-8", newline="\n") as archivo:
                archivo.write(
                    f"{CABECERA} · base {config['BD_NOMBRE']} · {_ahora():%d/%m/%Y %H:%M:%S} "
                    "(hora de Lima)\n"
                    "-- Restaurarlo BORRA lo que hay en la base y deja lo de este archivo:\n"
                    f"--   flask bd restaurar respaldos\\{nombre}\n"
                    "--   o phpMyAdmin: elegir la base → Importar → este archivo\n"
                    f"--   o C:\\xampp\\mysql\\bin\\mysql.exe -u root {config['BD_NOMBRE']} "
                    f"< respaldos\\{nombre}\n\n"
                    "SET NAMES utf8mb4 COLLATE utf8mb4_spanish_ci;\n"
                    "SET time_zone = '-05:00';\n"
                    "SET FOREIGN_KEY_CHECKS = 0;\n")
                tablas, filas = _escribir(archivo, conexion)
                archivo.write("\nSET FOREIGN_KEY_CHECKS = 1;\n\n"
                              "-- Vistas, procedimiento y triggers: "
                              "database/02_vistas_triggers.sql\n"
                              f"{objetos.rstrip()}\n\n{FIN}: {tablas} tablas y {filas} filas.\n")
            os.replace(parcial, destino)          # el archivo aparece completo o no aparece
            listo = True
        except OSError as error:
            raise ErrorNegocio(f"No se pudo escribir el respaldo en {carpeta()}: "
                               f"{error}") from error
        finally:
            conexion.close()
            if not listo:
                parcial.unlink(missing_ok=True)
        _podar()
    hecho = {"nombre": nombre, "tipo": TIPOS[tipo], "kb": round(destino.stat().st_size / 1024, 1),
             "fecha": _fecha_de(destino), "tablas": tablas, "filas": filas}
    with bd.transaccion() as cur:
        bitacora.anotar(cur, usuario_id, "respaldo_creado", None, None,
                        {"archivo": nombre, "tipo": hecho["tipo"], "tablas": tablas,
                         "filas": filas, "kb": hecho["kb"]}, ip)
    return hecho


def crear_desde_panel(actor, ip):
    exigir_rol(actor, "admin")
    return crear(None, actor.id, ip)


def para_descargar(actor, nombre, ip):
    """La ruta del respaldo `nombre` (y anota la descarga), o None si no existe.

    Solo nombres con la forma de un respaldo: «../.env» u otro archivo nunca salen."""
    exigir_rol(actor, "admin")
    if not PATRON_NOMBRE.match(nombre or ""):
        return None
    ruta = carpeta() / nombre
    if not ruta.is_file():
        return None
    with bd.transaccion() as cur:
        bitacora.anotar(cur, actor.id, "respaldo_descargado", None, None, {"archivo": nombre}, ip)
    return ruta


# --- Restaurar -----------------------------------------------------------------------------------

def restaurar(ruta, ip=None, respaldo_previo=True):
    """Deja la base como en el respaldo `ruta`. Antes guarda uno «antes de restaurar».

    Devuelve (sentencias, respaldo_previo o None). Solo un respaldo COMPLETO de Titicaca Vivo
    (con su cabecera y su «Fin del respaldo»): uno cortado a la mitad no se restaura.
    """
    ruta = Path(ruta)
    try:
        texto = ruta.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ErrorNegocio(f"No se pudo leer {ruta}: {error}") from error
    if not texto.startswith(CABECERA) or FIN not in texto[-300:]:
        raise ErrorNegocio(f"{ruta.name} no es un respaldo completo de Titicaca Vivo.")
    bd.cerrar_conexion()             # ninguna transacción abierta de esta petición frena los DROP
    previo = crear("antes-de-restaurar", ip=ip) if respaldo_previo else None
    bd.cerrar_conexion()
    sentencias = bd.dividir_sentencias(texto)
    conexion = bd.conectar(current_app.config)
    try:
        with conexion.cursor() as cur:
            for sentencia in sentencias:
                cur.execute(sentencia)          # sin parámetros: el texto del respaldo va tal cual
        conexion.commit()
    finally:
        conexion.close()
    with bd.transaccion() as cur:
        bitacora.anotar(cur, None, "respaldo_restaurado", None, None,
                        {"archivo": ruta.name, "sentencias": len(sentencias),
                         "respaldo_previo": previo["nombre"] if previo else "ninguno"}, ip)
    return len(sentencias), previo


# --- Respaldo automático ------------------------------------------------------------------------

def crear_si_hace_falta():
    """Uno nuevo si el último automático tiene más de RESPALDO_CADA_HORAS horas (o si no hay)."""
    horas = current_app.config["RESPALDO_CADA_HORAS"]
    automaticos = [r for r in listar() if r["tipo"] == TIPOS["auto"]]
    if automaticos and (_ahora() - automaticos[0]["fecha"]).total_seconds() < horas * 3600:
        return None
    return crear("auto", ip="servidor")      # lo llama cada hora el hilo de app/tareas.py


# --- Reporte general para Excel ----------------------------------------------------------------

LEEME = """Titicaca Vivo · Reporte general ({fecha}, hora de Lima)

Cada archivo .csv se abre con Excel: reservas, pagos, salidas y hospedajes.
No lleva números de documento, teléfonos ni correos de los turistas.
Para guardar o recuperar la base COMPLETA se usa un respaldo .sql (Panel → Respaldos).
"""

REPORTE = {
    # Devuelve cada reserva con su salida, su ruta, el titular y cuántos pasajeros tiene.
    "reservas": (
        ["Código", "Estado", "Método de pago", "Total (S/)", "Canal", "Reservada el", "Ruta",
         "Zarpe", "Titular", "País", "Pasajeros"],
        """
        SELECT r.codigo, r.estado, r.metodo_pago_elegido, r.total, r.canal, r.creada_en,
               ru.nombre AS ruta, s.fecha_hora_zarpe,
               CONCAT(t.nombres, ' ', t.apellidos) AS titular, t.nacionalidad,
               (SELECT COUNT(*) FROM reserva_pasajero rp WHERE rp.reserva_id = r.id) AS pasajeros
        FROM reserva r
        JOIN salida s  ON s.id = r.salida_id
        JOIN ruta ru   ON ru.id = s.ruta_id
        JOIN turista t ON t.id = r.turista_id
        ORDER BY r.creada_en, r.id
        """),
    # Devuelve cada pago con su reserva y quién lo verificó (LEFT JOIN: puede no estar verificado).
    "pagos": (
        ["Reserva", "Método", "Monto (S/)", "Estado", "N.º de operación", "Reportado el",
         "Verificado el", "Verificado por", "Observación"],
        """
        SELECT r.codigo, p.metodo, p.monto, p.estado, p.numero_operacion, p.reportado_en,
               p.verificado_en, u.nombre_usuario, p.observacion
        FROM pago p
        JOIN reserva r      ON r.id = p.reserva_id
        LEFT JOIN usuario u ON u.id = p.verificado_por
        ORDER BY p.reportado_en, p.id
        """),
    # Devuelve cada salida con sus cupos (vista v_disponibilidad_salida), su capitán y su guía.
    "salidas": (
        ["Salida", "Ruta", "Zarpe", "Retorno", "Lancha", "Capitán", "Guía", "Cupo", "Ocupados",
         "Libres", "Estado", "Estado público"],
        """
        SELECT v.salida_id, v.ruta_nombre, v.fecha_hora_zarpe, v.fecha_hora_retorno,
               v.embarcacion_nombre, cap.nombre_completo AS capitan, gui.nombre_completo AS guia,
               v.cupo, v.ocupados, v.libres, v.estado, v.estado_publico
        FROM v_disponibilidad_salida v
        JOIN salida s         ON s.id = v.salida_id
        JOIN usuario cap      ON cap.id = s.capitan_id
        LEFT JOIN usuario gui ON gui.id = s.guia_id
        ORDER BY v.fecha_hora_zarpe
        """),
    # Devuelve cada noche de hospedaje con su familia, su comunidad y su reserva.
    "hospedajes": (
        ["Noche", "Comunidad", "Familia", "Reserva", "Personas", "Monto familia (S/)", "Estado",
         "Motivo de reasignación"],
        """
        SELECT h.fecha_noche, c.nombre AS comunidad, f.nombre_familia, r.codigo, h.personas,
               h.monto_familia, h.estado, h.motivo_reasignacion
        FROM hospedaje h
        JOIN familia_anfitriona f ON f.id = h.familia_id
        JOIN comunidad c          ON c.id = f.comunidad_id
        JOIN reserva r            ON r.id = h.reserva_id
        ORDER BY h.fecha_noche, c.nombre, f.nombre_familia
        """),
}


def reporte_general(actor, ip):
    """Las hojas del reporte {nombre: (encabezados, filas)} y su texto LEEME. Queda anotado."""
    exigir_rol(actor, "admin")
    hojas = {}
    for nombre, (encabezados, consulta) in REPORTE.items():
        hojas[nombre] = (encabezados, [list(fila.values()) for fila in bd.consultar(consulta)])
    with bd.transaccion() as cur:
        bitacora.anotar(cur, actor.id, "reporte_general_descargado", None, None,
                        {nombre: len(filas) for nombre, (_, filas) in hojas.items()}, ip)
    return hojas, LEEME.format(fecha=f"{_ahora():%d/%m/%Y %H:%M}")

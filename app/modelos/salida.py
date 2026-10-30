"""Salidas: lo que ve el público (F3) y lo que hace el personal en el panel (F5).

Panel: crear y editar con la regla RN-07, suspender, cancelar, marcar el zarpe y ver
la lista de pasajeros (manifiesto). Los permisos se revisan otra vez aquí (exigir_rol).
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import pymysql

from app import bd
from app.modelos import (
    ERROR_TRIGGER,
    ErrorNegocio,
    ErrorValidacion,
    EstadoNoPermite,
    PermisoDenegado,
    bitacora,
    exigir_rol,
    mensaje_de_la_base,
)

ESTADOS_ACTIVOS = ("programada", "embarcando")       # todavía no zarpa y no se suspendió
ESTADOS_EDITABLES = ("programada", "suspendida")
MINUTOS_ANTES_DEL_ZARPE = 60                          # RN-12: el embarque abre 60 min antes
LARGO_MOTIVO = (5, 255)


def listar_publicas(fecha, ruta_codigo=None):
    # Devuelve las salidas (no canceladas) de un día, con cupos y estado público (vista),
    # y si alguna alerta naranja o roja se cruza con su horario y toca su ruta (RN-11).
    return bd.consultar(
        """
        SELECT v.salida_id, v.fecha_hora_zarpe, v.fecha_hora_retorno, v.ruta_codigo,
               v.ruta_nombre, v.incluye_pernocte, v.embarcacion_nombre, v.cupo, v.ocupados,
               v.libres, v.estado, v.estado_publico,
               EXISTS (SELECT 1
                       FROM alerta_lago a
                       WHERE a.nivel IN ('naranja','rojo')
                         AND a.vigente_desde < v.fecha_hora_retorno
                         AND a.vigente_hasta > v.fecha_hora_zarpe
                         AND (a.comunidad_id IS NULL
                              OR a.comunidad_id IN (SELECT rp.comunidad_id FROM ruta_parada rp
                                                    WHERE rp.ruta_id = v.ruta_id))
               ) AS afectada_por_alerta
        FROM v_disponibilidad_salida v
        WHERE v.fecha_hora_zarpe >= %s
          AND v.fecha_hora_zarpe <  %s + INTERVAL 1 DAY
          AND v.estado <> 'cancelada'
          AND (%s IS NULL OR v.ruta_codigo = %s)
        ORDER BY v.fecha_hora_zarpe, v.ruta_nombre
        """,
        (fecha, fecha, ruta_codigo, ruta_codigo),
    )


def dias_con_salidas(dias=7):
    # Devuelve cada día (desde hoy y durante `dias` días) que tiene salidas no canceladas,
    # con cuántas tiene. GROUP BY junta todas las salidas de un mismo día.
    return bd.consultar(
        """
        SELECT DATE(fecha_hora_zarpe) AS dia, COUNT(*) AS salidas
        FROM salida
        WHERE estado <> 'cancelada'
          AND fecha_hora_zarpe >= CURDATE()
          AND fecha_hora_zarpe <  CURDATE() + INTERVAL %s DAY
        GROUP BY DATE(fecha_hora_zarpe)
        ORDER BY dia
        """,
        (dias,),
    )


def buscar_publica(salida_id):
    # Devuelve una salida con su ruta, su lancha, cupos y estado público, o None si no existe.
    return bd.consultar_uno(
        """
        SELECT v.salida_id, v.fecha_hora_zarpe, v.fecha_hora_retorno, v.estado,
               v.motivo_estado, v.cupo, v.ocupados, v.libres, v.estado_publico,
               v.ruta_id, v.ruta_codigo, v.ruta_nombre, v.incluye_pernocte,
               v.embarcacion_nombre, v.capacidad_maxima,
               r.descripcion AS ruta_descripcion, r.duracion_horas, r.muelle_salida
        FROM v_disponibilidad_salida v
        JOIN ruta r ON r.id = v.ruta_id
        WHERE v.salida_id = %s
        """,
        (salida_id,),
    )


def alertas_que_la_afectan(salida_id):
    # Devuelve las alertas naranja o roja cuyo horario se cruza con el de la salida y que
    # son de todo el lago o de una comunidad de su ruta (RN-11).
    return bd.consultar(
        """
        SELECT a.id, a.tipo, a.nivel, a.titulo, a.descripcion, a.fuente,
               a.vigente_desde, a.vigente_hasta,
               COALESCE(c.nombre, 'Todo el lago') AS lugar
        FROM salida s
        JOIN alerta_lago a ON a.vigente_desde < s.fecha_hora_retorno
                          AND a.vigente_hasta > s.fecha_hora_zarpe
        LEFT JOIN comunidad c ON c.id = a.comunidad_id
        WHERE s.id = %s
          AND a.nivel IN ('naranja','rojo')
          AND (a.comunidad_id IS NULL
               OR a.comunidad_id IN (SELECT rp.comunidad_id FROM ruta_parada rp
                                     WHERE rp.ruta_id = s.ruta_id))
        ORDER BY a.nivel DESC, a.vigente_desde
        """,
        (salida_id,),
    )


# =============================================================================================
# Panel del personal (F5)
# =============================================================================================

@dataclass
class DatosSalida:
    """Lo que el operador escribe en el formulario de una salida."""

    ruta_id: int
    embarcacion_id: int
    capitan_id: int
    guia_id: int | None
    fecha: date
    hora: time
    cupo: int


def es_suya(actor, salida):
    """◐ de la matriz: el guía y el capitán solo ven las salidas que tienen asignadas."""
    if actor.rol in ("admin", "operador"):
        return True
    if actor.rol == "capitan":
        return salida["capitan_id"] == actor.id
    if actor.rol == "guia":
        return salida["guia_id"] == actor.id
    return False


def listar_panel(actor, fecha):
    """Salidas de un día para el operador (y el admin, que solo mira)."""
    exigir_rol(actor, "admin", "operador")
    # Devuelve TODAS las salidas del día (también canceladas y suspendidas) con su ruta, lancha,
    # capitán, guía y cupos. LEFT JOIN con el guía porque una salida puede no tenerlo.
    return bd.consultar(
        """
        SELECT v.salida_id, v.fecha_hora_zarpe, v.fecha_hora_retorno, v.estado, v.motivo_estado,
               v.estado_publico, v.ruta_nombre, v.embarcacion_nombre, v.matricula,
               v.cupo, v.ocupados, v.libres, (v.fecha_hora_zarpe > NOW()) AS aun_no_zarpa,
               cap.nombre_completo AS capitan, gui.nombre_completo AS guia
        FROM v_disponibilidad_salida v
        JOIN salida s         ON s.id = v.salida_id
        JOIN usuario cap      ON cap.id = s.capitan_id
        LEFT JOIN usuario gui ON gui.id = s.guia_id
        WHERE v.fecha_hora_zarpe >= %s
          AND v.fecha_hora_zarpe <  %s + INTERVAL 1 DAY
        ORDER BY v.fecha_hora_zarpe, v.ruta_nombre
        """,
        (fecha, fecha),
    )


def buscar_panel(actor, salida_id):
    """Una salida con todo lo que el personal necesita, o None. Revisa el ◐ del guía y capitán."""
    exigir_rol(actor, "admin", "operador", "guia", "capitan")
    # Devuelve la salida con ruta, lancha (y matrícula), capitán (y licencia), guía (y teléfono),
    # cupos y si ya se puede marcar el zarpe (desde 60 minutos antes de la hora programada).
    fila = bd.consultar_uno(
        """
        SELECT v.salida_id, v.fecha_hora_zarpe, v.fecha_hora_retorno, v.estado, v.motivo_estado,
               v.estado_publico, v.cupo, v.ocupados, v.libres,
               v.ruta_id, v.ruta_codigo, v.ruta_nombre, v.incluye_pernocte,
               v.embarcacion_id, v.embarcacion_nombre, v.matricula, v.capacidad_maxima,
               s.capitan_id, s.guia_id, r.muelle_salida,
               cap.nombre_completo AS capitan, cap.licencia_navegacion,
               gui.nombre_completo AS guia, gui.telefono AS guia_telefono,
               (v.fecha_hora_zarpe > NOW()) AS aun_no_zarpa,
               (NOW() >= v.fecha_hora_zarpe - INTERVAL %s MINUTE) AS ventana_zarpe
        FROM v_disponibilidad_salida v
        JOIN salida s         ON s.id = v.salida_id
        JOIN ruta r           ON r.id = v.ruta_id
        JOIN usuario cap      ON cap.id = s.capitan_id
        LEFT JOIN usuario gui ON gui.id = s.guia_id
        WHERE v.salida_id = %s
        """,
        (MINUTOS_ANTES_DEL_ZARPE, salida_id),
    )
    if fila is not None and not es_suya(actor, fila):
        raise PermisoDenegado("Esta salida no está asignada a este usuario.")
    return fila


def opciones_formulario():
    """Rutas activas, lanchas operativas y personal que puede ir en una salida."""
    # Devuelve las rutas activas con su duración (el retorno se calcula con ella).
    rutas = bd.consultar(
        "SELECT id, codigo, nombre, duracion_horas FROM ruta WHERE activa = 1 ORDER BY nombre")
    # Devuelve las lanchas operativas con su capacidad (RN-07: solo esas pueden salir).
    lanchas = bd.consultar(
        """
        SELECT id, nombre, matricula, capacidad_maxima
        FROM embarcacion
        WHERE estado = 'operativa'
        ORDER BY nombre
        """
    )
    # Devuelve el personal activo que puede ir en una salida: capitanes con licencia y guías.
    personal = bd.consultar(
        """
        SELECT u.id, u.nombre_completo, ro.codigo AS rol
        FROM usuario u
        JOIN rol ro ON ro.id = u.rol_id
        WHERE u.activo = 1
          AND (ro.codigo = 'guia'
               OR (ro.codigo = 'capitan' AND COALESCE(u.licencia_navegacion, '') <> ''))
        ORDER BY u.nombre_completo
        """
    )
    return {
        "rutas": rutas,
        "lanchas": lanchas,
        "capitanes": [p for p in personal if p["rol"] == "capitan"],
        "guias": [p for p in personal if p["rol"] == "guia"],
    }


# --- RN-07 ----------------------------------------------------------------------------------

def contar_ocupados(cur, salida_id):
    """RN-01 con lectura actual (LOCK IN SHARE MODE): pasajeros que ocupan lugar en la salida."""
    # Devuelve cuántos pasajeros ocupan lugar: reservas confirmadas, pagadas, abordadas y
    # pendientes de pago que todavía no vencen.
    cur.execute(
        """
        SELECT COUNT(*) AS ocupados
        FROM reserva_pasajero rp
        JOIN reserva r ON r.id = rp.reserva_id
        WHERE r.salida_id = %s
          AND (r.estado IN ('confirmada','pagada','abordada')
               OR (r.estado = 'pendiente_pago' AND r.vence_en > NOW()))
        LOCK IN SHARE MODE
        """,
        (salida_id,),
    )
    return cur.fetchone()["ocupados"]


def _revisar_personal(cur, usuario_id, rol, errores, campo):
    # Devuelve el usuario con su rol, si está activo y su licencia (para el capitán).
    cur.execute(
        """
        SELECT u.activo, u.licencia_navegacion, ro.codigo AS rol
        FROM usuario u
        JOIN rol ro ON ro.id = u.rol_id
        WHERE u.id = %s
        """,
        (usuario_id,),
    )
    fila = cur.fetchone()
    if fila is None or fila["rol"] != rol or not fila["activo"]:
        errores[campo] = ("Elige un capitán activo." if rol == "capitan"
                          else "Elige un guía activo o deja la salida sin guía.")
    elif rol == "capitan" and not (fila["licencia_navegacion"] or "").strip():
        errores[campo] = "El capitán no tiene licencia de navegación registrada."


def _validar_rn07(cur, datos, salida_actual=None, ocupados=0):
    """RN-07. Devuelve (zarpe, retorno) o lanza ErrorValidacion con todos los errores.

    `salida_actual` es la fila bloqueada cuando se edita (None al crear).
    """
    errores = {}
    salida_id = salida_actual["id"] if salida_actual else 0
    zarpe = datetime.combine(datos.fecha, datos.hora)

    # Devuelve la duración de la ruta (retorno = zarpe + duración) y si está activa.
    cur.execute("SELECT duracion_horas, activa FROM ruta WHERE id = %s", (datos.ruta_id,))
    ruta = cur.fetchone()
    if ruta is None or (salida_actual is None and not ruta["activa"]):
        errores["ruta_id"] = "Elige una ruta activa."
        retorno = zarpe
    else:
        retorno = zarpe + timedelta(minutes=int(ruta["duracion_horas"] * 60))

    # Devuelve la hora actual de la base (hora de Lima, RN-15).
    cur.execute("SELECT NOW() AS ahora")
    if zarpe <= cur.fetchone()["ahora"]:
        errores["hora"] = "El zarpe tiene que ser en el futuro."
    if salida_actual and ocupados and zarpe.date() != salida_actual["fecha_hora_zarpe"].date():
        errores["fecha"] = ("La salida ya tiene reservas: puedes cambiar la hora, pero no el día "
                            "(la noche con la familia y el viaje de los turistas dependen de él).")

    # Devuelve la lancha y la BLOQUEA hasta el COMMIT: dos salidas para la misma lancha
    # se revisan una detrás de otra, así no pueden cruzarse sin que nadie lo vea.
    cur.execute(
        "SELECT capacidad_maxima, estado FROM embarcacion WHERE id = %s FOR UPDATE",
        (datos.embarcacion_id,),
    )
    lancha = cur.fetchone()
    if lancha is None:
        errores["embarcacion_id"] = "Elige una lancha."
    elif lancha["estado"] != "operativa":
        errores["embarcacion_id"] = f"La lancha está en {lancha['estado']}: elige una operativa."
    elif not 1 <= datos.cupo <= lancha["capacidad_maxima"]:
        errores["cupo"] = (f"El cupo va de 1 a {lancha['capacidad_maxima']} "
                           "(capacidad de la lancha).")
    if salida_actual and datos.cupo < ocupados:
        errores["cupo"] = f"Ya hay {ocupados} pasajeros con reserva: el cupo no puede ser menor."

    _revisar_personal(cur, datos.capitan_id, "capitan", errores, "capitan_id")
    if datos.guia_id:
        _revisar_personal(cur, datos.guia_id, "guia", errores, "guia_id")

    # Una salida suspendida no ocupa la lancha (igual que en el trigger): se revisa al reactivarla.
    estado = salida_actual["estado"] if salida_actual else "programada"
    if "embarcacion_id" not in errores and estado != "suspendida":
        # Devuelve otra salida de la misma lancha cuyo horario se cruza con el nuevo.
        # Dos horarios se cruzan si uno empieza antes de que el otro termine, y viceversa.
        cur.execute(
            """
            SELECT s.fecha_hora_zarpe, r.nombre AS ruta
            FROM salida s
            JOIN ruta r ON r.id = s.ruta_id
            WHERE s.embarcacion_id = %s
              AND s.id <> %s
              AND s.estado NOT IN ('cancelada','suspendida')
              AND s.fecha_hora_zarpe < %s
              AND %s < s.fecha_hora_retorno
            ORDER BY s.fecha_hora_zarpe
            LIMIT 1
            """,
            (datos.embarcacion_id, salida_id, retorno, zarpe),
        )
        cruce = cur.fetchone()
        if cruce:
            errores["embarcacion_id"] = (
                f"La lancha ya tiene la salida «{cruce['ruta']}» del "
                f"{cruce['fecha_hora_zarpe']:%d/%m %H:%M} en ese horario.")

    # Una persona no puede ir en dos lanchas a la vez: el capitán y el guía tampoco se cruzan,
    # ni consigo mismos ni entre sí (alguien que es guía de una salida no capitanea otra).
    for campo, usuario_id, quien in (("capitan_id", datos.capitan_id, "El capitán"),
                                     ("guia_id", datos.guia_id, "El guía")):
        if not usuario_id or campo in errores or estado == "suspendida":
            continue
        # Devuelve otra salida de esa persona (como capitán o como guía) que se cruza en horario.
        cur.execute(
            """
            SELECT s.fecha_hora_zarpe, r.nombre AS ruta
            FROM salida s
            JOIN ruta r ON r.id = s.ruta_id
            WHERE (s.capitan_id = %s OR s.guia_id = %s)
              AND s.id <> %s
              AND s.estado NOT IN ('cancelada','suspendida')
              AND s.fecha_hora_zarpe < %s
              AND %s < s.fecha_hora_retorno
            ORDER BY s.fecha_hora_zarpe
            LIMIT 1
            """,
            (usuario_id, usuario_id, salida_id, retorno, zarpe),
        )
        cruce = cur.fetchone()
        if cruce:
            errores[campo] = (f"{quien} ya va en la salida «{cruce['ruta']}» del "
                              f"{cruce['fecha_hora_zarpe']:%d/%m %H:%M}, que se cruza en horario.")

    if errores:
        raise ErrorValidacion(errores)
    return zarpe, retorno


def _ejecutar(cur, sql, parametros):
    """Ejecuta un INSERT o UPDATE de salida. Si el trigger lo frena, muestra su mensaje."""
    try:
        cur.execute(sql, parametros)
    except pymysql.err.OperationalError as error:
        if error.args[0] == ERROR_TRIGGER:
            raise ErrorNegocio(mensaje_de_la_base(error)) from error
        raise


def crear(actor, datos, ip=None):
    """Crea una salida 'programada'. Devuelve su id."""
    exigir_rol(actor, "operador")
    with bd.transaccion(lectura_actual=True) as cur:
        zarpe, retorno = _validar_rn07(cur, datos)
        _ejecutar(
            cur,
            """
            INSERT INTO salida (ruta_id, embarcacion_id, capitan_id, guia_id, fecha_hora_zarpe,
                                fecha_hora_retorno, cupo, estado, creada_por)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'programada', %s)
            """,
            (datos.ruta_id, datos.embarcacion_id, datos.capitan_id, datos.guia_id or None,
             zarpe, retorno, datos.cupo, actor.id),
        )
        salida_id = cur.lastrowid
        bitacora.anotar(cur, actor.id, "creacion", "salida", salida_id,
                        {"ruta_id": datos.ruta_id, "zarpe": zarpe, "cupo": datos.cupo}, ip)
    return salida_id


def _bloquear(cur, salida_id):
    # Devuelve la salida y la BLOQUEA (FOR UPDATE) hasta el COMMIT, con si ya pasó su hora
    # y si ya se abrió la ventana para marcar el zarpe.
    cur.execute(
        """
        SELECT id, ruta_id, embarcacion_id, capitan_id, guia_id, fecha_hora_zarpe, cupo, estado,
               (fecha_hora_zarpe > NOW()) AS aun_no_zarpa,
               (NOW() >= fecha_hora_zarpe - INTERVAL %s MINUTE) AS ventana_zarpe
        FROM salida
        WHERE id = %s
        FOR UPDATE
        """,
        (MINUTOS_ANTES_DEL_ZARPE, salida_id),
    )
    fila = cur.fetchone()
    if fila is None:
        raise EstadoNoPermite("Esa salida no existe.")
    return fila


def editar(actor, salida_id, datos, ip=None):
    """RN-07: no se edita si ya zarpó, y el cupo nuevo no baja de los ocupados.

    Devuelve True si algo cambió.
    """
    exigir_rol(actor, "operador")
    with bd.transaccion(lectura_actual=True) as cur:
        actual = _bloquear(cur, salida_id)
        if actual["estado"] not in ESTADOS_EDITABLES or not actual["aun_no_zarpa"]:
            raise EstadoNoPermite("Esta salida ya zarpó o se canceló: no se puede editar.")
        datos.ruta_id = actual["ruta_id"]      # la ruta no cambia: los precios dependen de ella
        ocupados = contar_ocupados(cur, salida_id)
        zarpe, retorno = _validar_rn07(cur, datos, actual, ocupados)
        _ejecutar(
            cur,
            """
            UPDATE salida
            SET embarcacion_id = %s, capitan_id = %s, guia_id = %s,
                fecha_hora_zarpe = %s, fecha_hora_retorno = %s, cupo = %s
            WHERE id = %s
            """,
            (datos.embarcacion_id, datos.capitan_id, datos.guia_id or None, zarpe, retorno,
             datos.cupo, salida_id),
        )
        nuevos = {"embarcacion_id": datos.embarcacion_id, "capitan_id": datos.capitan_id,
                  "guia_id": datos.guia_id or None, "fecha_hora_zarpe": zarpe, "cupo": datos.cupo}
        cambios = {campo: [actual[campo], valor] for campo, valor in nuevos.items()
                   if actual[campo] != valor}
        if cambios:
            bitacora.anotar(cur, actor.id, "edicion", "salida", salida_id, cambios, ip)
    return bool(cambios)


def _validar_motivo(motivo):
    motivo = " ".join((motivo or "").split())
    minimo, maximo = LARGO_MOTIVO
    if not minimo <= len(motivo) <= maximo:
        raise ErrorValidacion({"motivo": f"Escribe el motivo ({minimo} a {maximo} caracteres)."})
    return motivo


def _cambiar_estado(cur, actor, ip, salida_id, estado, motivo):
    """El trigger trg_salida_au anota el cambio en la bitácora (S-24) con estas variables."""
    cur.execute("SET @app_usuario_id = %s, @app_ip = %s", (actor.id, ip))
    cur.execute("UPDATE salida SET estado = %s, motivo_estado = %s WHERE id = %s",
                (estado, motivo, salida_id))


def suspender(actor, salida_id, motivo, ip=None):
    """Suspende una salida que todavía no zarpa. Sus reservas quedan como están: el turista
    podrá reprogramar o pedir la devolución (RN-11, F6)."""
    exigir_rol(actor, "operador")
    motivo = _validar_motivo(motivo)
    with bd.transaccion(lectura_actual=True) as cur:
        actual = _bloquear(cur, salida_id)
        if actual["estado"] not in ESTADOS_ACTIVOS:
            raise EstadoNoPermite("Solo se suspende una salida que todavía no zarpó.")
        _cambiar_estado(cur, actor, ip, salida_id, "suspendida", motivo)


def cancelar(actor, salida_id, motivo, ip=None):
    """Cancela una salida SIN reservas activas (si tiene, se suspende: D-66)."""
    exigir_rol(actor, "operador")
    motivo = _validar_motivo(motivo)
    with bd.transaccion(lectura_actual=True) as cur:
        actual = _bloquear(cur, salida_id)
        if actual["estado"] not in (*ESTADOS_ACTIVOS, "suspendida"):
            raise EstadoNoPermite("Esta salida ya zarpó o ya estaba cancelada.")
        ocupados = contar_ocupados(cur, salida_id)
        if ocupados:
            raise EstadoNoPermite(
                f"La salida tiene {ocupados} pasajeros con reserva activa: no se puede cancelar. "
                "Suspéndela; así cada turista puede reprogramar o pedir la devolución.")
        _cambiar_estado(cur, actor, ip, salida_id, "cancelada", motivo)


def marcar_zarpe(actor, salida_id, ip=None):
    """El operador o el capitán de la salida marcan el zarpe.

    Devuelve los códigos que quedaron como no_show: reservas sin ningún pasajero a bordo (S-11).
    """
    exigir_rol(actor, "operador", "capitan")
    with bd.transaccion(lectura_actual=True) as cur:
        actual = _bloquear(cur, salida_id)
        if not es_suya(actor, actual):
            raise PermisoDenegado("Solo el capitán de esta salida puede marcar su zarpe.")
        if actual["estado"] not in ESTADOS_ACTIVOS:
            raise EstadoNoPermite("Esta salida no está programada: no se puede marcar el zarpe.")
        if not actual["ventana_zarpe"]:
            raise EstadoNoPermite(f"El zarpe se marca desde {MINUTOS_ANTES_DEL_ZARPE} minutos "
                                  "antes de la hora programada.")
        _cambiar_estado(cur, actor, ip, salida_id, "zarpo", None)

        # Devuelve (y bloquea) las reservas confirmadas o pagadas de la salida que no tienen
        # NINGÚN pasajero a bordo (NOT EXISTS): esas personas no se presentaron.
        cur.execute(
            """
            SELECT r.id, r.codigo, r.estado
            FROM reserva r
            WHERE r.salida_id = %s
              AND r.estado IN ('confirmada','pagada')
              AND NOT EXISTS (SELECT 1
                              FROM reserva_pasajero rp
                              JOIN abordaje a ON a.reserva_pasajero_id = rp.id
                                             AND a.salida_id = r.salida_id
                              WHERE rp.reserva_id = r.id)
            FOR UPDATE
            """,
            (salida_id,),
        )
        ausentes = cur.fetchall()
        for reserva in ausentes:
            cur.execute("UPDATE reserva SET estado = 'no_show' WHERE id = %s", (reserva["id"],))
            bitacora.anotar(cur, actor.id, "cambio_estado", "reserva", reserva["id"],
                            {"de": reserva["estado"], "a": "no_show", "origen": "zarpe"}, ip)
    return [r["codigo"] for r in ausentes]


# --- Lista de pasajeros y manifiesto ---------------------------------------------------------

def pasajeros_de_salida(actor, salida_id):
    """(salida, pasajeros) de las reservas que ocupan lugar, con su abordaje y lo pagado."""
    salida = buscar_panel(actor, salida_id)          # revisa el rol y el ◐ del guía y capitán
    if salida is None:
        return None, []
    # Devuelve cada pasajero de las reservas que ocupan lugar (RN-01) con su tipo, su documento,
    # el titular y su teléfono, si ya abordó (LEFT JOIN: puede no haber abordado todavía) y cuánto
    # se pagó de su reserva (subconsulta que suma los pagos verificados por reserva).
    filas = bd.consultar(
        """
        SELECT r.codigo, r.estado AS estado_reserva, r.metodo_pago_elegido, r.total,
               COALESCE(pv.pagado, 0) AS pagado,
               rp.id AS pasajero_id, rp.nombres, rp.apellidos, rp.tipo_documento,
               rp.numero_documento, rp.nacionalidad, tp.nombre AS tipo,
               t.nombres AS titular_nombres, t.apellidos AS titular_apellidos,
               t.telefono AS titular_telefono,
               a.registrado_en AS abordo_en, a.metodo AS metodo_abordaje
        FROM reserva r
        JOIN reserva_pasajero rp ON rp.reserva_id = r.id
        JOIN tipo_pasajero tp    ON tp.id = rp.tipo_pasajero_id
        JOIN turista t           ON t.id = r.turista_id
        LEFT JOIN abordaje a     ON a.reserva_pasajero_id = rp.id AND a.salida_id = r.salida_id
        LEFT JOIN (SELECT p.reserva_id, SUM(p.monto) AS pagado
                   FROM pago p
                   JOIN reserva r2 ON r2.id = p.reserva_id
                   WHERE r2.salida_id = %s AND p.estado = 'verificado'
                   GROUP BY p.reserva_id) pv ON pv.reserva_id = r.id
        WHERE r.salida_id = %s
          AND (r.estado IN ('confirmada','pagada','abordada')
               OR (r.estado = 'pendiente_pago' AND r.vence_en > NOW()))
        ORDER BY r.codigo, rp.id
        """,
        (salida_id, salida_id),
    )
    return salida, filas

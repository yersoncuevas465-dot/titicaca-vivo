"""Reservas (nivel Oro): crear sin sobreventa, sin duplicados, con el precio como foto.

Reglas: RN-01 (cupos), RN-02 (transacción con FOR UPDATE), RN-03 (token de envío),
RN-04 (precio), RN-05 (pendiente de pago y vencimiento), RN-06 (reporte de pago),
RN-09 (datos) y RN-10 (familia anfitriona al confirmar).
"""

import json
import re
import secrets
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

import pymysql
from flask import current_app

from app import bd
from app.modelos import (
    ERROR_DUPLICADO,
    ERROR_TRIGGER,
    ErrorNegocio,
    ErrorValidacion,
    EstadoNoPermite,
    exigir_rol,
    hospedaje,
    tarifa,
)
from app.servicios import paises

ALFABETO_CODIGO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"     # sin 0, O, 1, I ni L
PATRON_CODIGO = re.compile(r"^TV-[A-HJKMNP-Z2-9]{4}$")
PATRON_TOKEN = re.compile(r"^[0-9a-f]{32}$")
METODOS_PAGO = ("yape", "plin", "muelle")
TIPOS_DOCUMENTO = ("DNI", "CE", "PASAPORTE")
PATRONES_DOCUMENTO = {
    "DNI": (re.compile(r"^\d{8}$"), "El DNI tiene 8 dígitos."),
    "CE": (re.compile(r"^\d{9}$"), "El carné de extranjería tiene 9 dígitos."),
    "PASAPORTE": (re.compile(r"^[A-Z0-9]{6,12}$"),
                  "El pasaporte tiene de 6 a 12 letras o números."),
}
PATRON_TELEFONO = re.compile(r"^(9\d{8}|\+\d{7,15})$")
PATRON_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Letras (con tildes y ñ) separadas por espacio, apóstrofo, punto o guion: "María José", "O'Neill"
PATRON_NOMBRE = re.compile(r"^[^\W\d_]+(?:[ '.\-][^\W\d_]+)*\.?$")
PATRON_OPERACION = re.compile(r"^[A-Za-z0-9-]{4,30}$")


# --- Errores de negocio (la ruta los muestra junto al formulario) ------------------------

class SinCupo(ErrorNegocio):
    pass


class SalidaNoDisponible(ErrorNegocio):
    pass


class DocumentoRepetido(ErrorNegocio):
    pass


class TitularDistinto(ErrorNegocio):
    pass


class _TokenRepetido(Exception):
    """Uso interno: el mismo envío ya creó la reserva (RN-03)."""


# --- Datos que llegan del formulario --------------------------------------------------------

@dataclass
class Persona:
    nombres: str
    apellidos: str
    tipo_documento: str
    numero_documento: str
    nacionalidad: str
    tipo_pasajero_id: int | None = None


@dataclass
class Solicitud:
    salida_id: int
    titular: Persona
    telefono: str | None
    correo: str | None
    titular_viaja: bool
    metodo_pago: str
    acompanantes: list[Persona] = field(default_factory=list)
    idioma: str = "es"
    canal: str = "web"

    def pasajeros(self):
        """D-08: si el titular viaja, es el pasajero 1."""
        return ([self.titular] if self.titular_viaja else []) + list(self.acompanantes)


# --- Validación y limpieza (RN-09) ------------------------------------------------------------

def generar_token():
    return secrets.token_hex(16)


def generar_codigo():
    return "TV-" + "".join(secrets.choice(ALFABETO_CODIGO) for _ in range(4))


def normalizar_codigo(texto):
    return (texto or "").strip().upper()


def normalizar_documento(numero):
    """Quita espacios, puntos y guiones, y pasa a mayúsculas: ' 41.020.304 ' → '41020304'."""
    return re.sub(r"[\s.\-]", "", numero or "").upper()


def _limpiar_texto(texto):
    return " ".join((texto or "").split())


def _sin_tildes(texto):
    """'José  PÉREZ' → 'jose perez' (para comparar nombres sin importar tildes ni mayúsculas)."""
    descompuesto = unicodedata.normalize("NFKD", texto or "")
    sin_marcas = "".join(ch for ch in descompuesto if not unicodedata.combining(ch))
    return " ".join(sin_marcas.lower().split())


def _validar_persona(persona, prefijo, errores):
    persona.nombres = _limpiar_texto(persona.nombres)
    persona.apellidos = _limpiar_texto(persona.apellidos)
    persona.tipo_documento = (persona.tipo_documento or "").upper()
    persona.numero_documento = normalizar_documento(persona.numero_documento)
    persona.nacionalidad = paises.codigo_de(persona.nacionalidad)    # «Perú» o «PE»: «PE»

    for campo, valor in (("nombres", persona.nombres), ("apellidos", persona.apellidos)):
        if not valor:
            errores[f"{prefijo}{campo}"] = "Escribe los " + campo + "."
        elif len(valor) > 80 or not PATRON_NOMBRE.match(valor):
            errores[f"{prefijo}{campo}"] = "Usa solo letras, espacios, apóstrofos o guiones."
    if persona.tipo_documento not in TIPOS_DOCUMENTO:
        errores[f"{prefijo}tipo_documento"] = "Elige DNI, CE o pasaporte."
    else:
        patron, mensaje = PATRONES_DOCUMENTO[persona.tipo_documento]
        if not patron.match(persona.numero_documento):
            errores[f"{prefijo}numero_documento"] = mensaje
    if not paises.es_valido(persona.nacionalidad):
        errores[f"{prefijo}nacionalidad"] = "Elige un país de la lista."


def validar(solicitud):
    """RN-09. Limpia los datos de la solicitud y lanza ErrorValidacion con todos los errores."""
    errores = {}
    _validar_persona(solicitud.titular, "titular_", errores)

    solicitud.telefono = re.sub(r"[\s\-()]", "", solicitud.telefono or "") or None
    solicitud.correo = (solicitud.correo or "").strip().lower() or None
    if solicitud.telefono and not PATRON_TELEFONO.match(solicitud.telefono):
        errores["telefono"] = "Celular peruano de 9 dígitos que empieza en 9, o +código del país."
    correo = solicitud.correo
    if correo and (len(correo) > 120 or not PATRON_CORREO.match(correo)):
        errores["correo"] = "Escribe un correo válido, por ejemplo nombre@correo.com."
    if not solicitud.telefono and not solicitud.correo:
        errores["telefono"] = "Deja al menos un teléfono o un correo para avisarte cambios."

    if solicitud.metodo_pago not in METODOS_PAGO:
        errores["metodo_pago"] = "Elige cómo vas a pagar."
    if solicitud.titular_viaja and not solicitud.titular.tipo_pasajero_id:
        errores["titular_tipo_pasajero_id"] = "Elige tu tipo de pasajero."

    for i, acompanante in enumerate(solicitud.acompanantes):
        _validar_persona(acompanante, f"acompanantes-{i}-", errores)
        if not acompanante.tipo_pasajero_id:
            errores[f"acompanantes-{i}-tipo_pasajero_id"] = "Elige el tipo de pasajero."

    pasajeros = solicitud.pasajeros()
    maximo = current_app.config["MAX_PASAJEROS_POR_RESERVA"]
    if not pasajeros:
        errores["pasajeros"] = "La reserva necesita al menos un pasajero."
    elif len(pasajeros) > maximo:
        errores["pasajeros"] = f"Una reserva lleva como máximo {maximo} pasajeros."

    # RN-09: el mismo documento no puede ir dos veces en la misma reserva
    vistos = {}
    for i, p in enumerate(pasajeros):
        clave = (p.tipo_documento, p.numero_documento)
        if clave in vistos:
            indice = i - (1 if solicitud.titular_viaja else 0)
            errores[f"acompanantes-{indice}-numero_documento"] = (
                "Este documento ya está en la reserva.")
        vistos[clave] = i

    if errores:
        raise ErrorValidacion(errores)


# --- Crear la reserva (RN-02 y RN-03) ----------------------------------------------------------

def crear(solicitud, token, ip=None, usuario_id=None):
    """Crea la reserva en UNA transacción. Devuelve (código, nueva).

    nueva=False significa que ese mismo envío (token) ya había creado la reserva: se
    devuelve la existente en vez de duplicarla (RN-03).
    """
    if not PATRON_TOKEN.match(token or ""):
        raise ErrorValidacion(
            {"token_envio": "El formulario no es válido. Vuelve a cargar la página."})
    validar(solicitud)

    conexion = bd.obtener_conexion()
    # Cerramos cualquier lectura previa de esta petición: la transacción empieza "limpia".
    conexion.rollback()
    with conexion.cursor() as cur:
        # READ COMMITTED: cada SELECT de esta transacción ve lo ÚLTIMO confirmado por otras
        # transacciones. En REPEATABLE READ (lo normal en MariaDB) un SELECT común lee una
        # "foto" tomada en la primera lectura de la transacción: si otra persona confirmó una
        # reserva después de esa foto, no la veríamos y contaríamos cupos de más.
        # Además, los conteos usan LOCK IN SHARE MODE (lectura actual), y la fila de la salida
        # queda bloqueada con FOR UPDATE: dos reservas de la misma salida van una detrás de otra.
        cur.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
    conexion.begin()
    try:
        with conexion.cursor() as cur:
            resultado = _crear_en_transaccion(cur, solicitud, token, ip, usuario_id)
        conexion.commit()
        return resultado
    except _TokenRepetido:
        conexion.rollback()
        return buscar_codigo_por_token(token), False
    except pymysql.err.OperationalError as error:
        conexion.rollback()
        if error.args[0] == ERROR_TRIGGER:            # el trigger frenó la sobreventa
            raise SinCupo("Se acaban de ocupar los últimos lugares. Elige otra salida.") from error
        if error.args[0] in (1205, 1213):            # espera de bloqueo o interbloqueo
            raise ErrorNegocio(
                "Hay muchas reservas al mismo tiempo. Inténtalo de nuevo.") from error
        raise
    except Exception:
        conexion.rollback()
        raise


def _crear_en_transaccion(cur, solicitud, token, ip, usuario_id):
    pasajeros = solicitud.pasajeros()

    # Paso 1 (RN-02): bloquear la fila de la salida hasta el COMMIT.
    # Devuelve la salida; otra transacción que pida FOR UPDATE sobre ella espera aquí.
    cur.execute(
        """
        SELECT id, ruta_id, cupo, estado, fecha_hora_zarpe, fecha_hora_zarpe > NOW() AS aun_no_zarpa
        FROM salida
        WHERE id = %s
        FOR UPDATE
        """,
        (solicitud.salida_id,),
    )
    salida = cur.fetchone()
    if salida is None:
        raise SalidaNoDisponible("Esa salida no existe.")

    # RN-03: ¿este mismo envío ya creó la reserva? (doble clic, botón "atrás", 3 envíos a la vez)
    cur.execute("SELECT codigo FROM reserva WHERE token_envio = %s", (token,))
    if cur.fetchone():
        raise _TokenRepetido()

    if salida["estado"] != "programada" or not salida["aun_no_zarpa"]:
        raise SalidaNoDisponible("Esta salida ya no recibe reservas.")

    # Paso 2 (RN-01): contar los pasajeros que ocupan lugar, con lectura actual.
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
        (salida["id"],),
    )
    libres = max(salida["cupo"] - cur.fetchone()["ocupados"], 0)
    if len(pasajeros) > libres:
        palabra = "lugar" if libres == 1 else "lugares"
        raise SinCupo(f"Solo quedan {libres} {palabra} en esta salida.", campo="pasajeros")

    # RN-09: ningún documento puede viajar dos veces en la misma salida (aunque sea otra reserva).
    # Devuelve los documentos de esta reserva que ya ocupan lugar en la salida.
    marcas = ", ".join(["(%s, %s)"] * len(pasajeros))       # un par (tipo, número) por pasajero
    valores = [v for p in pasajeros for v in (p.tipo_documento, p.numero_documento)]
    cur.execute(
        f"""
        SELECT rp.tipo_documento, rp.numero_documento
        FROM reserva_pasajero rp
        JOIN reserva r ON r.id = rp.reserva_id
        WHERE r.salida_id = %s
          AND (r.estado IN ('confirmada','pagada','abordada')
               OR (r.estado = 'pendiente_pago' AND r.vence_en > NOW()))
          AND (rp.tipo_documento, rp.numero_documento) IN ({marcas})
        LOCK IN SHARE MODE
        """,  # noqa: S608 (solo marcas %s; los valores van como parámetros)
        [salida["id"], *valores],
    )
    repetido = cur.fetchone()
    if repetido:
        raise DocumentoRepetido(
            f"El documento {repetido['tipo_documento']} {repetido['numero_documento']} "
            "ya tiene un lugar en esta salida.")

    turista_id = _guardar_titular(cur, solicitud)

    # RN-04: precio de cada pasajero = tarifa vigente × (1 + recargo de temporada). Es una foto.
    precios = {p["tipo_pasajero_id"]: p["precio"] for p in tarifa.precios_para_salida(salida["id"])}
    for p in pasajeros:
        if p.tipo_pasajero_id not in precios:
            raise ErrorNegocio("Uno de los tipos de pasajero no tiene precio para esta salida.")
    total = sum((precios[p.tipo_pasajero_id] for p in pasajeros), Decimal("0.00"))

    # RN-05: Yape/Plin queda pendiente de pago (vence en N minutos); en el muelle, confirmada.
    estado = "confirmada" if solicitud.metodo_pago == "muelle" else "pendiente_pago"

    # RN-10: si la ruta tiene noche, tiene que haber una familia libre para el grupo.
    comunidad_noche = hospedaje.comunidad_de_pernocte(cur, salida["ruta_id"])
    fecha_noche = salida["fecha_hora_zarpe"].date()
    if comunidad_noche and estado == "pendiente_pago":
        familia = hospedaje.elegir_familia(cur, comunidad_noche, fecha_noche, len(pasajeros))
    else:
        familia = True
    if familia is None:
        raise hospedaje.SinHospedaje(hospedaje.mensaje_sin_familia(len(pasajeros)))

    reserva_id, codigo = _insertar_reserva(cur, solicitud, salida["id"], turista_id, estado,
                                           total, token)

    # Paso 3: los pasajeros (el trigger trg_reserva_pasajero_bi vuelve a revisar el cupo).
    cur.executemany(
        """
        INSERT INTO reserva_pasajero (reserva_id, tipo_pasajero_id, nombres, apellidos,
                                      tipo_documento, numero_documento, nacionalidad,
                                      precio_aplicado)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        [(reserva_id, p.tipo_pasajero_id, p.nombres, p.apellidos, p.tipo_documento,
          p.numero_documento, p.nacionalidad, precios[p.tipo_pasajero_id]) for p in pasajeros],
    )

    if comunidad_noche and estado == "confirmada":
        hospedaje.asignar(cur, reserva_id, comunidad_noche, fecha_noche, len(pasajeros),
                          usuario_id, ip)

    detalle = {"estado": estado, "canal": solicitud.canal, "pasajeros": len(pasajeros),
               "total": str(total), "salida_id": salida["id"]}
    cur.execute(
        """
        INSERT INTO bitacora (usuario_id, accion, tabla_afectada, registro_id, detalle, ip)
        VALUES (%s, 'creacion', 'reserva', %s, %s, %s)
        """,
        (usuario_id, reserva_id, json.dumps(detalle), ip),
    )
    return codigo, True


def _guardar_titular(cur, solicitud):
    """Reutiliza al turista si ya existe (mismo documento y mismo nombre) o lo crea (S-08)."""
    t = solicitud.titular
    # Devuelve el turista con ese documento, bloqueado hasta el COMMIT.
    cur.execute(
        """
        SELECT id, nombres, apellidos FROM turista
        WHERE tipo_documento = %s AND numero_documento = %s
        FOR UPDATE
        """,
        (t.tipo_documento, t.numero_documento),
    )
    fila = cur.fetchone()
    if fila is None:
        try:
            cur.execute(
                """
                INSERT INTO turista (nombres, apellidos, tipo_documento, numero_documento,
                                     nacionalidad, telefono, correo, idioma)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (t.nombres, t.apellidos, t.tipo_documento, t.numero_documento, t.nacionalidad,
                 solicitud.telefono, solicitud.correo, solicitud.idioma),
            )
            return cur.lastrowid
        except pymysql.err.IntegrityError as error:
            # Otra reserva creó a este mismo turista justo ahora: lo volvemos a leer.
            if error.args[0] != ERROR_DUPLICADO:
                raise
            return _guardar_titular(cur, solicitud)

    nombre_guardado = _sin_tildes(fila["nombres"] + " " + fila["apellidos"])
    if nombre_guardado != _sin_tildes(t.nombres + " " + t.apellidos):
        raise TitularDistinto(
            "Ese documento ya está registrado con otro nombre. "
            "Revisa los datos o escribe a la agencia.",
            campo="titular_numero_documento")
    cur.execute(
        """
        UPDATE turista
        SET telefono = COALESCE(%s, telefono), correo = COALESCE(%s, correo), idioma = %s
        WHERE id = %s
        """,
        (solicitud.telefono, solicitud.correo, solicitud.idioma, fila["id"]),
    )
    return fila["id"]


def _insertar_reserva(cur, solicitud, salida_id, turista_id, estado, total, token):
    """Inserta la reserva con un código nuevo. Si el código ya existe (muy raro), prueba otro."""
    minutos = current_app.config["MINUTOS_VENCIMIENTO_PAGO"]
    for _ in range(10):
        codigo = generar_codigo()
        try:
            cur.execute(
                """
                INSERT INTO reserva (codigo, salida_id, turista_id, estado, metodo_pago_elegido,
                                     total, vence_en, token_envio, canal)
                VALUES (%s, %s, %s, %s, %s, %s,
                        CASE WHEN %s = 'pendiente_pago' THEN NOW() + INTERVAL %s MINUTE END,
                        %s, %s)
                """,
                (codigo, salida_id, turista_id, estado, solicitud.metodo_pago, total,
                 estado, minutos, token, solicitud.canal),
            )
            return cur.lastrowid, codigo
        except pymysql.err.IntegrityError as error:
            mensaje = str(error.args[1]) if len(error.args) > 1 else ""
            if error.args[0] == ERROR_DUPLICADO and "uk_reserva_token" in mensaje:
                raise _TokenRepetido() from error
            if error.args[0] == ERROR_DUPLICADO and "uk_reserva_codigo" in mensaje:
                continue
            raise
    raise ErrorNegocio("No pudimos generar el código de la reserva. Inténtalo de nuevo.")


# --- Consultas ---------------------------------------------------------------------------------

def buscar_codigo_por_token(token):
    # Devuelve el código de la reserva que creó ese envío (RN-03).
    fila = bd.consultar_uno("SELECT codigo FROM reserva WHERE token_envio = %s", (token,))
    return fila["codigo"] if fila else None


def buscar_por_codigo(codigo):
    # Devuelve la reserva con su salida, ruta, lancha y titular, más lo pagado (verificado)
    # y lo reportado (sin verificar), o None si el código no existe.
    return bd.consultar_uno(
        """
        SELECT r.id, r.codigo, r.estado, r.metodo_pago_elegido, r.total, r.vence_en, r.canal,
               r.creada_en, (r.vence_en > NOW()) AS vigente,
               s.id AS salida_id, s.fecha_hora_zarpe, s.fecha_hora_retorno,
               s.estado AS salida_estado, s.motivo_estado,
               ru.nombre AS ruta_nombre, ru.muelle_salida, ru.incluye_pernocte,
               e.nombre AS embarcacion_nombre,
               t.nombres, t.apellidos, t.tipo_documento, t.numero_documento, t.telefono, t.correo,
               COALESCE((SELECT SUM(p.monto) FROM pago p
                         WHERE p.reserva_id = r.id AND p.estado = 'verificado'), 0) AS pagado,
               COALESCE((SELECT SUM(p.monto) FROM pago p
                         WHERE p.reserva_id = r.id AND p.estado = 'reportado'), 0) AS reportado
        FROM reserva r
        JOIN salida s      ON s.id = r.salida_id
        JOIN ruta ru       ON ru.id = s.ruta_id
        JOIN embarcacion e ON e.id = s.embarcacion_id
        JOIN turista t     ON t.id = r.turista_id
        WHERE r.codigo = %s
        """,
        (codigo,),
    )


def pasajeros(reserva_id):
    # Devuelve los pasajeros de la reserva con su tipo y el precio que se les aplicó.
    return bd.consultar(
        """
        SELECT rp.id, rp.nombres, rp.apellidos, rp.tipo_documento, rp.numero_documento,
               rp.nacionalidad, rp.precio_aplicado, tp.nombre AS tipo
        FROM reserva_pasajero rp
        JOIN tipo_pasajero tp ON tp.id = rp.tipo_pasajero_id
        WHERE rp.reserva_id = %s
        ORDER BY rp.id
        """,
        (reserva_id,),
    )


def pagos(reserva_id):
    # Devuelve los pagos de la reserva, del más reciente al más antiguo.
    return bd.consultar(
        """
        SELECT p.metodo, p.monto, p.numero_operacion, p.estado, p.reportado_en, p.observacion
        FROM pago p
        WHERE p.reserva_id = %s
        ORDER BY p.reportado_en DESC
        """,
        (reserva_id,),
    )


def hospedajes(reserva_id):
    # Devuelve las noches con familia anfitriona de la reserva (sin datos personales de la familia).
    return bd.consultar(
        """
        SELECT h.fecha_noche, h.personas, h.estado, f.nombre_familia, c.nombre AS comunidad
        FROM hospedaje h
        JOIN familia_anfitriona f ON f.id = h.familia_id
        JOIN comunidad c          ON c.id = f.comunidad_id
        WHERE h.reserva_id = %s AND h.estado <> 'cancelado'
        ORDER BY h.fecha_noche
        """,
        (reserva_id,),
    )


def validar_acceso(codigo, numero_documento):
    """True si el documento es el del titular de esa reserva ("Mi reserva")."""
    # Devuelve una fila si el código existe y el documento es el de su titular.
    fila = bd.consultar_uno(
        """
        SELECT 1 AS ok
        FROM reserva r
        JOIN turista t ON t.id = r.turista_id
        WHERE r.codigo = %s AND t.numero_documento = %s
        """,
        (normalizar_codigo(codigo), normalizar_documento(numero_documento)),
    )
    return fila is not None


# --- Pagos reportados por el turista (RN-06) ---------------------------------------------------

def reportar_pago(codigo, metodo, monto, numero_operacion, ip=None):
    """Registra un pago Yape/Plin como 'reportado'. El operador lo verifica en el panel (F5)."""
    errores = {}
    if metodo not in ("yape", "plin"):
        errores["metodo"] = "Elige Yape o Plin."
    try:
        monto = Decimal(str(monto)).quantize(Decimal("0.01"))
        if monto <= 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        errores["monto"] = "Escribe el monto pagado, por ejemplo 160.00."
        monto = None
    numero_operacion = (numero_operacion or "").strip()
    if not PATRON_OPERACION.match(numero_operacion):
        errores["numero_operacion"] = ("Escribe el número de operación que aparece en tu app "
                                       "(4 a 30 caracteres).")
    if errores:
        raise ErrorValidacion(errores)

    conexion = bd.obtener_conexion()
    conexion.rollback()
    conexion.begin()
    try:
        with conexion.cursor() as cur:
            # Devuelve la reserva bloqueada hasta el COMMIT, con la hora de zarpe de su salida.
            cur.execute(
                """
                SELECT r.id, r.estado, r.total, (r.vence_en > NOW()) AS vigente
                FROM reserva r
                WHERE r.codigo = %s
                FOR UPDATE
                """,
                (codigo,),
            )
            reserva = cur.fetchone()
            if reserva is None:
                raise EstadoNoPermite("Esa reserva no existe.")
            if reserva["estado"] != "pendiente_pago" or not reserva["vigente"]:
                raise EstadoNoPermite("Esta reserva no está esperando un pago (ya venció, se pagó "
                                      "o se paga en el muelle).")
            if monto > reserva["total"]:
                raise ErrorValidacion(
                    {"monto": "El monto no puede ser mayor que el total de la reserva."})
            try:
                cur.execute(
                    """
                    INSERT INTO pago (reserva_id, metodo, monto, numero_operacion, estado)
                    VALUES (%s, %s, %s, %s, 'reportado')
                    """,
                    (reserva["id"], metodo, monto, numero_operacion),
                )
            except pymysql.err.IntegrityError as error:
                if error.args[0] == ERROR_DUPLICADO:
                    raise ErrorValidacion(
                        {"numero_operacion": "Ese número de operación ya fue reportado."}
                    ) from error
                raise
            pago_id = cur.lastrowid
            # D-09 (P2 de la F0): con el pago reportado, el cupo se guarda hasta 60 min antes del
            # zarpe, para que la verificación del operador no le quite el lugar al turista.
            cur.execute(
                """
                UPDATE reserva r
                JOIN salida s ON s.id = r.salida_id
                SET r.vence_en = GREATEST(r.vence_en, s.fecha_hora_zarpe - INTERVAL 60 MINUTE)
                WHERE r.id = %s
                """,
                (reserva["id"],),
            )
            cur.execute(
                """
                INSERT INTO bitacora (usuario_id, accion, tabla_afectada, registro_id, detalle, ip)
                VALUES (NULL, 'pago_reportado', 'pago', %s, %s, %s)
                """,
                (pago_id,
                 json.dumps({"reserva": codigo, "metodo": metodo, "monto": str(monto)}), ip),
            )
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise


# --- Vencimiento (RN-05) -----------------------------------------------------------------------

def vencer_pendientes(origen="flask reservas vencer"):
    """Marca 'vencida' cada pendiente de pago cuyo plazo pasó. Devuelve los códigos.

    La llama el servidor cada 5 minutos (app/tareas.py) y el comando `flask reservas vencer`."""
    conexion = bd.obtener_conexion()
    conexion.rollback()
    conexion.begin()
    try:
        with conexion.cursor() as cur:
            # Devuelve (y bloquea) las reservas pendientes de pago cuyo plazo ya pasó.
            cur.execute(
                """
                SELECT id, codigo FROM reserva
                WHERE estado = 'pendiente_pago' AND vence_en <= NOW()
                FOR UPDATE
                """
            )
            vencidas = cur.fetchall()
            for fila in vencidas:
                cur.execute("UPDATE reserva SET estado = 'vencida' WHERE id = %s", (fila["id"],))
            cur.executemany(
                """
                INSERT INTO bitacora (usuario_id, accion, tabla_afectada, registro_id, detalle, ip)
                VALUES (NULL, 'cambio_estado', 'reserva', %s, %s, NULL)
                """,
                [(f["id"], json.dumps({"de": "pendiente_pago", "a": "vencida",
                                       "origen": origen})) for f in vencidas],
            )
        conexion.commit()
        return [f["codigo"] for f in vencidas]
    except Exception:
        conexion.rollback()
        raise


# --- Reservas en el panel: buscar, recientes e historial (operador y admin) --------------------

def _como_like(texto):
    """'Quispe' → '%Quispe%', con los % y _ que escribió la persona tomados como letras."""
    escapado = texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escapado}%"


def buscar_en_panel(actor, texto):
    """Reservas por código, documento, celular o nombre (del titular o de un pasajero).

    Devuelve hasta 50, las de zarpe más cercano primero. Con menos de 3 letras busca solo por
    código, documento o celular exactos (así una sola letra no trae media base)."""
    exigir_rol(actor, "admin", "operador")
    texto = " ".join((texto or "").split())
    if not texto:
        return []
    exacto = texto.upper()
    nombre = _como_like(texto) if len(texto) >= 3 else None
    # Devuelve las reservas cuyo código, documento o celular coincide, o cuyo titular o algún
    # pasajero se llama así (EXISTS: basta un pasajero). Los valores van como parámetros.
    return bd.consultar(
        """
        SELECT r.codigo, r.estado, (r.vence_en > NOW()) AS vigente, r.total, r.canal,
               r.creada_en, t.nombres, t.apellidos, t.tipo_documento, t.numero_documento,
               s.id AS salida_id, s.fecha_hora_zarpe, ru.nombre AS ruta_nombre
        FROM reserva r
        JOIN turista t ON t.id = r.turista_id
        JOIN salida s  ON s.id = r.salida_id
        JOIN ruta ru   ON ru.id = s.ruta_id
        WHERE r.codigo = %s
           OR t.numero_documento = %s
           OR t.telefono = %s
           OR (%s IS NOT NULL AND CONCAT(t.nombres, ' ', t.apellidos) LIKE %s)
           OR EXISTS (SELECT 1 FROM reserva_pasajero rp
                      WHERE rp.reserva_id = r.id
                        AND (rp.numero_documento = %s
                             OR (%s IS NOT NULL
                                 AND CONCAT(rp.nombres, ' ', rp.apellidos) LIKE %s)))
        ORDER BY ABS(TIMESTAMPDIFF(MINUTE, NOW(), s.fecha_hora_zarpe)), r.id DESC
        LIMIT 50
        """,
        (exacto, exacto, texto, nombre, nombre, exacto, nombre, nombre),
    )


def recientes(actor, cantidad=20):
    """Las últimas reservas registradas (web, muelle o WhatsApp)."""
    exigir_rol(actor, "admin", "operador")
    # Devuelve las reservas más nuevas con su titular y su salida.
    return bd.consultar(
        """
        SELECT r.codigo, r.estado, (r.vence_en > NOW()) AS vigente, r.total, r.canal,
               r.creada_en, t.nombres, t.apellidos, t.tipo_documento, t.numero_documento,
               s.id AS salida_id, s.fecha_hora_zarpe, ru.nombre AS ruta_nombre
        FROM reserva r
        JOIN turista t ON t.id = r.turista_id
        JOIN salida s  ON s.id = r.salida_id
        JOIN ruta ru   ON ru.id = s.ruta_id
        ORDER BY r.creada_en DESC, r.id DESC
        LIMIT %s
        """,
        (cantidad,),
    )


def historial(actor, reserva_id):
    """Todo lo que le pasó a una reserva, en orden: la bitácora de la reserva, de sus pagos y
    de sus noches de hospedaje (quién, cuándo, desde qué IP)."""
    exigir_rol(actor, "admin", "operador")
    # Devuelve la bitácora de la reserva y de sus pagos y hospedajes (índice por tabla y registro).
    filas = bd.consultar(
        """
        SELECT b.creado_en, b.accion, b.tabla_afectada, b.detalle, b.ip, u.nombre_usuario
        FROM bitacora b
        LEFT JOIN usuario u ON u.id = b.usuario_id
        WHERE (b.tabla_afectada = 'reserva' AND b.registro_id = %s)
           OR (b.tabla_afectada = 'pago'
               AND b.registro_id IN (SELECT p.id FROM pago p WHERE p.reserva_id = %s))
           OR (b.tabla_afectada = 'hospedaje'
               AND b.registro_id IN (SELECT h.id FROM hospedaje h WHERE h.reserva_id = %s))
        ORDER BY b.creado_en, b.id
        """,
        (reserva_id, reserva_id, reserva_id),
    )
    for fila in filas:
        fila["detalle"] = json.loads(fila["detalle"]) if fila["detalle"] else {}
    return filas

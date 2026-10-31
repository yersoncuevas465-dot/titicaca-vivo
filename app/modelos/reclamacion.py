"""Libro de reclamaciones virtual (v2.8): Ley N.º 29571 (Código de Protección y Defensa del
Consumidor) y su reglamento.

Cada hoja queda en la bitácora: la app no tiene ninguna opción para editarla ni borrarla, que
es lo que la ley pide de un libro de reclamaciones, y el modelo de datos del enunciado (20
tablas) no cambia. La numeración es correlativa por año (N.º 000001-2026). La respuesta del
operador también va a la bitácora, apuntando a la hoja (tabla_afectada = 'bitacora').
"""

import json
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from app import bd
from app.modelos import ErrorNegocio, ErrorValidacion, EstadoNoPermite, bitacora, exigir_rol
from app.modelos.reserva import (
    PATRON_CODIGO,
    PATRON_CORREO,
    PATRON_NOMBRE,
    PATRON_TELEFONO,
    PATRONES_DOCUMENTO,
    normalizar_codigo,
    normalizar_documento,
)

TIPOS = ("reclamo", "queja")
DIAS_HABILES_PARA_RESPONDER = 15
ACCION, ACCION_RESPUESTA = "reclamacion", "reclamacion_respondida"
CANDADO = "titicaca_libro_reclamaciones"    # dos hojas a la vez no se llevan el mismo número
MONTO_MAXIMO = Decimal("100000")


def _texto(datos, campo, largo, mensaje, errores, una_linea=True):
    """Limpia un texto (en una línea, o con sus saltos de línea) y revisa su largo."""
    texto = (datos.get(campo) or "").strip()
    datos[campo] = " ".join(texto.split()) if una_linea else texto
    if not largo[0] <= len(datos[campo]) <= largo[1]:
        errores[campo] = mensaje


def validar(datos):
    """Limpia la hoja y lanza ErrorValidacion con todos los errores (como la reserva)."""
    errores = {}
    if datos.get("tipo") not in TIPOS:
        errores["tipo"] = "Elige si es un reclamo o una queja."
    for campo in ("nombres", "apellidos"):
        datos[campo] = " ".join((datos.get(campo) or "").split())
        if not datos[campo] or len(datos[campo]) > 80 or not PATRON_NOMBRE.match(datos[campo]):
            errores[campo] = "Usa solo letras, espacios, apóstrofos o guiones."
    datos["numero_documento"] = normalizar_documento(datos.get("numero_documento"))
    patron = PATRONES_DOCUMENTO.get(datos.get("tipo_documento"))
    if patron is None:
        errores["tipo_documento"] = "Elige DNI, CE o pasaporte."
    elif not patron[0].match(datos["numero_documento"]):
        errores["numero_documento"] = patron[1]
    _texto(datos, "domicilio", (5, 200), "Escribe tu domicilio (entre 5 y 200 caracteres).",
           errores)
    datos["correo"] = (datos.get("correo") or "").strip().lower()
    if not PATRON_CORREO.match(datos["correo"]) or len(datos["correo"]) > 120:
        errores["correo"] = "Escribe tu correo: ahí te llega la constancia y la respuesta."
    datos["telefono"] = "".join((datos.get("telefono") or "").split()) or None
    if datos["telefono"] and not PATRON_TELEFONO.match(datos["telefono"]):
        errores["telefono"] = "Celular peruano de 9 dígitos que empieza en 9, o +código del país."
    datos["apoderado"] = " ".join((datos.get("apoderado") or "").split()) or None
    if datos["apoderado"] and len(datos["apoderado"]) > 120:
        errores["apoderado"] = "Máximo 120 caracteres."
    datos["codigo_reserva"] = normalizar_codigo(datos.get("codigo_reserva")) or None
    if datos["codigo_reserva"] and not PATRON_CODIGO.match(datos["codigo_reserva"]):
        errores["codigo_reserva"] = "El código tiene la forma TV-XXXX."
    texto_monto = str(datos.get("monto") or "").strip().replace(",", ".")
    try:
        monto = Decimal(texto_monto).quantize(Decimal("0.01")) if texto_monto else None
        if monto is not None and not Decimal("0") <= monto <= MONTO_MAXIMO:
            raise InvalidOperation
        datos["monto"] = str(monto) if monto is not None else None
    except (InvalidOperation, ValueError):
        errores["monto"] = "Escribe el monto en soles, por ejemplo 160.00."
    _texto(datos, "servicio", (5, 300), "Describe el servicio (entre 5 y 300 caracteres).", errores)
    _texto(datos, "detalle", (20, 2000), "Cuéntanos qué pasó (entre 20 y 2000 caracteres).",
           errores, una_linea=False)
    _texto(datos, "pedido", (5, 1000), "Escribe qué pides (entre 5 y 1000 caracteres).", errores,
           una_linea=False)
    if not datos.get("acepto"):
        errores["acepto"] = "Marca la casilla para confirmar que los datos son verdaderos."
    if errores:
        raise ErrorValidacion(errores)
    return datos


CAMPOS_HOJA = ("tipo", "nombres", "apellidos", "tipo_documento", "numero_documento", "domicilio",
               "correo", "telefono", "apoderado", "codigo_reserva", "monto", "servicio", "detalle",
               "pedido", "idioma")


def registrar(datos, ip):
    """Guarda la hoja en la bitácora con su número correlativo del año. Devuelve el número."""
    validar(datos)
    conexion = bd.obtener_conexion()
    with conexion.cursor() as cur:
        # GET_LOCK: mientras una hoja cuenta y se guarda, otra espera (máximo 10 segundos)
        cur.execute("SELECT GET_LOCK(%s, 10) AS ok", (CANDADO,))
        if not cur.fetchone()["ok"]:
            raise ErrorNegocio("Hay muchas hojas a la vez. Vuelve a enviarla en un momento.")
    try:
        with bd.transaccion() as cur:
            # Devuelve cuántas hojas lleva el año y el año (el número sigue la cuenta).
            cur.execute(
                """
                SELECT COUNT(*) AS hojas, YEAR(NOW()) AS anio
                FROM bitacora
                WHERE accion = 'reclamacion' AND creado_en >= MAKEDATE(YEAR(NOW()), 1)
                """
            )
            fila = cur.fetchone()
            numero = f"{fila['hojas'] + 1:06d}-{fila['anio']}"
            bitacora.anotar(cur, None, ACCION, None, None,
                            {"numero": numero, **{c: datos.get(c) for c in CAMPOS_HOJA}}, ip)
    finally:
        with conexion.cursor() as cur:
            cur.execute("SELECT RELEASE_LOCK(%s)", (CANDADO,))
    return numero


def _armar(fila):
    hoja = json.loads(fila["detalle"])
    hoja.update(id=fila["id"], registrada_en=fila["creado_en"],
                vence_el=vence_el(fila["creado_en"]),
                respuesta=json.loads(fila["respuesta"])["respuesta"] if fila["respuesta"] else None,
                respondida_en=fila["respondida_en"], respondida_por=fila["respondida_por"])
    return hoja


def buscar(numero):
    """La hoja con ese número (y su respuesta, si ya la tiene), o None."""
    # Devuelve la hoja (la fila de la bitácora con ese número) y, con LEFT JOIN, su respuesta.
    fila = bd.consultar_uno(
        """
        SELECT h.id, h.detalle, h.creado_en,
               r.detalle AS respuesta, r.creado_en AS respondida_en,
               u.nombre_usuario AS respondida_por
        FROM bitacora h
        LEFT JOIN bitacora r ON r.accion = 'reclamacion_respondida'
                            AND r.tabla_afectada = 'bitacora' AND r.registro_id = h.id
        LEFT JOIN usuario u  ON u.id = r.usuario_id
        WHERE h.accion = 'reclamacion' AND JSON_VALUE(h.detalle, '$.numero') = %s
        """,
        (numero,),
    )
    return _armar(fila) if fila else None


def listar_panel(actor):
    """Las hojas del libro, de la más nueva a la más antigua, con su respuesta (admin y
    operador)."""
    exigir_rol(actor, "admin", "operador")
    # Devuelve las últimas 200 hojas y, con LEFT JOIN, la respuesta de cada una (si la tiene).
    filas = bd.consultar(
        """
        SELECT h.id, h.detalle, h.creado_en,
               r.detalle AS respuesta, r.creado_en AS respondida_en,
               u.nombre_usuario AS respondida_por
        FROM bitacora h
        LEFT JOIN bitacora r ON r.accion = 'reclamacion_respondida'
                            AND r.tabla_afectada = 'bitacora' AND r.registro_id = h.id
        LEFT JOIN usuario u  ON u.id = r.usuario_id
        WHERE h.accion = 'reclamacion'
        ORDER BY h.id DESC
        LIMIT 200
        """
    )
    return [_armar(f) for f in filas]


def pendientes(actor):
    """Cuántas hojas esperan respuesta (para el resumen del operador)."""
    exigir_rol(actor, "admin", "operador")
    # Devuelve cuántas hojas no tienen todavía una respuesta (NOT EXISTS).
    fila = bd.consultar_uno(
        """
        SELECT COUNT(*) AS pendientes
        FROM bitacora h
        WHERE h.accion = 'reclamacion'
          AND NOT EXISTS (SELECT 1 FROM bitacora r
                          WHERE r.accion = 'reclamacion_respondida'
                            AND r.tabla_afectada = 'bitacora' AND r.registro_id = h.id)
        """
    )
    return fila["pendientes"]


def responder(actor, hoja_id, respuesta, ip):
    """El operador responde una hoja (una sola vez). Devuelve la hoja con su respuesta."""
    exigir_rol(actor, "operador")
    respuesta = (respuesta or "").strip()
    if not 10 <= len(respuesta) <= 2000:
        raise ErrorValidacion({"respuesta": "Escribe la respuesta (entre 10 y 2000 caracteres)."})
    with bd.transaccion(lectura_actual=True) as cur:
        # Devuelve la hoja bloqueada hasta el COMMIT (dos respuestas a la vez: una espera).
        cur.execute(
            "SELECT id, detalle FROM bitacora WHERE id = %s AND accion = 'reclamacion' FOR UPDATE",
            (hoja_id,))
        hoja = cur.fetchone()
        if hoja is None:
            raise EstadoNoPermite("Esa hoja de reclamación no existe.")
        # Devuelve una fila si la hoja ya tiene respuesta.
        cur.execute(
            """
            SELECT 1 AS ya FROM bitacora
            WHERE accion = 'reclamacion_respondida' AND tabla_afectada = 'bitacora'
              AND registro_id = %s
            """,
            (hoja_id,))
        if cur.fetchone():
            raise EstadoNoPermite("Esta hoja ya tiene respuesta.")
        numero = json.loads(hoja["detalle"])["numero"]
        bitacora.anotar(cur, actor.id, ACCION_RESPUESTA, "bitacora", hoja_id,
                        {"numero": numero, "respuesta": respuesta}, ip)
    return buscar(numero)


def vence_el(registrada):
    """La fecha límite para responder: 15 días hábiles (sin sábados ni domingos; los feriados,
    si caen en el plazo, el operador los descuenta)."""
    dia, habiles = registrada.date(), 0
    while habiles < DIAS_HABILES_PARA_RESPONDER:
        dia += timedelta(days=1)
        if dia.weekday() < 5:
            habiles += 1
    return dia

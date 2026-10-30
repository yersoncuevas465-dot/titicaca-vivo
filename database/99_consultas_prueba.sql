-- =====================================================================
-- 99_consultas_prueba.sql · Titicaca Vivo · Evidencia del nivel BRONCE
-- Ejecutar en phpMyAdmin (pestaña SQL, base titicaca_vivo seleccionada),
-- de a una consulta o todas juntas. Solo LEE: no cambia ningún dato.
-- =====================================================================

SET time_zone = '-05:00';

-- ---------------------------------------------------------------------
-- A. Cuántas filas tiene cada tabla (todas >= 5; rol tiene 4 porque el
--    enunciado fija exactamente 4 roles).
-- ---------------------------------------------------------------------
-- Devuelve una fila por tabla con su número de filas.
SELECT 'rol' AS tabla, COUNT(*) AS filas FROM rol
UNION ALL SELECT 'usuario',            COUNT(*) FROM usuario
UNION ALL SELECT 'comunidad',          COUNT(*) FROM comunidad
UNION ALL SELECT 'familia_anfitriona', COUNT(*) FROM familia_anfitriona
UNION ALL SELECT 'embarcacion',        COUNT(*) FROM embarcacion
UNION ALL SELECT 'ruta',               COUNT(*) FROM ruta
UNION ALL SELECT 'ruta_parada',        COUNT(*) FROM ruta_parada
UNION ALL SELECT 'temporada',          COUNT(*) FROM temporada
UNION ALL SELECT 'tipo_pasajero',      COUNT(*) FROM tipo_pasajero
UNION ALL SELECT 'tarifa',             COUNT(*) FROM tarifa
UNION ALL SELECT 'salida',             COUNT(*) FROM salida
UNION ALL SELECT 'turista',            COUNT(*) FROM turista
UNION ALL SELECT 'reserva',            COUNT(*) FROM reserva
UNION ALL SELECT 'reserva_pasajero',   COUNT(*) FROM reserva_pasajero
UNION ALL SELECT 'pago',               COUNT(*) FROM pago
UNION ALL SELECT 'hospedaje',          COUNT(*) FROM hospedaje
UNION ALL SELECT 'abordaje',           COUNT(*) FROM abordaje
UNION ALL SELECT 'alerta_lago',        COUNT(*) FROM alerta_lago
UNION ALL SELECT 'resena',             COUNT(*) FROM resena
UNION ALL SELECT 'bitacora',           COUNT(*) FROM bitacora;

-- ---------------------------------------------------------------------
-- B. SELECT * de cada una de las 20 tablas
-- ---------------------------------------------------------------------
-- Los 4 roles del personal.
SELECT * FROM rol;
-- El personal demo (el hash es bcrypt: la contraseña nunca se guarda).
SELECT * FROM usuario;
-- Las comunidades reales del lago.
SELECT * FROM comunidad;
-- Las familias anfitrionas y su capacidad.
SELECT * FROM familia_anfitriona;
-- Las lanchas: 3 operativas, 1 en mantenimiento y 1 de baja.
SELECT * FROM embarcacion;
-- Las 5 rutas.
SELECT * FROM ruta;
-- Las paradas de cada ruta (relación N:M ruta–comunidad).
SELECT * FROM ruta_parada;
-- Las temporadas con recargo.
SELECT * FROM temporada;
-- Los 5 tipos de pasajero.
SELECT * FROM tipo_pasajero;
-- Las tarifas (2025 como historia y las vigentes).
SELECT * FROM tarifa;
-- Las 14 salidas, de hace 12 días a dentro de 3 días.
SELECT * FROM salida;
-- Los titulares de reserva.
SELECT * FROM turista;
-- Las reservas, en sus 7 estados posibles.
SELECT * FROM reserva;
-- Los pasajeros: cada fila ocupa un cupo.
SELECT * FROM reserva_pasajero;
-- Los pagos: verificados, rechazado, reportado y parciales.
SELECT * FROM pago;
-- Las noches en casa de las familias anfitrionas.
SELECT * FROM hospedaje;
-- Quién abordó y quién lo registró.
SELECT * FROM abordaje;
-- Las alertas del lago (la 1 está vigente).
SELECT * FROM alerta_lago;
-- Las reseñas en sus 3 estados.
SELECT * FROM resena;
-- La bitácora de auditoría.
SELECT * FROM bitacora;

-- ---------------------------------------------------------------------
-- C. Las 2 vistas
-- ---------------------------------------------------------------------
-- Cada salida con sus ocupados, libres y el estado que ve el público (RN-01 y RN-08).
SELECT * FROM v_disponibilidad_salida ORDER BY fecha_hora_zarpe;
-- Ingresos de cada familia por mes: lo cumplido y lo que falta cumplir.
SELECT * FROM v_ingresos_familia ORDER BY mes, comunidad, familia;

-- ---------------------------------------------------------------------
-- D. Cinco consultas con JOIN
-- ---------------------------------------------------------------------

-- D1. Salidas de hoy, mañana y pasado mañana con ruta, lancha, capitán y guía.
--     Devuelve una fila por salida; el guía puede faltar (por eso LEFT JOIN).
SELECT s.id, s.fecha_hora_zarpe, r.nombre AS ruta, e.nombre AS lancha, e.matricula,
       cap.nombre_completo AS capitan, gui.nombre_completo AS guia, s.cupo, s.estado
FROM salida s
JOIN ruta r           ON r.id = s.ruta_id
JOIN embarcacion e    ON e.id = s.embarcacion_id
JOIN usuario cap      ON cap.id = s.capitan_id
LEFT JOIN usuario gui ON gui.id = s.guia_id
WHERE s.fecha_hora_zarpe >= CURDATE()
  AND s.fecha_hora_zarpe <  CURDATE() + INTERVAL 3 DAY
ORDER BY s.fecha_hora_zarpe;

-- D2. Manifiesto de la salida 8 (hoy, 14:00): pasajeros que ocupan lugar con su documento.
--     Devuelve un pasajero por fila, ordenado por código de reserva.
SELECT re.codigo, rp.apellidos, rp.nombres, rp.tipo_documento, rp.numero_documento,
       rp.nacionalidad, tp.nombre AS tipo, rp.precio_aplicado
FROM reserva_pasajero rp
JOIN reserva re       ON re.id = rp.reserva_id
JOIN tipo_pasajero tp ON tp.id = rp.tipo_pasajero_id
WHERE re.salida_id = 8
  AND (re.estado IN ('confirmada','pagada','abordada')
       OR (re.estado = 'pendiente_pago' AND re.vence_en > NOW()))
ORDER BY re.codigo, rp.apellidos;

-- D3. Recorrido de cada ruta: sus paradas en orden, el idioma y dónde se duerme.
--     Devuelve una fila por parada (relación N:M a través de ruta_parada).
SELECT r.codigo, rp.orden, c.nombre AS comunidad, c.idioma_originario,
       rp.minutos_estadia, rp.es_pernocte
FROM ruta r
JOIN ruta_parada rp ON rp.ruta_id = r.id
JOIN comunidad c    ON c.id = rp.comunidad_id
ORDER BY r.codigo, rp.orden;

-- D4. Pagos que el operador todavía debe revisar, con el titular y el total de su reserva.
--     Devuelve los pagos en estado 'reportado'.
SELECT p.id, re.codigo, CONCAT(t.nombres, ' ', t.apellidos) AS titular, p.metodo,
       p.numero_operacion, p.monto, re.total, p.reportado_en
FROM pago p
JOIN reserva re ON re.id = p.reserva_id
JOIN turista t  ON t.id = re.turista_id
WHERE p.estado = 'reportado'
ORDER BY p.reportado_en;

-- D5. Transparencia comunitaria: noches y monto por familia (sin lo cancelado).
--     Devuelve una fila por familia que recibió o recibirá turistas.
SELECT c.nombre AS comunidad, f.nombre_familia,
       COUNT(*) AS noches, SUM(h.personas) AS personas_noche, SUM(h.monto_familia) AS monto
FROM hospedaje h
JOIN familia_anfitriona f ON f.id = h.familia_id
JOIN comunidad c          ON c.id = f.comunidad_id
WHERE h.estado IN ('asignado','cumplido')
GROUP BY c.nombre, f.id, f.nombre_familia
ORDER BY c.nombre, monto DESC;

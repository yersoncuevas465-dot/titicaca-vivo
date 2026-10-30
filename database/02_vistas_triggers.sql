-- =====================================================================
-- 02_vistas_triggers.sql · Titicaca Vivo · Vistas, procedimiento y triggers
-- Importar DESPUÉS de 01_esquema.sql, en la misma base.
--
-- Las reglas de negocio viven en Python (app/modelos). Estos triggers son
-- solo una RED DE SEGURIDAD: si alguien inserta a mano en phpMyAdmin, o si
-- el código tiene un error, la base igual frena la sobreventa y los cruces.
-- Cada trigger avisa con SIGNAL SQLSTATE '45000' y un mensaje claro.
-- =====================================================================

SET NAMES utf8mb4 COLLATE utf8mb4_spanish_ci;
-- Los triggers recuerdan el sql_mode con el que se crearon: los creamos en modo estricto.
SET SESSION sql_mode = 'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ZERO_IN_DATE,NO_ZERO_DATE,NO_ENGINE_SUBSTITUTION';
SET time_zone = '-05:00';

-- ---------------------------------------------------------------------
-- VISTA 1 · v_disponibilidad_salida
-- Devuelve cada salida con su ruta, su lancha, los pasajeros que ocupan
-- lugar (RN-01), los cupos libres y el estado que ve el público (RN-08).
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_disponibilidad_salida AS
SELECT
  s.id                 AS salida_id,
  s.fecha_hora_zarpe,
  s.fecha_hora_retorno,
  s.estado,
  s.motivo_estado,
  s.cupo,
  r.id                 AS ruta_id,
  r.codigo             AS ruta_codigo,
  r.nombre             AS ruta_nombre,
  r.incluye_pernocte,
  e.id                 AS embarcacion_id,
  e.nombre             AS embarcacion_nombre,
  e.matricula,
  e.capacidad_maxima,
  COALESCE(o.ocupados, 0) AS ocupados,
  -- Nunca negativo (RN-01). CAST: cupo es UNSIGNED y restar podría desbordar.
  GREATEST(CAST(s.cupo AS SIGNED) - COALESCE(o.ocupados, 0), 0) AS libres,
  CASE
    WHEN s.estado = 'cancelada' THEN 'cancelada'                       -- no se muestra al público
    WHEN s.estado IN ('zarpo','finalizada') OR s.fecha_hora_zarpe <= NOW() THEN 'zarpo'
    WHEN s.estado = 'suspendida' THEN 'suspendida'
    WHEN COALESCE(o.ocupados, 0) >= s.cupo THEN 'llena'
    WHEN CAST(s.cupo AS SIGNED) - COALESCE(o.ocupados, 0) <= 3 THEN 'pocos_cupos'
    ELSE 'disponible'
  END AS estado_publico
FROM salida s
JOIN ruta r        ON r.id = s.ruta_id
JOIN embarcacion e ON e.id = s.embarcacion_id
-- LEFT JOIN: una salida sin reservas igual debe aparecer (con 0 ocupados)
LEFT JOIN (
  SELECT re.salida_id, COUNT(*) AS ocupados
  FROM reserva re
  JOIN reserva_pasajero rp ON rp.reserva_id = re.id
  WHERE re.estado IN ('confirmada','pagada','abordada')
     OR (re.estado = 'pendiente_pago' AND re.vence_en > NOW())
  GROUP BY re.salida_id
) o ON o.salida_id = s.id;

-- ---------------------------------------------------------------------
-- VISTA 2 · v_ingresos_familia
-- Devuelve, por mes, comunidad y familia: noches y monto ya cumplidos,
-- y aparte lo asignado que aún no se cumple (transparencia comunitaria).
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_ingresos_familia AS
SELECT
  DATE_FORMAT(h.fecha_noche, '%Y-%m') AS mes,
  c.id             AS comunidad_id,
  c.nombre         AS comunidad,
  f.id             AS familia_id,
  f.nombre_familia AS familia,
  SUM(h.estado = 'cumplido')                                         AS noches,
  SUM(CASE WHEN h.estado = 'cumplido' THEN h.personas ELSE 0 END)     AS personas_noche,
  SUM(CASE WHEN h.estado = 'cumplido' THEN h.monto_familia ELSE 0 END) AS monto,
  SUM(h.estado = 'asignado')                                         AS noches_por_cumplir,
  SUM(CASE WHEN h.estado = 'asignado' THEN h.monto_familia ELSE 0 END) AS monto_por_cumplir
FROM hospedaje h
JOIN familia_anfitriona f ON f.id = h.familia_id
JOIN comunidad c          ON c.id = f.comunidad_id
WHERE h.estado IN ('asignado','cumplido')        -- lo cancelado no es ingreso
GROUP BY DATE_FORMAT(h.fecha_noche, '%Y-%m'), c.id, c.nombre, f.id, f.nombre_familia;

-- ---------------------------------------------------------------------
-- Limpieza previa (para poder volver a importar este archivo)
-- ---------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_reserva_pasajero_bi;
DROP TRIGGER IF EXISTS trg_salida_bi;
DROP TRIGGER IF EXISTS trg_salida_bu;
DROP TRIGGER IF EXISTS trg_salida_au;
DROP PROCEDURE IF EXISTS pr_validar_salida;

DELIMITER $$

-- ---------------------------------------------------------------------
-- TRIGGER 1 · antes de insertar un pasajero: frena la sobreventa (RN-02)
-- y el documento repetido en la misma salida (RN-09).
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_reserva_pasajero_bi
BEFORE INSERT ON reserva_pasajero
FOR EACH ROW
BEGIN
  DECLARE v_salida_id INT UNSIGNED;
  DECLARE v_estado    VARCHAR(20);
  DECLARE v_vence     DATETIME;
  DECLARE v_cupo      INT;
  DECLARE v_ocupados  INT;
  DECLARE v_repetidos INT;
  DECLARE v_mensaje   VARCHAR(128);

  SELECT r.salida_id, r.estado, r.vence_en
    INTO v_salida_id, v_estado, v_vence
  FROM reserva r
  WHERE r.id = NEW.reserva_id;

  -- Solo se controla si la reserva ocupa lugar (misma condición que RN-01).
  IF v_estado IN ('confirmada','pagada','abordada')
     OR (v_estado = 'pendiente_pago' AND v_vence > NOW()) THEN

    -- Bloquea la fila de la salida: otra transacción que quiera vender
    -- en esta misma salida espera aquí hasta que esta termine.
    SELECT cupo INTO v_cupo FROM salida WHERE id = v_salida_id FOR UPDATE;

    -- LOCK IN SHARE MODE = lectura actual: ve lo último confirmado, no una foto vieja.
    SELECT COUNT(*) INTO v_ocupados
    FROM reserva_pasajero rp
    JOIN reserva r ON r.id = rp.reserva_id
    WHERE r.salida_id = v_salida_id
      AND (r.estado IN ('confirmada','pagada','abordada')
           OR (r.estado = 'pendiente_pago' AND r.vence_en > NOW()))
    LOCK IN SHARE MODE;

    IF v_ocupados + 1 > v_cupo THEN
      SET v_mensaje = CONCAT('Sobreventa: la salida ', v_salida_id, ' tiene ',
                             GREATEST(v_cupo - v_ocupados, 0), ' cupos libres');
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_mensaje;
    END IF;

    SELECT COUNT(*) INTO v_repetidos
    FROM reserva_pasajero rp
    JOIN reserva r ON r.id = rp.reserva_id
    WHERE r.salida_id = v_salida_id
      AND rp.tipo_documento = NEW.tipo_documento
      AND rp.numero_documento = NEW.numero_documento
      AND (r.estado IN ('confirmada','pagada','abordada')
           OR (r.estado = 'pendiente_pago' AND r.vence_en > NOW()))
    LOCK IN SHARE MODE;

    IF v_repetidos > 0 THEN
      SET v_mensaje = CONCAT('Documento repetido: ', NEW.tipo_documento, ' ',
                             NEW.numero_documento, ' ya tiene lugar en la salida ', v_salida_id);
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_mensaje;
    END IF;
  END IF;
END$$

-- ---------------------------------------------------------------------
-- PROCEDIMIENTO · revisa una salida antes de guardarla (RN-07).
-- Lo usan los dos triggers de abajo (MariaDB no permite un trigger
-- para INSERT y UPDATE a la vez, así la regla se escribe una sola vez).
-- ---------------------------------------------------------------------
CREATE PROCEDURE pr_validar_salida(
  IN p_id INT UNSIGNED, IN p_embarcacion_id INT UNSIGNED, IN p_capitan_id INT UNSIGNED,
  IN p_cupo INT, IN p_zarpe DATETIME, IN p_retorno DATETIME, IN p_estado VARCHAR(20))
BEGIN
  DECLARE v_capacidad INT;
  DECLARE v_es_capitan INT;
  DECLARE v_cruces INT;
  DECLARE v_mensaje VARCHAR(128);

  -- a) El cupo no puede pasar la capacidad de la lancha.
  SELECT capacidad_maxima INTO v_capacidad FROM embarcacion WHERE id = p_embarcacion_id;
  IF p_cupo > v_capacidad THEN
    SET v_mensaje = CONCAT('Cupo ', p_cupo, ' mayor que la capacidad de la lancha (', v_capacidad, ')');
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_mensaje;
  END IF;

  -- b) El capitán tiene rol capitan y licencia de navegación.
  SELECT COUNT(*) INTO v_es_capitan
  FROM usuario u
  JOIN rol ro ON ro.id = u.rol_id
  WHERE u.id = p_capitan_id
    AND ro.codigo = 'capitan'
    AND COALESCE(u.licencia_navegacion, '') <> '';
  IF v_es_capitan = 0 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'El capitán asignado no tiene rol capitan o no tiene licencia de navegación';
  END IF;

  -- c) La misma lancha no puede tener dos salidas que se crucen.
  --    Dos horarios se cruzan si uno empieza antes de que el otro termine, y viceversa.
  --    Las salidas canceladas o suspendidas no cuentan.
  IF p_estado NOT IN ('cancelada','suspendida') THEN
    SELECT COUNT(*) INTO v_cruces
    FROM salida s
    WHERE s.embarcacion_id = p_embarcacion_id
      AND s.id <> p_id
      AND s.estado NOT IN ('cancelada','suspendida')
      AND s.fecha_hora_zarpe < p_retorno
      AND p_zarpe < s.fecha_hora_retorno;
    IF v_cruces > 0 THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Cruce de horario: la lancha ya tiene otra salida en ese horario';
    END IF;
  END IF;
END$$

-- TRIGGER 2 · antes de insertar una salida.
CREATE TRIGGER trg_salida_bi
BEFORE INSERT ON salida
FOR EACH ROW
BEGIN
  -- NEW.id todavía vale 0 (el AUTO_INCREMENT se asigna después): no se excluye a sí misma.
  CALL pr_validar_salida(NEW.id, NEW.embarcacion_id, NEW.capitan_id, NEW.cupo,
                         NEW.fecha_hora_zarpe, NEW.fecha_hora_retorno, NEW.estado);
END$$

-- TRIGGER 3 · antes de actualizar una salida.
-- Solo revisa si cambió algo que afecte la regla (así marcar "finalizada" una
-- salida antigua no falla porque, por ejemplo, la lancha ya se dio de baja).
CREATE TRIGGER trg_salida_bu
BEFORE UPDATE ON salida
FOR EACH ROW
BEGIN
  IF NEW.embarcacion_id <> OLD.embarcacion_id
     OR NEW.capitan_id <> OLD.capitan_id
     OR NEW.cupo <> OLD.cupo
     OR NEW.fecha_hora_zarpe <> OLD.fecha_hora_zarpe
     OR NEW.fecha_hora_retorno <> OLD.fecha_hora_retorno
     OR (OLD.estado IN ('cancelada','suspendida') AND NEW.estado NOT IN ('cancelada','suspendida'))
  THEN
    CALL pr_validar_salida(NEW.id, NEW.embarcacion_id, NEW.capitan_id, NEW.cupo,
                           NEW.fecha_hora_zarpe, NEW.fecha_hora_retorno, NEW.estado);
  END IF;
END$$

-- ---------------------------------------------------------------------
-- TRIGGER 4 · después de actualizar una salida: si cambió el estado,
-- lo anota en la bitácora (RN-14). Quién y desde dónde lo dice la app
-- antes del UPDATE con:  SET @app_usuario_id = ..., @app_ip = ...
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_salida_au
AFTER UPDATE ON salida
FOR EACH ROW
BEGIN
  IF NOT (OLD.estado <=> NEW.estado) THEN
    INSERT INTO bitacora (usuario_id, accion, tabla_afectada, registro_id, detalle, ip)
    VALUES (@app_usuario_id, 'cambio_estado', 'salida', NEW.id,
            JSON_OBJECT('de', OLD.estado, 'a', NEW.estado, 'motivo', NEW.motivo_estado),
            @app_ip);
  END IF;
END$$

DELIMITER ;

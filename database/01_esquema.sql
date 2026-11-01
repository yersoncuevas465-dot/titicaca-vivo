-- =====================================================================
-- 01_esquema.sql · Titicaca Vivo · Las 21 tablas del modelo (la 21, producto, desde la v2.9)
-- MariaDB 10.4+ · InnoDB · utf8mb4 / utf8mb4_spanish_ci
--
-- Cómo importarlo:
--   phpMyAdmin: selecciona la base "titicaca_vivo" > Importar > este archivo.
--   o bien:     flask bd reiniciar   (ejecuta 01, 02 y 03 en orden)
-- Este script NO dice "USE": se aplica a la base que esté seleccionada,
-- así sirve igual para titicaca_vivo y para titicaca_vivo_pruebas.
-- Se puede volver a importar: primero borra todo lo que existía.
-- =====================================================================

SET NAMES utf8mb4 COLLATE utf8mb4_spanish_ci;
-- XAMPP trae un sql_mode NO estricto: un ENUM inválido se guardaría como ''.
-- Con STRICT_TRANS_TABLES, MariaDB rechaza el dato en vez de "arreglarlo".
SET SESSION sql_mode = 'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ZERO_IN_DATE,NO_ZERO_DATE,NO_ENGINE_SUBSTITUTION';
SET time_zone = '-05:00';

SET FOREIGN_KEY_CHECKS = 0;
DROP VIEW IF EXISTS v_disponibilidad_salida, v_ingresos_familia;
DROP TABLE IF EXISTS producto, bitacora, resena, alerta_lago, abordaje, hospedaje, pago,
  reserva_pasajero, reserva, turista, salida, tarifa, tipo_pasajero, temporada,
  ruta_parada, ruta, embarcacion, familia_anfitriona, usuario, comunidad, rol;
SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------
-- CATÁLOGOS Y PERSONAS
-- ---------------------------------------------------------------------

-- 1. rol: los 4 roles del personal (el turista no tiene cuenta).
CREATE TABLE rol (
  id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
  codigo      VARCHAR(20)  NOT NULL,
  nombre      VARCHAR(40)  NOT NULL,
  descripcion VARCHAR(255) NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_rol_codigo (codigo),
  CONSTRAINT ck_rol_codigo CHECK (codigo IN ('admin','operador','guia','capitan','residente'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

-- 3. comunidad (antes comunidad_destino). Va antes que usuario por la FK del guía.
CREATE TABLE comunidad (
  id                INT UNSIGNED NOT NULL AUTO_INCREMENT,
  nombre            VARCHAR(80)  NOT NULL,
  slug              VARCHAR(80)  NOT NULL,
  distrito          VARCHAR(60)  NOT NULL,
  provincia         VARCHAR(60)  NOT NULL,
  idioma_originario ENUM('quechua','aimara') NOT NULL,
  senal             ENUM('buena','debil','sin_senal') NOT NULL,
  whatsapp_contacto VARCHAR(16)  NULL,
  descripcion       TEXT         NULL,
  foto_credito      VARCHAR(200) NULL,           -- P5 (F0): crédito visible de la foto <slug>.webp
  latitud           DECIMAL(9,6) NULL,           -- D-38 (F3): ubicación para el mapa del lago
  longitud          DECIMAL(9,6) NULL,
  tiene_hospedaje   BOOLEAN      NOT NULL DEFAULT 0,
  activa            BOOLEAN      NOT NULL DEFAULT 1,
  PRIMARY KEY (id),
  UNIQUE KEY uk_comunidad_nombre (nombre),
  UNIQUE KEY uk_comunidad_slug (slug),
  -- COLLATE utf8mb4_bin: así el REGEXP distingue mayúsculas (el cotejamiento _ci no lo hace).
  -- Funciona igual en MariaDB y en MySQL 8 (CAST AS BINARY falla en MySQL 8: D-99).
  CONSTRAINT ck_comunidad_slug CHECK (slug COLLATE utf8mb4_bin REGEXP '^[a-z0-9-]+$'),
  CONSTRAINT ck_comunidad_whatsapp CHECK (whatsapp_contacto IS NULL
    OR whatsapp_contacto REGEXP '^(9[0-9]{8}|[+][0-9]{7,15})$'),
  -- Las dos coordenadas van juntas (las dos o ninguna) y dentro de rangos posibles
  CONSTRAINT ck_comunidad_ubicacion CHECK ((latitud IS NULL) = (longitud IS NULL)),
  CONSTRAINT ck_comunidad_latitud CHECK (latitud IS NULL OR latitud BETWEEN -90 AND 90),
  CONSTRAINT ck_comunidad_longitud CHECK (longitud IS NULL OR longitud BETWEEN -180 AND 180)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

-- 2. usuario (antes usuario_sistema): el personal que entra al panel.
CREATE TABLE usuario (
  id                  INT UNSIGNED NOT NULL AUTO_INCREMENT,
  rol_id              INT UNSIGNED NOT NULL,
  nombre_usuario      VARCHAR(30)  NOT NULL,
  nombre_completo     VARCHAR(120) NOT NULL,
  correo              VARCHAR(120) NULL,
  telefono            VARCHAR(16)  NULL,
  hash_contrasena     CHAR(60)     NOT NULL,      -- hash bcrypt, nunca la contraseña
  comunidad_id        INT UNSIGNED NULL,          -- obligatorio para el guía (regla en el modelo)
  licencia_navegacion VARCHAR(30)  NULL,          -- obligatoria para el capitán (modelo + trigger de salida)
  activo              BOOLEAN      NOT NULL DEFAULT 1,
  ultimo_acceso       DATETIME     NULL,
  creado_en           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_usuario_nombre (nombre_usuario),
  UNIQUE KEY uk_usuario_correo (correo),
  KEY ix_usuario_rol (rol_id),
  KEY ix_usuario_comunidad (comunidad_id),
  CONSTRAINT fk_usuario_rol FOREIGN KEY (rol_id) REFERENCES rol (id) ON DELETE RESTRICT,
  CONSTRAINT fk_usuario_comunidad FOREIGN KEY (comunidad_id) REFERENCES comunidad (id) ON DELETE RESTRICT,
  CONSTRAINT ck_usuario_telefono CHECK (telefono IS NULL
    OR telefono REGEXP '^(9[0-9]{8}|[+][0-9]{7,15})$')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

-- 4. familia_anfitriona: familias que reciben turistas en su casa (turismo vivencial).
CREATE TABLE familia_anfitriona (
  id                 INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  comunidad_id       INT UNSIGNED     NOT NULL,
  nombre_familia     VARCHAR(80)      NOT NULL,
  responsable        VARCHAR(120)     NOT NULL,
  telefono           VARCHAR(16)      NULL,
  capacidad_personas TINYINT UNSIGNED NOT NULL,
  servicios          SET('desayuno','almuerzo','cena','vestimenta','taller_textil') NOT NULL DEFAULT '',
  activa             BOOLEAN          NOT NULL DEFAULT 1,
  registrada_en      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY ix_familia_comunidad (comunidad_id),
  CONSTRAINT fk_familia_comunidad FOREIGN KEY (comunidad_id) REFERENCES comunidad (id) ON DELETE RESTRICT,
  CONSTRAINT ck_familia_capacidad CHECK (capacidad_personas BETWEEN 1 AND 10),
  CONSTRAINT ck_familia_telefono CHECK (telefono IS NULL
    OR telefono REGEXP '^(9[0-9]{8}|[+][0-9]{7,15})$')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

-- 5. embarcacion: las lanchas de la agencia.
CREATE TABLE embarcacion (
  id                   INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  nombre               VARCHAR(60)      NOT NULL,
  matricula            VARCHAR(20)      NOT NULL,
  capacidad_maxima     TINYINT UNSIGNED NOT NULL,
  tipo                 ENUM('lancha','deslizador','balsa_totora') NOT NULL,
  estado               ENUM('operativa','mantenimiento','baja') NOT NULL DEFAULT 'operativa',
  ultimo_mantenimiento DATE             NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_embarcacion_matricula (matricula),
  CONSTRAINT ck_embarcacion_capacidad CHECK (capacidad_maxima BETWEEN 1 AND 40)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

-- 6. ruta: los recorridos que vende la agencia.
CREATE TABLE ruta (
  id               INT UNSIGNED NOT NULL AUTO_INCREMENT,
  codigo           VARCHAR(12)  NOT NULL,
  nombre           VARCHAR(100) NOT NULL,
  descripcion      TEXT         NULL,
  duracion_horas   DECIMAL(4,1) NOT NULL,
  incluye_pernocte BOOLEAN      NOT NULL DEFAULT 0,
  muelle_salida    VARCHAR(100) NOT NULL,
  activa           BOOLEAN      NOT NULL DEFAULT 1,
  PRIMARY KEY (id),
  UNIQUE KEY uk_ruta_codigo (codigo),
  CONSTRAINT ck_ruta_duracion CHECK (duracion_horas > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

-- 7. ruta_parada: relación N:M entre ruta y comunidad, con atributos propios.
--    CASCADE: una parada no tiene sentido sin su ruta.
CREATE TABLE ruta_parada (
  id              INT UNSIGNED      NOT NULL AUTO_INCREMENT,
  ruta_id         INT UNSIGNED      NOT NULL,
  comunidad_id    INT UNSIGNED      NOT NULL,
  orden           TINYINT UNSIGNED  NOT NULL,
  minutos_estadia SMALLINT UNSIGNED NOT NULL,
  es_pernocte     BOOLEAN           NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY uk_parada_orden (ruta_id, orden),
  UNIQUE KEY uk_parada_comunidad (ruta_id, comunidad_id),
  KEY ix_parada_comunidad (comunidad_id),
  CONSTRAINT fk_parada_ruta FOREIGN KEY (ruta_id) REFERENCES ruta (id) ON DELETE CASCADE,
  CONSTRAINT fk_parada_comunidad FOREIGN KEY (comunidad_id) REFERENCES comunidad (id) ON DELETE RESTRICT,
  CONSTRAINT ck_parada_orden CHECK (orden >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

-- 8. temporada: recargos por rango de fechas. Se cruza con salida por FECHA, no por FK.
CREATE TABLE temporada (
  id                 INT UNSIGNED NOT NULL AUTO_INCREMENT,
  nombre             VARCHAR(60)  NOT NULL,
  fecha_inicio       DATE         NOT NULL,
  fecha_fin          DATE         NOT NULL,
  recargo_porcentaje DECIMAL(5,2) NOT NULL,
  PRIMARY KEY (id),
  KEY ix_temporada_fechas (fecha_inicio, fecha_fin),
  CONSTRAINT ck_temporada_fechas CHECK (fecha_fin >= fecha_inicio),
  CONSTRAINT ck_temporada_recargo CHECK (recargo_porcentaje BETWEEN 0 AND 100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

-- 9. tipo_pasajero: define qué tarifa paga cada pasajero.
CREATE TABLE tipo_pasajero (
  id          INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  codigo      VARCHAR(20)      NOT NULL,
  nombre      VARCHAR(40)      NOT NULL,
  edad_minima TINYINT UNSIGNED NOT NULL,
  edad_maxima TINYINT UNSIGNED NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_tipo_pasajero_codigo (codigo),
  CONSTRAINT ck_tipo_pasajero_codigo CHECK (codigo IN
    ('adulto_nacional','adulto_extranjero','estudiante','nino','adulto_mayor')),
  CONSTRAINT ck_tipo_pasajero_edades CHECK (edad_maxima IS NULL OR edad_maxima >= edad_minima)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

-- 10. tarifa: precio base por ruta y tipo de pasajero, con vigencia.
CREATE TABLE tarifa (
  id               INT UNSIGNED NOT NULL AUTO_INCREMENT,
  ruta_id          INT UNSIGNED NOT NULL,
  tipo_pasajero_id INT UNSIGNED NOT NULL,
  precio_base      DECIMAL(8,2) NOT NULL,
  vigente_desde    DATE         NOT NULL,
  vigente_hasta    DATE         NULL,                 -- NULL = sin fecha de fin
  PRIMARY KEY (id),
  UNIQUE KEY uk_tarifa_vigencia (ruta_id, tipo_pasajero_id, vigente_desde),
  KEY ix_tarifa_tipo (tipo_pasajero_id),
  CONSTRAINT fk_tarifa_ruta FOREIGN KEY (ruta_id) REFERENCES ruta (id) ON DELETE RESTRICT,
  CONSTRAINT fk_tarifa_tipo FOREIGN KEY (tipo_pasajero_id) REFERENCES tipo_pasajero (id) ON DELETE RESTRICT,
  CONSTRAINT ck_tarifa_precio CHECK (precio_base > 0),
  CONSTRAINT ck_tarifa_vigencia CHECK (vigente_hasta IS NULL OR vigente_hasta >= vigente_desde)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

-- ---------------------------------------------------------------------
-- OPERACIÓN
-- ---------------------------------------------------------------------

-- 11. salida: un viaje concreto (ruta + lancha + capitán + fecha y hora).
CREATE TABLE salida (
  id                 INT UNSIGNED      NOT NULL AUTO_INCREMENT,
  ruta_id            INT UNSIGNED      NOT NULL,
  embarcacion_id     INT UNSIGNED      NOT NULL,
  capitan_id         INT UNSIGNED      NOT NULL,
  guia_id            INT UNSIGNED      NULL,
  fecha_hora_zarpe   DATETIME          NOT NULL,      -- hora de Lima
  fecha_hora_retorno DATETIME          NOT NULL,
  cupo               SMALLINT UNSIGNED NOT NULL,
  estado             ENUM('programada','embarcando','zarpo','finalizada','suspendida','cancelada')
                     NOT NULL DEFAULT 'programada',
  motivo_estado      VARCHAR(255)      NULL,
  creada_por         INT UNSIGNED      NOT NULL,
  creada_en          DATETIME          NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizada_en     DATETIME          NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY ix_salida_zarpe (fecha_hora_zarpe),
  KEY ix_salida_ruta_zarpe (ruta_id, fecha_hora_zarpe),
  KEY ix_salida_embarcacion_zarpe (embarcacion_id, fecha_hora_zarpe),
  KEY ix_salida_capitan (capitan_id),
  KEY ix_salida_guia (guia_id),
  KEY ix_salida_creada_por (creada_por),
  CONSTRAINT fk_salida_ruta FOREIGN KEY (ruta_id) REFERENCES ruta (id) ON DELETE RESTRICT,
  CONSTRAINT fk_salida_embarcacion FOREIGN KEY (embarcacion_id) REFERENCES embarcacion (id) ON DELETE RESTRICT,
  CONSTRAINT fk_salida_capitan FOREIGN KEY (capitan_id) REFERENCES usuario (id) ON DELETE RESTRICT,
  CONSTRAINT fk_salida_guia FOREIGN KEY (guia_id) REFERENCES usuario (id) ON DELETE RESTRICT,
  CONSTRAINT fk_salida_creada_por FOREIGN KEY (creada_por) REFERENCES usuario (id) ON DELETE RESTRICT,
  CONSTRAINT ck_salida_horario CHECK (fecha_hora_retorno > fecha_hora_zarpe),
  CONSTRAINT ck_salida_cupo CHECK (cupo >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

-- 12. turista: el TITULAR de la reserva (los que viajan están en reserva_pasajero).
CREATE TABLE turista (
  id               INT UNSIGNED NOT NULL AUTO_INCREMENT,
  nombres          VARCHAR(80)  NOT NULL,
  apellidos        VARCHAR(80)  NOT NULL,
  tipo_documento   ENUM('DNI','CE','PASAPORTE') NOT NULL,
  numero_documento VARCHAR(12)  NOT NULL,
  nacionalidad     CHAR(2)      NOT NULL,             -- ISO 3166-1 alfa-2: PE, FR, US...
  telefono         VARCHAR(16)  NULL,
  correo           VARCHAR(120) NULL,
  idioma           ENUM('es','en') NOT NULL DEFAULT 'es',
  creado_en        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_turista_documento (tipo_documento, numero_documento),
  CONSTRAINT ck_turista_contacto CHECK (telefono IS NOT NULL OR correo IS NOT NULL),
  CONSTRAINT ck_turista_documento CHECK (
       (tipo_documento = 'DNI' AND numero_documento REGEXP '^[0-9]{8}$')
    OR (tipo_documento = 'CE' AND numero_documento REGEXP '^[0-9]{9}$')
    OR (tipo_documento = 'PASAPORTE' AND numero_documento COLLATE utf8mb4_bin REGEXP '^[A-Z0-9]{6,12}$')),
  CONSTRAINT ck_turista_nacionalidad CHECK (nacionalidad COLLATE utf8mb4_bin REGEXP '^[A-Z]{2}$'),
  CONSTRAINT ck_turista_telefono CHECK (telefono IS NULL
    OR telefono REGEXP '^(9[0-9]{8}|[+][0-9]{7,15})$')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

-- 13. reserva: la acción principal del sistema.
CREATE TABLE reserva (
  id                           INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  -- ascii_bin: el código distingue mayúsculas; el modelo lo guarda siempre en mayúsculas
  codigo                       CHAR(7) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  salida_id                    INT UNSIGNED  NOT NULL,
  turista_id                   INT UNSIGNED  NOT NULL,
  estado                       ENUM('pendiente_pago','confirmada','pagada','abordada',
                                    'cancelada','vencida','no_show') NOT NULL DEFAULT 'pendiente_pago',
  metodo_pago_elegido          ENUM('yape','plin','muelle') NOT NULL,
  total                        DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  vence_en                     DATETIME      NULL,
  token_envio                  CHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  canal                        ENUM('web','whatsapp','mostrador') NOT NULL DEFAULT 'web',
  reprogramada_desde_salida_id INT UNSIGNED  NULL,
  creada_en                    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizada_en               DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_reserva_codigo (codigo),
  UNIQUE KEY uk_reserva_token (token_envio),          -- RN-03: idempotencia (error 1062)
  KEY ix_reserva_salida_estado (salida_id, estado),   -- RN-01: contar ocupados por salida
  KEY ix_reserva_turista (turista_id),
  KEY ix_reserva_vence (vence_en),
  KEY ix_reserva_reprogramada (reprogramada_desde_salida_id),
  CONSTRAINT fk_reserva_salida FOREIGN KEY (salida_id) REFERENCES salida (id) ON DELETE RESTRICT,
  CONSTRAINT fk_reserva_turista FOREIGN KEY (turista_id) REFERENCES turista (id) ON DELETE RESTRICT,
  CONSTRAINT fk_reserva_reprogramada FOREIGN KEY (reprogramada_desde_salida_id)
    REFERENCES salida (id) ON DELETE RESTRICT,
  -- Formato TV-XXXX sin 0, O, 1, I ni L (se confunden al dictarlos por teléfono)
  CONSTRAINT ck_reserva_codigo CHECK (codigo REGEXP '^TV-[A-HJKMNP-Z2-9]{4}$'),
  CONSTRAINT ck_reserva_token CHECK (token_envio REGEXP '^[0-9a-f]{32}$'),
  CONSTRAINT ck_reserva_total CHECK (total >= 0),
  CONSTRAINT ck_reserva_vence CHECK (estado <> 'pendiente_pago' OR vence_en IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

-- 14. reserva_pasajero: cada persona que viaja. Estas filas son las que ocupan cupo.
--     CASCADE: los pasajeros son parte de la reserva.
CREATE TABLE reserva_pasajero (
  id               INT UNSIGNED NOT NULL AUTO_INCREMENT,
  reserva_id       INT UNSIGNED NOT NULL,
  tipo_pasajero_id INT UNSIGNED NOT NULL,
  nombres          VARCHAR(80)  NOT NULL,
  apellidos        VARCHAR(80)  NOT NULL,
  tipo_documento   ENUM('DNI','CE','PASAPORTE') NOT NULL,
  numero_documento VARCHAR(12)  NOT NULL,
  nacionalidad     CHAR(2)      NOT NULL,
  precio_aplicado  DECIMAL(8,2) NOT NULL,              -- RN-04: foto del precio al reservar
  PRIMARY KEY (id),
  UNIQUE KEY uk_pasajero_documento (reserva_id, tipo_documento, numero_documento),
  KEY ix_pasajero_documento (tipo_documento, numero_documento),   -- RN-09: documento por salida
  KEY ix_pasajero_tipo (tipo_pasajero_id),
  CONSTRAINT fk_pasajero_reserva FOREIGN KEY (reserva_id) REFERENCES reserva (id) ON DELETE CASCADE,
  CONSTRAINT fk_pasajero_tipo FOREIGN KEY (tipo_pasajero_id) REFERENCES tipo_pasajero (id) ON DELETE RESTRICT,
  CONSTRAINT ck_pasajero_precio CHECK (precio_aplicado > 0),
  CONSTRAINT ck_pasajero_documento CHECK (
       (tipo_documento = 'DNI' AND numero_documento REGEXP '^[0-9]{8}$')
    OR (tipo_documento = 'CE' AND numero_documento REGEXP '^[0-9]{9}$')
    OR (tipo_documento = 'PASAPORTE' AND numero_documento COLLATE utf8mb4_bin REGEXP '^[A-Z0-9]{6,12}$')),
  CONSTRAINT ck_pasajero_nacionalidad CHECK (nacionalidad COLLATE utf8mb4_bin REGEXP '^[A-Z]{2}$')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

-- 15. pago: lo que el turista reporta (Yape/Plin) o lo que se cobra en el muelle.
CREATE TABLE pago (
  id               INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  reserva_id       INT UNSIGNED  NOT NULL,
  metodo           ENUM('yape','plin','efectivo_muelle','transferencia','pos') NOT NULL,
  monto            DECIMAL(10,2) NOT NULL,
  numero_operacion VARCHAR(30)   NULL,
  estado           ENUM('reportado','verificado','rechazado') NOT NULL DEFAULT 'reportado',
  reportado_en     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  verificado_por   INT UNSIGNED  NULL,
  verificado_en    DATETIME      NULL,
  observacion      VARCHAR(255)  NULL,
  PRIMARY KEY (id),
  -- Un mismo número de operación no se puede usar dos veces. Varios NULL sí (efectivo).
  UNIQUE KEY uk_pago_operacion (metodo, numero_operacion),
  KEY ix_pago_reserva (reserva_id),
  KEY ix_pago_estado (estado),
  KEY ix_pago_verificado_por (verificado_por),
  CONSTRAINT fk_pago_reserva FOREIGN KEY (reserva_id) REFERENCES reserva (id) ON DELETE RESTRICT,
  CONSTRAINT fk_pago_verificado_por FOREIGN KEY (verificado_por) REFERENCES usuario (id) ON DELETE RESTRICT,
  CONSTRAINT ck_pago_monto CHECK (monto > 0),
  CONSTRAINT ck_pago_operacion CHECK (metodo NOT IN ('yape','plin','transferencia')
    OR numero_operacion IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

-- 16. hospedaje: una noche de una reserva en casa de una familia anfitriona.
CREATE TABLE hospedaje (
  id                  INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  reserva_id          INT UNSIGNED     NOT NULL,
  familia_id          INT UNSIGNED     NOT NULL,
  fecha_noche         DATE             NOT NULL,
  personas            TINYINT UNSIGNED NOT NULL,
  monto_familia       DECIMAL(8,2)     NOT NULL,       -- foto: personas × PAGO_FAMILIA_PERSONA_NOCHE
  estado              ENUM('asignado','cumplido','cancelado') NOT NULL DEFAULT 'asignado',
  motivo_reasignacion VARCHAR(255)     NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_hospedaje_noche (reserva_id, fecha_noche),
  KEY ix_hospedaje_familia_noche (familia_id, fecha_noche),       -- RN-10: rotación
  CONSTRAINT fk_hospedaje_reserva FOREIGN KEY (reserva_id) REFERENCES reserva (id) ON DELETE RESTRICT,
  CONSTRAINT fk_hospedaje_familia FOREIGN KEY (familia_id) REFERENCES familia_anfitriona (id) ON DELETE RESTRICT,
  CONSTRAINT ck_hospedaje_personas CHECK (personas BETWEEN 1 AND 10),
  CONSTRAINT ck_hospedaje_monto CHECK (monto_familia >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

-- 17. abordaje: el pasajero subió a la lancha (lo registra el guía, el capitán o el operador).
CREATE TABLE abordaje (
  id                  INT UNSIGNED NOT NULL AUTO_INCREMENT,
  reserva_pasajero_id INT UNSIGNED NOT NULL,
  salida_id           INT UNSIGNED NOT NULL,
  registrado_por      INT UNSIGNED NOT NULL,
  registrado_en       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  metodo              ENUM('qr','manual') NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_abordaje (reserva_pasajero_id, salida_id),        -- RN-12: una sola vez
  KEY ix_abordaje_salida (salida_id),
  KEY ix_abordaje_registrado_por (registrado_por),
  CONSTRAINT fk_abordaje_pasajero FOREIGN KEY (reserva_pasajero_id)
    REFERENCES reserva_pasajero (id) ON DELETE RESTRICT,
  CONSTRAINT fk_abordaje_salida FOREIGN KEY (salida_id) REFERENCES salida (id) ON DELETE RESTRICT,
  CONSTRAINT fk_abordaje_usuario FOREIGN KEY (registrado_por) REFERENCES usuario (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

-- 18. alerta_lago: avisos de clima o seguridad (se registran a mano, sin scraping).
CREATE TABLE alerta_lago (
  id             INT UNSIGNED NOT NULL AUTO_INCREMENT,
  tipo           ENUM('oleaje','tormenta','helada','neblina','granizo','otro') NOT NULL,
  nivel          ENUM('verde','amarillo','naranja','rojo') NOT NULL,
  titulo         VARCHAR(120) NOT NULL,
  descripcion    TEXT         NULL,
  fuente         ENUM('SENAMHI','Capitania','Agencia','Comunidad') NOT NULL,
  comunidad_id   INT UNSIGNED NULL,                   -- NULL = todo el lago
  vigente_desde  DATETIME     NOT NULL,
  vigente_hasta  DATETIME     NOT NULL,
  registrada_por INT UNSIGNED NOT NULL,
  PRIMARY KEY (id),
  KEY ix_alerta_vigencia (vigente_desde, vigente_hasta),
  KEY ix_alerta_comunidad (comunidad_id),
  KEY ix_alerta_registrada_por (registrada_por),
  CONSTRAINT fk_alerta_comunidad FOREIGN KEY (comunidad_id) REFERENCES comunidad (id) ON DELETE RESTRICT,
  CONSTRAINT fk_alerta_usuario FOREIGN KEY (registrada_por) REFERENCES usuario (id) ON DELETE RESTRICT,
  CONSTRAINT ck_alerta_vigencia CHECK (vigente_hasta > vigente_desde)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

-- 19. resena: opinión del turista; se publica después de moderarla.
CREATE TABLE resena (
  id           INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  reserva_id   INT UNSIGNED     NOT NULL,
  puntuacion   TINYINT UNSIGNED NOT NULL,
  comentario   TEXT             NULL,
  idioma       ENUM('es','en')  NOT NULL DEFAULT 'es',
  estado       ENUM('pendiente','publicada','rechazada') NOT NULL DEFAULT 'pendiente',
  moderada_por INT UNSIGNED     NULL,
  creada_en    DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_resena_reserva (reserva_id),          -- una reseña por reserva (1 : 0..1)
  KEY ix_resena_estado (estado),
  KEY ix_resena_moderada_por (moderada_por),
  CONSTRAINT fk_resena_reserva FOREIGN KEY (reserva_id) REFERENCES reserva (id) ON DELETE RESTRICT,
  CONSTRAINT fk_resena_usuario FOREIGN KEY (moderada_por) REFERENCES usuario (id) ON DELETE RESTRICT,
  CONSTRAINT ck_resena_puntuacion CHECK (puntuacion BETWEEN 1 AND 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

-- 20. bitacora: auditoría de cambios de estado e inicios de sesión.
CREATE TABLE bitacora (
  id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  usuario_id     INT UNSIGNED    NULL,                -- NULL: actuó un turista o el sistema
  accion         VARCHAR(50)     NOT NULL,
  tabla_afectada VARCHAR(40)     NULL,
  registro_id    BIGINT UNSIGNED NULL,
  detalle        JSON            NULL,                -- en MariaDB, JSON = LONGTEXT
  ip             VARCHAR(45)     NULL,                -- 45 caracteres alcanzan para IPv6
  creado_en      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY ix_bitacora_registro (tabla_afectada, registro_id),
  KEY ix_bitacora_usuario (usuario_id),
  KEY ix_bitacora_creado (creado_en),
  CONSTRAINT fk_bitacora_usuario FOREIGN KEY (usuario_id) REFERENCES usuario (id) ON DELETE RESTRICT,
  CONSTRAINT ck_bitacora_detalle CHECK (detalle IS NULL OR JSON_VALID(detalle))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

-- 21. producto (v2.9): artesanías y productos que se venden en las islas. Los publica un
--     residente (solo en su comunidad) o la agencia (el operador). El operador puede ocultar
--     cualquiera; quien lo publicó lo retira o lo vuelve a publicar.
CREATE TABLE producto (
  id             INT UNSIGNED NOT NULL AUTO_INCREMENT,
  residente_id   INT UNSIGNED NULL,               -- quién lo publica; NULL: lo ofrece la agencia
  comunidad_id   INT UNSIGNED NULL,               -- dónde está; NULL: en Puno, con la agencia
  nombre         VARCHAR(80)  NOT NULL,
  categoria      ENUM('textil','artesania','alimento','recuerdo') NOT NULL,
  descripcion    VARCHAR(600) NOT NULL,           -- características: material, medidas, colores
  precio         DECIMAL(8,2) NOT NULL,
  lugar          VARCHAR(160) NOT NULL,           -- dónde encontrarlo: tienda, casa, feria...
  foto           VARCHAR(120) NULL,               -- img/productos/... (semilla) o subidas/productos/...
  foto_credito   VARCHAR(160) NULL,               -- autor y licencia, si la foto no es de quien lo vende
  estado         ENUM('publicado','retirado','oculto') NOT NULL DEFAULT 'publicado',
  creado_en      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY ix_producto_residente (residente_id),
  KEY ix_producto_comunidad (comunidad_id),
  KEY ix_producto_estado (estado, creado_en),
  CONSTRAINT fk_producto_residente FOREIGN KEY (residente_id) REFERENCES usuario (id) ON DELETE RESTRICT,
  CONSTRAINT fk_producto_comunidad FOREIGN KEY (comunidad_id) REFERENCES comunidad (id) ON DELETE RESTRICT,
  CONSTRAINT ck_producto_precio CHECK (precio > 0 AND precio <= 10000),
  CONSTRAINT ck_producto_del_residente CHECK (residente_id IS NULL OR comunidad_id IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_spanish_ci;

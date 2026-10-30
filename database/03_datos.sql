-- =====================================================================
-- 03_datos.sql · Titicaca Vivo · Datos de prueba (semilla)
-- Importar DESPUÉS de 01_esquema.sql y 02_vistas_triggers.sql (tablas vacías).
--
-- * Las PERSONAS son ficticias: nombres, documentos, teléfonos (9000000xx),
--   correos (@correo.example, dominio reservado) e IP (203.0.113.x, rango de ejemplo).
-- * Los LUGARES son reales: comunidades, distritos y festividades de Puno.
--   Señal, matrículas, precios y fechas de temporada: "por confirmar".
-- * Las fechas se calculan desde CURDATE(): siempre hay salidas para hoy,
--   mañana y pasado mañana, se importe el día que se importe.
-- * Los precios de los pasajeros NO se escriben a mano: se calculan con la
--   misma regla RN-04 (tarifa vigente × recargo de temporada).
-- =====================================================================

SET NAMES utf8mb4 COLLATE utf8mb4_spanish_ci;
SET SESSION sql_mode = 'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ZERO_IN_DATE,NO_ZERO_DATE,NO_ENGINE_SUBSTITUTION';
SET time_zone = '-05:00';                 -- RN-15: hora de Lima
SET @hoy = CURDATE();                     -- todas las fechas de la semilla parten de aquí

-- ---------------------------------------------------------------------
-- 1. rol (4 filas: el enunciado fija exactamente 4 códigos de rol)
-- ---------------------------------------------------------------------
INSERT INTO rol (id, codigo, nombre, descripcion) VALUES
(1, 'admin',    'Administrador', 'Usuarios, roles, catálogos y bitácora'),
(2, 'operador', 'Operador',      'Toda la operación de la agencia: salidas, pagos, abordaje, alertas y hospedajes'),
(3, 'guia',     'Guía',          'Ve sus salidas asignadas y sus pasajeros; registra el abordaje'),
(4, 'capitan',  'Capitán',       'Ve sus salidas y el manifiesto; registra el abordaje y marca el zarpe');

-- ---------------------------------------------------------------------
-- 3. comunidad (reales; ver docs/fase-0-analisis.md, supuesto S-26)
-- ---------------------------------------------------------------------
INSERT INTO comunidad (id, nombre, slug, distrito, provincia, idioma_originario, senal,
                       whatsapp_contacto, descripcion, foto_credito, latitud, longitud,
                       tiene_hospedaje, activa) VALUES
(1, 'Uros', 'uros', 'Puno', 'Puno', 'aimara', 'buena', '900000111',
 'Islas flotantes construidas con capas de totora, muy cerca del muelle de Puno. Paseos en balsa de totora y bordados.',
 'Foto: Entropy1963 · Dominio público · Wikimedia Commons', -15.817000, -69.968000, 1, 1),
(2, 'Taquile', 'taquile', 'Amantaní', 'Puno', 'quechua', 'debil', '900000112',
 'Isla quechua conocida por su arte textil, reconocido por la UNESCO como Patrimonio Cultural Inmaterial. Caminata a la plaza y almuerzo comunitario.',
 'Foto: Alonso Cárdenas · CC BY-SA 3.0 · Wikimedia Commons', -15.777222, -69.684167, 1, 1),
(3, 'Amantaní', 'amantani', 'Amantaní', 'Puno', 'quechua', 'debil', '900000113',
 'Una de las islas más grandes del lado peruano. Las familias reciben visitantes en sus casas; desde Pachatata y Pachamama se ve el atardecer.',
 'Foto: Pastor3571 · CC BY 4.0 · Wikimedia Commons', -15.664167, -69.710000, 1, 1),
(4, 'Llachón', 'llachon', 'Capachica', 'Puno', 'quechua', 'debil', '900000114',
 'Comunidad de la península de Capachica, pionera del turismo vivencial en el lago: playas, andenes y casas de adobe.',
 'Foto: Hilda Maria FC · CC0 · Wikimedia Commons', -15.722000, -69.745000, 1, 1),
(5, 'Luquina Chico', 'luquina-chico', 'Chucuito', 'Puno', 'aimara', 'debil', '900000115',
 'Comunidad aimara de la península de Chucuito que ofrece turismo vivencial y labores del campo con las familias.',
 'Foto: Murray Foubister · CC BY-SA 2.0 · Wikimedia Commons', -15.805000, -69.850000, 1, 1),
(6, 'Ticonata', 'ticonata', 'Capachica', 'Puno', 'quechua', 'sin_senal', NULL,
 'Pequeña isla frente a la península de Capachica con turismo vivencial a cargo de la comunidad.',
 'Foto: Titico · Dominio público · Wikimedia Commons', -15.648472, -69.787722, 1, 1);
-- Fotos (D-49): miniaturas de Wikimedia Commons convertidas a WebP; créditos en docs/creditos-imagenes.md.
-- Coordenadas (D-38): Amantaní, Taquile y Ticonata según Wikipedia; Uros cerca de Chullune;
-- Llachón y Luquina Chico APROXIMADAS (por confirmar en OpenStreetMap). El mapa es esquemático.

-- ---------------------------------------------------------------------
-- 2. usuario · 6 usuarios demo (admin, operador, 2 guías, 2 capitanes)
-- Las contraseñas están en el README. Este bloque lo escribe
-- scripts/generar_hashes.py: NO lo edites a mano.
-- ---------------------------------------------------------------------
-- [[USUARIOS_INICIO]]
INSERT INTO usuario (id, rol_id, nombre_usuario, nombre_completo, correo, telefono,
                     hash_contrasena, comunidad_id, licencia_navegacion, activo,
                     creado_en) VALUES
(1, 1, 'admin', 'Lucía Mamani Quispe', 'admin@titicaca-vivo.example', '900000101', '$2b$12$/g0Wq7kXa7f60ZECvl3KWugsbZXyy7HvrUAnhw4QSXnDKrSr8YbNy', NULL, NULL, 1, @hoy - INTERVAL 200 DAY),
(2, 2, 'operador', 'Jorge Apaza Huanca', 'operador@titicaca-vivo.example', '900000102', '$2b$12$PYmGmCcZb7x5UswZ95m2/OIihRCs4uwx6aYcW5jbui/gIE4no7dhG', NULL, NULL, 1, @hoy - INTERVAL 200 DAY),
(3, 3, 'guia.elena', 'Elena Yucra Cruz', 'elena.yucra@titicaca-vivo.example', '900000103', '$2b$12$ZPPYwRsLVaYETC51q47Uoec7fi10huPeTV4vkR0lahHtt6w1inJIy', 3, NULL, 1, @hoy - INTERVAL 200 DAY),
(4, 3, 'guia.marco', 'Marco Cutipa Flores', NULL, '900000104', '$2b$12$RLVgv/CShrud4naymJ.H4eYHOagB4FXwEVDrUK/gEWVcyHNVOQ5Mi', 4, NULL, 1, @hoy - INTERVAL 200 DAY),
(5, 4, 'capitan.teodoro', 'Teodoro Choque Pari', NULL, '900000105', '$2b$12$1BskS9.d79w1IHY02/IGiu881DUXmY4zhzEQM9r7LOKzo5oHuvxB6', NULL, 'LIC-PUN-00123', 1, @hoy - INTERVAL 200 DAY),
(6, 4, 'capitan.fermin', 'Fermín Ccama Turpo', NULL, '900000106', '$2b$12$Dk.Q/O56JEa3.qhZpExKF..WuSE0acGyv.2x2tksLcwu7MMqS6bzW', NULL, 'LIC-PUN-00456', 1, @hoy - INTERVAL 200 DAY);
-- [[USUARIOS_FIN]]

-- ---------------------------------------------------------------------
-- 4. familia_anfitriona (personas ficticias, apellidos frecuentes de la zona)
-- ---------------------------------------------------------------------
INSERT INTO familia_anfitriona (id, comunidad_id, nombre_familia, responsable, telefono,
                                capacidad_personas, servicios, activa, registrada_en) VALUES
(1,  3, 'Familia Quispe Cruz',      'Celestino Quispe Cruz',  '900000301', 6, 'desayuno,almuerzo,cena,vestimenta', 1, @hoy - INTERVAL 400 DAY),
(2,  3, 'Familia Mamani Yucra',     'Juana Mamani Yucra',     '900000302', 4, 'desayuno,almuerzo,cena',            1, @hoy - INTERVAL 380 DAY),
(3,  3, 'Familia Huatta Calsin',    'Marcelino Huatta Calsin', '900000303', 5, 'desayuno,cena,taller_textil',      1, @hoy - INTERVAL 300 DAY),
(4,  3, 'Familia Pacompía Ccalla',  'Basilia Pacompía Ccalla', NULL,       8, 'desayuno,almuerzo,cena,vestimenta', 1, @hoy - INTERVAL 120 DAY),
(5,  3, 'Familia Cari Tito',        'Eusebio Cari Tito',      '900000305', 3, 'desayuno,cena',                     0, @hoy - INTERVAL 500 DAY),
(6,  4, 'Familia Cahuana Charca',   'Victoria Cahuana Charca', '900000306', 6, 'desayuno,almuerzo,cena,vestimenta,taller_textil', 1, @hoy - INTERVAL 450 DAY),
(7,  4, 'Familia Flores Mamani',    'Teófilo Flores Mamani',  '900000307', 4, 'desayuno,cena',                     1, @hoy - INTERVAL 200 DAY),
(8,  4, 'Familia Turpo Coila',      'Rufina Turpo Coila',     '900000308', 5, 'desayuno,almuerzo,cena',            1, @hoy - INTERVAL 90 DAY),
(9,  2, 'Familia Huatta Machaca',   'Florentino Huatta Machaca', '900000309', 4, 'desayuno,cena,taller_textil',    1, @hoy - INTERVAL 350 DAY),
(10, 5, 'Familia Choque Ari',       'Hilaria Choque Ari',     '900000310', 6, 'desayuno,almuerzo,cena',            1, @hoy - INTERVAL 150 DAY);

-- ---------------------------------------------------------------------
-- 5. embarcacion: 3 lanchas operativas (las que hacen las salidas) y
--    2 más para mostrar los estados "mantenimiento" y "baja".
--    Matrículas ficticias (formato por confirmar con la Capitanía).
-- ---------------------------------------------------------------------
INSERT INTO embarcacion (id, nombre, matricula, capacidad_maxima, tipo, estado, ultimo_mantenimiento) VALUES
(1, 'Qhapaq Qocha', 'PUN-LT-0101', 30, 'lancha',     'operativa',     @hoy - INTERVAL 40 DAY),
(2, 'Mama Qota',    'PUN-LT-0102', 24, 'lancha',     'operativa',     @hoy - INTERVAL 25 DAY),
(3, 'Wiñay Inti',   'PUN-LT-0103', 20, 'lancha',     'operativa',     @hoy - INTERVAL 60 DAY),
(4, 'Kantuta',      'PUN-DZ-0201', 12, 'deslizador', 'mantenimiento', @hoy - INTERVAL 2 DAY),
(5, 'Totorita',     'PUN-LT-0099', 18, 'lancha',     'baja',          '2024-03-10');

-- ---------------------------------------------------------------------
-- 6. ruta (las 4 del enunciado + Uros y Luquina Chico)
-- ---------------------------------------------------------------------
INSERT INTO ruta (id, codigo, nombre, descripcion, duracion_horas, incluye_pernocte, muelle_salida, activa) VALUES
(1, 'URO-MD',      'Islas flotantes de los Uros',  'Medio día en las islas flotantes de totora.', 3.0, 0, 'Muelle de Puno', 1),
(2, 'URO-TAQ',     'Uros y Taquile',               'Día completo: Uros por la mañana y Taquile con almuerzo comunitario.', 9.5, 0, 'Muelle de Puno', 1),
(3, 'URO-AMA-TAQ', 'Uros, Amantaní y Taquile',     '2 días y 1 noche: Uros, noche con una familia de Amantaní y Taquile al volver.', 33.0, 1, 'Muelle de Puno', 1),
(4, 'LLA-VIV',     'Llachón vivencial',            '2 días y 1 noche en Llachón, con parada en los Uros (itinerario por confirmar con la agencia).', 31.5, 1, 'Muelle de Puno', 1),
(5, 'URO-LUQ',     'Uros y Luquina Chico',         'Día completo: Uros y la comunidad aimara de Luquina Chico.', 8.0, 0, 'Muelle de Puno', 1);

-- ---------------------------------------------------------------------
-- 7. ruta_parada (orden de visita; es_pernocte = dónde se duerme)
-- ---------------------------------------------------------------------
INSERT INTO ruta_parada (ruta_id, comunidad_id, orden, minutos_estadia, es_pernocte) VALUES
(1, 1, 1,   90, 0),
(2, 1, 1,   60, 0), (2, 2, 2,  180, 0),
(3, 1, 1,   60, 0), (3, 3, 2, 1080, 1), (3, 2, 3, 180, 0),
(4, 1, 1,   45, 0), (4, 4, 2, 1200, 1),
(5, 1, 1,   60, 0), (5, 5, 2,  240, 0);

-- ---------------------------------------------------------------------
-- 8. temporada (fechas por confirmar cada año; no se solapan)
-- ---------------------------------------------------------------------
INSERT INTO temporada (nombre, fecha_inicio, fecha_fin, recargo_porcentaje) VALUES
('Temporada alta 2026',        '2026-06-15', '2026-08-31', 15.00),
('Semana Jubilar de Puno 2026', '2026-11-01', '2026-11-07', 10.00),
('Fiestas de fin de año',      '2026-12-24', '2027-01-02', 10.00),
('Virgen de la Candelaria 2027', '2027-02-01', '2027-02-15', 20.00),
('Semana Santa 2027',          '2027-03-25', '2027-03-28', 10.00),
('Temporada alta 2027',        '2027-06-15', '2027-08-31', 15.00);

-- ---------------------------------------------------------------------
-- 9. tipo_pasajero (edades informativas: se verifican con el documento)
-- ---------------------------------------------------------------------
INSERT INTO tipo_pasajero (id, codigo, nombre, edad_minima, edad_maxima) VALUES
(1, 'adulto_nacional',   'Adulto nacional',   18, NULL),
(2, 'adulto_extranjero', 'Adulto extranjero', 18, NULL),
(3, 'estudiante',        'Estudiante (con carné)', 12, 30),
(4, 'nino',              'Niño o niña',        3, 11),
(5, 'adulto_mayor',      'Adulto mayor',      60, NULL);

-- ---------------------------------------------------------------------
-- 10. tarifa (soles; precios de ejemplo por confirmar con Giant Trip)
--     Uros y Uros+Taquile guardan su tarifa 2025 como historia.
-- ---------------------------------------------------------------------
INSERT INTO tarifa (ruta_id, tipo_pasajero_id, precio_base, vigente_desde, vigente_hasta) VALUES
-- historia 2025
(1, 1,  25.00, '2025-01-01', '2025-12-31'), (1, 2,  40.00, '2025-01-01', '2025-12-31'),
(1, 3,  18.00, '2025-01-01', '2025-12-31'), (1, 4,  12.00, '2025-01-01', '2025-12-31'),
(1, 5,  18.00, '2025-01-01', '2025-12-31'),
(2, 1,  70.00, '2025-01-01', '2025-12-31'), (2, 2, 110.00, '2025-01-01', '2025-12-31'),
(2, 3,  55.00, '2025-01-01', '2025-12-31'), (2, 4,  35.00, '2025-01-01', '2025-12-31'),
(2, 5,  55.00, '2025-01-01', '2025-12-31'),
-- vigentes (sin fecha de fin)
(1, 1,  30.00, '2026-01-01', NULL), (1, 2,  45.00, '2026-01-01', NULL), (1, 3,  20.00, '2026-01-01', NULL),
(1, 4,  15.00, '2026-01-01', NULL), (1, 5,  20.00, '2026-01-01', NULL),
(2, 1,  80.00, '2026-01-01', NULL), (2, 2, 120.00, '2026-01-01', NULL), (2, 3,  60.00, '2026-01-01', NULL),
(2, 4,  40.00, '2026-01-01', NULL), (2, 5,  60.00, '2026-01-01', NULL),
(3, 1, 150.00, '2025-07-01', NULL), (3, 2, 220.00, '2025-07-01', NULL), (3, 3, 120.00, '2025-07-01', NULL),
(3, 4,  80.00, '2025-07-01', NULL), (3, 5, 120.00, '2025-07-01', NULL),
(4, 1, 140.00, '2025-07-01', NULL), (4, 2, 200.00, '2025-07-01', NULL), (4, 3, 110.00, '2025-07-01', NULL),
(4, 4,  70.00, '2025-07-01', NULL), (4, 5, 110.00, '2025-07-01', NULL),
(5, 1,  90.00, '2025-07-01', NULL), (5, 2, 130.00, '2025-07-01', NULL), (5, 3,  70.00, '2025-07-01', NULL),
(5, 4,  45.00, '2025-07-01', NULL), (5, 5,  70.00, '2025-07-01', NULL);

-- ---------------------------------------------------------------------
-- 11. salida · 14 salidas: 4 pasadas, 1 cancelada (ayer), 3 de HOY,
--     3 de MAÑANA (una suspendida por alerta), 2 de PASADO MAÑANA y 1 más.
--     Los triggers revisan cupo <= capacidad, capitán y cruces de lancha.
-- ---------------------------------------------------------------------
INSERT INTO salida (id, ruta_id, embarcacion_id, capitan_id, guia_id, fecha_hora_zarpe, fecha_hora_retorno,
                    cupo, estado, motivo_estado, creada_por, creada_en) VALUES
(1,  4, 3, 6, 4,    TIMESTAMP(@hoy - INTERVAL 12 DAY, '07:30'), TIMESTAMP(@hoy - INTERVAL 11 DAY, '15:00'), 16, 'finalizada', NULL, 2, @hoy - INTERVAL 30 DAY),
(2,  2, 1, 5, 3,    TIMESTAMP(@hoy - INTERVAL 7 DAY, '07:00'),  TIMESTAMP(@hoy - INTERVAL 7 DAY, '16:30'),  25, 'finalizada', NULL, 2, @hoy - INTERVAL 25 DAY),
(3,  3, 2, 6, 3,    TIMESTAMP(@hoy - INTERVAL 6 DAY, '07:00'),  TIMESTAMP(@hoy - INTERVAL 5 DAY, '16:00'),  20, 'finalizada', NULL, 2, @hoy - INTERVAL 25 DAY),
(4,  1, 3, 5, NULL, TIMESTAMP(@hoy - INTERVAL 2 DAY, '09:00'),  TIMESTAMP(@hoy - INTERVAL 2 DAY, '12:00'),  18, 'finalizada', NULL, 2, @hoy - INTERVAL 10 DAY),
(5,  2, 2, 5, 4,    TIMESTAMP(@hoy - INTERVAL 1 DAY, '07:00'),  TIMESTAMP(@hoy - INTERVAL 1 DAY, '16:30'),  20, 'cancelada',
     'Falla del motor: la lancha pasó a revisión', 2, @hoy - INTERVAL 10 DAY),
(6,  2, 1, 6, 3,    TIMESTAMP(@hoy, '07:00'), TIMESTAMP(@hoy, '16:30'), 25, 'programada', NULL, 2, @hoy - INTERVAL 7 DAY),
(7,  1, 3, 5, NULL, TIMESTAMP(@hoy, '08:00'), TIMESTAMP(@hoy, '11:00'), 18, 'programada', NULL, 2, @hoy - INTERVAL 7 DAY),
(8,  1, 3, 5, NULL, TIMESTAMP(@hoy, '14:00'), TIMESTAMP(@hoy, '17:00'), 18, 'programada', NULL, 2, @hoy - INTERVAL 7 DAY),
(9,  3, 2, 6, 3,    TIMESTAMP(@hoy + INTERVAL 1 DAY, '07:00'),  TIMESTAMP(@hoy + INTERVAL 2 DAY, '16:00'),  20, 'suspendida',
     'Alerta naranja de oleaje en Amantaní (SENAMHI)', 2, @hoy - INTERVAL 7 DAY),
(10, 2, 1, 5, 4,    TIMESTAMP(@hoy + INTERVAL 1 DAY, '07:00'),  TIMESTAMP(@hoy + INTERVAL 1 DAY, '16:30'),  25, 'programada', NULL, 2, @hoy - INTERVAL 7 DAY),
(11, 1, 3, 6, NULL, TIMESTAMP(@hoy + INTERVAL 1 DAY, '09:00'),  TIMESTAMP(@hoy + INTERVAL 1 DAY, '12:00'),  18, 'programada', NULL, 2, @hoy - INTERVAL 7 DAY),
(12, 3, 2, 6, 3,    TIMESTAMP(@hoy + INTERVAL 2 DAY, '07:00'),  TIMESTAMP(@hoy + INTERVAL 3 DAY, '16:00'),  20, 'programada', NULL, 2, @hoy - INTERVAL 7 DAY),
(13, 5, 1, 5, NULL, TIMESTAMP(@hoy + INTERVAL 2 DAY, '08:00'),  TIMESTAMP(@hoy + INTERVAL 2 DAY, '16:00'),  25, 'programada', NULL, 2, @hoy - INTERVAL 7 DAY),
(14, 4, 3, 5, 4,    TIMESTAMP(@hoy + INTERVAL 3 DAY, '07:30'),  TIMESTAMP(@hoy + INTERVAL 4 DAY, '15:00'),  16, 'programada', NULL, 2, @hoy - INTERVAL 7 DAY);

-- ---------------------------------------------------------------------
-- 12. turista (titulares; ficticios)
-- ---------------------------------------------------------------------
INSERT INTO turista (id, nombres, apellidos, tipo_documento, numero_documento, nacionalidad,
                     telefono, correo, idioma, creado_en) VALUES
(1,  'Carmen Rosa',  'Torres Villanueva', 'DNI',       '41020304',  'PE', '900000201',    NULL,                             'es', NOW() - INTERVAL 20 DAY),
(2,  'Camille',      'Durand',            'PASAPORTE', '21FR45873', 'FR', NULL,           'camille.durand@correo.example',  'en', NOW() - INTERVAL 15 DAY),
(3,  'Michael',      'Bennett',           'PASAPORTE', '571234098', 'US', '+12125550101', 'michael.bennett@correo.example', 'en', NOW() - INTERVAL 14 DAY),
(4,  'Julio César',  'Mamani Coaquira',   'DNI',       '42870915',  'PE', '900000204',    NULL,                             'es', NOW() - INTERVAL 12 DAY),
(5,  'Lukas',        'Schneider',         'PASAPORTE', 'C4F7K2L9M', 'DE', NULL,           'lukas.schneider@correo.example', 'en', NOW() - INTERVAL 5 DAY),
(6,  'Patricia',     'Flores Arias',      'DNI',       '45678123',  'PE', '900000206',    'patricia.flores@correo.example', 'es', NOW() - INTERVAL 6 DAY),
(7,  'Martín',       'Gómez Ferreyra',    'CE',        '001234567', 'AR', '900000207',    NULL,                             'es', NOW() - INTERVAL 25 DAY),
(8,  'Diego',        'Salazar Ríos',      'DNI',       '46301122',  'PE', '900000208',    NULL,                             'es', NOW() - INTERVAL 4 DAY),
(9,  'Valentina',    'Rojas Muñoz',       'PASAPORTE', 'P12345678', 'CL', NULL,           'valentina.rojas@correo.example', 'es', NOW() - INTERVAL 3 DAY),
(10, 'Andrés',       'Ccori Huanca',      'DNI',       '47219034',  'PE', '900000210',    NULL,                             'es', NOW() - INTERVAL 2 DAY),
(11, 'Ana Beatriz',  'Souza Lima',        'PASAPORTE', 'FX123456',  'BR', NULL,           'ana.souza@correo.example',       'en', NOW() - INTERVAL 2 DAY),
(12, 'Gabriela',     'Paredes Chávez',    'DNI',       '43356781',  'PE', '900000212',    NULL,                             'es', NOW() - INTERVAL 1 DAY),
(13, 'Haruto',       'Sato',              'PASAPORTE', 'TZ1234567', 'JP', NULL,           'haruto.sato@correo.example',     'en', NOW() - INTERVAL 3 DAY),
(14, 'Luis Alberto', 'Vargas Pineda',     'DNI',       '40998812',  'PE', '900000214',    NULL,                             'es', NOW() - INTERVAL 2 DAY),
(15, 'Sofía',        'Ramírez Ortega',    'DNI',       '44120987',  'PE', '900000215',    'sofia.ramirez@correo.example',   'es', NOW() - INTERVAL 2 DAY),
(16, 'Emma',         'Wilson',            'PASAPORTE', '548812345', 'GB', NULL,           'emma.wilson@correo.example',     'en', NOW() - INTERVAL 1 DAY),
(17, 'Raúl',         'Huarachi Condori',  'DNI',       '48761230',  'PE', '900000217',    NULL,                             'es', NOW() - INTERVAL 10 MINUTE),
(18, 'Milagros',     'Cahui Pari',        'DNI',       '47001234',  'PE', '900000218',    NULL,                             'es', NOW() - INTERVAL 100 MINUTE),
(19, 'Valeria',      'Cruz Mendoza',      'DNI',       '70451236',  'PE', '900000219',    NULL,                             'es', NOW() - INTERVAL 1 DAY),
(20, 'Jaime',        'Apaza Ticona',      'DNI',       '42233445',  'PE', '900000220',    NULL,                             'es', NOW() - INTERVAL 3 HOUR);

-- ---------------------------------------------------------------------
-- 13. reserva · 23 reservas con TODOS los estados:
--   abordada (1,2,3,4,5,7) · no_show (6) · cancelada (8, 16 con devolución)
--   pagada (9 con 2 pagos parciales, 12, 15 reprogramada, 21) · confirmada (10,11,13,14,22,23)
--   pendiente_pago: 17 vigente · 18 vencida SIN marcar (RN-05: ya no cuenta) · 19 con pago reportado (P2)
--   vencida (20, ya marcada por el comando)
-- El total se calcula más abajo, con la suma de los pasajeros.
-- ---------------------------------------------------------------------
INSERT INTO reserva (id, codigo, salida_id, turista_id, estado, metodo_pago_elegido, vence_en,
                     token_envio, canal, reprogramada_desde_salida_id, creada_en) VALUES
(1,  'TV-RA57', 1,  7,  'abordada',  'yape',   TIMESTAMP(@hoy - INTERVAL 25 DAY, '12:00'), '2e9f8a1986e9b5fc7fe3759157bea41a', 'web', NULL, TIMESTAMP(@hoy - INTERVAL 25 DAY, '10:00')),
(2,  'TV-2MCU', 2,  1,  'abordada',  'yape',   TIMESTAMP(@hoy - INTERVAL 20 DAY, '21:30'), '8dcfcab68b7e37df82db7ce593ec365c', 'web', NULL, TIMESTAMP(@hoy - INTERVAL 20 DAY, '19:30')),
(3,  'TV-233S', 2,  2,  'abordada',  'muelle', NULL,                                       '7d4b26fd6deae44cce563c188d7bc751', 'web', NULL, TIMESTAMP(@hoy - INTERVAL 15 DAY, '08:10')),
(4,  'TV-E7XZ', 3,  3,  'abordada',  'muelle', NULL,                                       '677e7a48d33bc47814b1fadb92c4f2f5', 'web', NULL, TIMESTAMP(@hoy - INTERVAL 14 DAY, '21:00')),
(5,  'TV-6ZNN', 3,  4,  'abordada',  'yape',   TIMESTAMP(@hoy - INTERVAL 12 DAY, '14:40'), '08c8f89b11fac153a871fd4df39c9151', 'web', NULL, TIMESTAMP(@hoy - INTERVAL 12 DAY, '12:40')),
(6,  'TV-2TXC', 4,  5,  'no_show',   'muelle', NULL,                                       '4cca5ab5f422c4a04cd7816283409707', 'web', NULL, TIMESTAMP(@hoy - INTERVAL 5 DAY, '18:00')),
(7,  'TV-4VU5', 4,  6,  'abordada',  'yape',   TIMESTAMP(@hoy - INTERVAL 6 DAY, '11:15'),  '51af1e7ffa6cd850c2fde95dd6273d51', 'web', NULL, TIMESTAMP(@hoy - INTERVAL 6 DAY, '09:15')),
(8,  'TV-436W', 5,  8,  'cancelada', 'yape',   TIMESTAMP(@hoy - INTERVAL 4 DAY, '22:00'),  '2927887251702bac4bc0e16a81d750d3', 'web', NULL, TIMESTAMP(@hoy - INTERVAL 4 DAY, '20:00')),
(9,  'TV-DMT9', 6,  1,  'pagada',    'yape',   TIMESTAMP(@hoy - INTERVAL 3 DAY, '13:00'),  'b85e3e2e2f5386783536fd0de43477e1', 'web', NULL, TIMESTAMP(@hoy - INTERVAL 3 DAY, '11:00')),
(10, 'TV-6DQT', 6,  9,  'confirmada','muelle', NULL,                                       'f1b497215a4c16e1a18ea5d55dc9690f', 'whatsapp', NULL, TIMESTAMP(@hoy - INTERVAL 3 DAY, '16:20')),
(11, 'TV-WWUQ', 8,  10, 'confirmada','muelle', NULL,                                       'bb4c22117e6ee74226454f4c1500179a', 'mostrador', NULL, TIMESTAMP(@hoy - INTERVAL 2 DAY, '10:00')),
(12, 'TV-HAWC', 8,  11, 'pagada',    'muelle', NULL,                                       '4d97999e199379fb4ae3b054fe1a29ab', 'web', NULL, TIMESTAMP(@hoy - INTERVAL 2 DAY, '15:30')),
(13, 'TV-DK5D', 8,  12, 'confirmada','muelle', NULL,                                       'cae843d72fb62c540c4fff1fb2a5702e', 'web', NULL, TIMESTAMP(@hoy - INTERVAL 1 DAY, '20:45')),
(14, 'TV-GPJN', 9,  13, 'confirmada','muelle', NULL,                                       'eab68372618dcecd318c65fd2ecd36c1', 'web', NULL, TIMESTAMP(@hoy - INTERVAL 3 DAY, '07:30')),
(15, 'TV-33VR', 12, 14, 'pagada',    'yape',   TIMESTAMP(@hoy - INTERVAL 2 DAY, '15:00'),  '991adf81abe3505355a028b1217372a6', 'web', 9,    TIMESTAMP(@hoy - INTERVAL 2 DAY, '13:00')),
(16, 'TV-YSYM', 9,  15, 'cancelada', 'yape',   TIMESTAMP(@hoy - INTERVAL 2 DAY, '19:10'),  'a2e6ebdf8dc88a671fff12f590edfc1a', 'web', NULL, TIMESTAMP(@hoy - INTERVAL 2 DAY, '17:10')),
(17, 'TV-TX69', 10, 17, 'pendiente_pago', 'yape', NOW() + INTERVAL 110 MINUTE,             '9cccf630f50c381aef8c3b112fba832b', 'web', NULL, NOW() - INTERVAL 10 MINUTE),
(18, 'TV-UKKR', 10, 6,  'pendiente_pago', 'yape', NOW() - INTERVAL 30 MINUTE,              'add291adc55439b0cec665628db7671b', 'web', NULL, NOW() - INTERVAL 150 MINUTE),
(19, 'TV-RQCP', 10, 18, 'pendiente_pago', 'yape', TIMESTAMP(@hoy + INTERVAL 1 DAY, '06:00'), '5330feeeed920e85f78fd8353bbfd149', 'web', NULL, NOW() - INTERVAL 100 MINUTE),
(20, 'TV-7VUS', 11, 4,  'vencida',   'yape',   TIMESTAMP(@hoy - INTERVAL 1 DAY, '11:00'),  'f5f51b4b4206553fc505f4c5bb465588', 'web', NULL, TIMESTAMP(@hoy - INTERVAL 1 DAY, '09:00')),
(21, 'TV-ZVKA', 12, 19, 'pagada',    'plin',   TIMESTAMP(@hoy - INTERVAL 1 DAY, '20:00'),  'f87e6fbac1aa423e6d1f6b26efda2b44', 'web', NULL, TIMESTAMP(@hoy - INTERVAL 1 DAY, '18:00')),
(22, 'TV-8N4P', 13, 20, 'confirmada','muelle', NULL,                                       'ca75f101c8d071fbe25bdb834389b8a8', 'mostrador', NULL, NOW() - INTERVAL 3 HOUR),
(23, 'TV-D7H7', 14, 16, 'confirmada','muelle', NULL,                                       '11856f253d1c5972a8550574fb47ca9a', 'web', NULL, TIMESTAMP(@hoy - INTERVAL 1 DAY, '10:00'));

-- ---------------------------------------------------------------------
-- 14. reserva_pasajero · 58 pasajeros. El titular viaja como pasajero 1 (P1 de la F0).
-- Se hace en 3 pasos:
--   a) se escriben en una tabla temporal;
--   b) se calcula su precio con la regla RN-04 (UPDATE sobre la temporal);
--   c) se copian a reserva_pasajero.
-- ¿Por qué no un solo INSERT ... SELECT con JOIN a salida? Porque el trigger
-- de sobreventa bloquea la fila de salida (FOR UPDATE) y MariaDB no deja que
-- un trigger bloquee una tabla que la misma sentencia está leyendo (error 1442).
-- Si faltara una tarifa, el precio quedaría NULL y el paso c) fallaría (NOT NULL).
-- ---------------------------------------------------------------------
CREATE TEMPORARY TABLE tmp_semilla_pasajero (
  orden            INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  reserva_id       INT UNSIGNED NOT NULL,
  tipo_codigo      VARCHAR(20)  NOT NULL,
  nombres          VARCHAR(80)  NOT NULL,
  apellidos        VARCHAR(80)  NOT NULL,
  tipo_documento   VARCHAR(10)  NOT NULL,
  numero_documento VARCHAR(12)  NOT NULL,
  nacionalidad     CHAR(2)      NOT NULL,
  tipo_pasajero_id INT UNSIGNED NULL,      -- se llena en el paso b)
  precio           DECIMAL(8,2) NULL       -- se llena en el paso b)
);

INSERT INTO tmp_semilla_pasajero (reserva_id, tipo_codigo, nombres, apellidos, tipo_documento, numero_documento, nacionalidad) VALUES
(1,  'adulto_extranjero', 'Martín',       'Gómez Ferreyra',    'CE',        '001234567', 'AR'),
(1,  'adulto_extranjero', 'Lucía',        'Benítez Sosa',      'CE',        '001234568', 'AR'),
(2,  'adulto_nacional',   'Carmen Rosa',  'Torres Villanueva', 'DNI',       '41020304',  'PE'),
(2,  'adulto_nacional',   'Jorge Luis',   'Torres Villanueva', 'DNI',       '41020399',  'PE'),
(3,  'adulto_extranjero', 'Camille',      'Durand',            'PASAPORTE', '21FR45873', 'FR'),
(3,  'adulto_extranjero', 'Hugo',         'Durand',            'PASAPORTE', '21FR45874', 'FR'),
(4,  'adulto_extranjero', 'Michael',      'Bennett',           'PASAPORTE', '571234098', 'US'),
(4,  'adulto_extranjero', 'Sarah',        'Bennett',           'PASAPORTE', '571234099', 'US'),
(4,  'nino',              'Lily',         'Bennett',           'PASAPORTE', '571234100', 'US'),
(5,  'adulto_nacional',   'Julio César',  'Mamani Coaquira',   'DNI',       '42870915',  'PE'),
(5,  'adulto_mayor',      'Rosa',         'Coaquira Apaza',    'DNI',       '29345671',  'PE'),
(6,  'adulto_extranjero', 'Lukas',        'Schneider',         'PASAPORTE', 'C4F7K2L9M', 'DE'),
(7,  'adulto_nacional',   'Patricia',     'Flores Arias',      'DNI',       '45678123',  'PE'),
(7,  'estudiante',        'Kevin',        'Flores Arias',      'DNI',       '73451209',  'PE'),
(7,  'nino',              'Mía',          'Flores Arias',      'DNI',       '81234560',  'PE'),
(8,  'adulto_nacional',   'Diego',        'Salazar Ríos',      'DNI',       '46301122',  'PE'),
(8,  'adulto_nacional',   'Pamela',       'Ríos Salas',        'DNI',       '46301123',  'PE'),
(9,  'adulto_nacional',   'Carmen Rosa',  'Torres Villanueva', 'DNI',       '41020304',  'PE'),
(9,  'nino',              'Mateo',        'Torres Quispe',     'DNI',       '78123456',  'PE'),
(10, 'adulto_extranjero', 'Valentina',    'Rojas Muñoz',       'PASAPORTE', 'P12345678', 'CL'),
(10, 'adulto_extranjero', 'Tomás',        'Rojas Muñoz',       'PASAPORTE', 'P12345679', 'CL'),
(10, 'nino',              'Isidora',      'Rojas Vidal',       'PASAPORTE', 'P12345680', 'CL'),
(10, 'nino',              'Pedro',        'Rojas Vidal',       'PASAPORTE', 'P12345681', 'CL'),
(11, 'adulto_nacional',   'Andrés',       'Ccori Huanca',      'DNI',       '47219034',  'PE'),
(11, 'estudiante',        'Brayan',       'Quispe Ticona',     'DNI',       '74120011',  'PE'),
(11, 'estudiante',        'Luz Clarita',  'Mamani Flores',     'DNI',       '74120012',  'PE'),
(11, 'estudiante',        'Edwin',        'Calcina Pari',      'DNI',       '74120013',  'PE'),
(11, 'estudiante',        'Yesenia',      'Condori Apaza',     'DNI',       '74120014',  'PE'),
(12, 'adulto_extranjero', 'Ana Beatriz',  'Souza Lima',        'PASAPORTE', 'FX123456',  'BR'),
(12, 'adulto_extranjero', 'Rafael',       'Souza Lima',        'PASAPORTE', 'FX123457',  'BR'),
(12, 'adulto_extranjero', 'Carla',        'Mendes Rocha',      'PASAPORTE', 'FY223344',  'BR'),
(12, 'adulto_extranjero', 'João Pedro',   'Mendes Rocha',      'PASAPORTE', 'FY223345',  'BR'),
(13, 'adulto_nacional',   'Gabriela',     'Paredes Chávez',    'DNI',       '43356781',  'PE'),
(13, 'adulto_nacional',   'Hernán',       'Paredes Luna',      'DNI',       '43356700',  'PE'),
(13, 'adulto_nacional',   'Elsa',         'Chávez Rivas',      'DNI',       '43356701',  'PE'),
(13, 'nino',              'Thiago',       'Paredes Chávez',    'DNI',       '80112233',  'PE'),
(13, 'nino',              'Luana',        'Paredes Chávez',    'DNI',       '80112234',  'PE'),
(13, 'adulto_mayor',      'Dora',         'Luna Ccama',        'DNI',       '01234987',  'PE'),
(14, 'adulto_extranjero', 'Haruto',       'Sato',              'PASAPORTE', 'TZ1234567', 'JP'),
(14, 'adulto_extranjero', 'Yui',          'Sato',              'PASAPORTE', 'TZ1234568', 'JP'),
(15, 'adulto_nacional',   'Luis Alberto', 'Vargas Pineda',     'DNI',       '40998812',  'PE'),
(15, 'adulto_nacional',   'Norma',        'Pineda Salas',      'DNI',       '40998813',  'PE'),
(16, 'adulto_nacional',   'Sofía',        'Ramírez Ortega',    'DNI',       '44120987',  'PE'),
(16, 'estudiante',        'Carlos',       'Ramírez Ortega',    'DNI',       '44120988',  'PE'),
(17, 'adulto_nacional',   'Raúl',         'Huarachi Condori',  'DNI',       '48761230',  'PE'),
(17, 'adulto_nacional',   'Nélida',       'Condori Mamani',    'DNI',       '48761231',  'PE'),
(18, 'adulto_nacional',   'Patricia',     'Flores Arias',      'DNI',       '45678123',  'PE'),
(18, 'estudiante',        'Kevin',        'Flores Arias',      'DNI',       '73451209',  'PE'),
(18, 'nino',              'Mía',          'Flores Arias',      'DNI',       '81234560',  'PE'),
(19, 'adulto_nacional',   'Milagros',     'Cahui Pari',        'DNI',       '47001234',  'PE'),
(19, 'estudiante',        'Ronald',       'Cahui Pari',        'DNI',       '47001235',  'PE'),
(20, 'adulto_nacional',   'Julio César',  'Mamani Coaquira',   'DNI',       '42870915',  'PE'),
(21, 'adulto_nacional',   'Valeria',      'Cruz Mendoza',      'DNI',       '70451236',  'PE'),
(22, 'adulto_nacional',   'Jaime',        'Apaza Ticona',      'DNI',       '42233445',  'PE'),
(22, 'adulto_nacional',   'Marisol',      'Ticona Choque',     'DNI',       '42233446',  'PE'),
(22, 'nino',              'Fabián',       'Apaza Ticona',      'DNI',       '78990011',  'PE'),
(23, 'adulto_extranjero', 'Emma',         'Wilson',            'PASAPORTE', '548812345', 'GB'),
(23, 'adulto_extranjero', 'Oliver',       'Wilson',            'PASAPORTE', '548812346', 'GB');

-- Paso b) RN-04: precio = tarifa vigente en la fecha de la salida × (1 + recargo de la temporada / 100).
-- Si la reserva fue reprogramada, el precio es el de la salida original (no se cobra de más).
UPDATE tmp_semilla_pasajero p
JOIN reserva r        ON r.id = p.reserva_id
JOIN salida s         ON s.id = COALESCE(r.reprogramada_desde_salida_id, r.salida_id)
JOIN tipo_pasajero tp ON tp.codigo = p.tipo_codigo
LEFT JOIN tarifa t    ON t.ruta_id = s.ruta_id
                     AND t.tipo_pasajero_id = tp.id
                     AND t.vigente_desde = (SELECT MAX(t2.vigente_desde) FROM tarifa t2
                                            WHERE t2.ruta_id = s.ruta_id
                                              AND t2.tipo_pasajero_id = tp.id
                                              AND t2.vigente_desde <= DATE(s.fecha_hora_zarpe)
                                              AND (t2.vigente_hasta IS NULL
                                                   OR t2.vigente_hasta >= DATE(s.fecha_hora_zarpe)))
SET p.tipo_pasajero_id = tp.id,
    p.precio = ROUND(t.precio_base * (1 + COALESCE(
                 (SELECT MAX(te.recargo_porcentaje) FROM temporada te
                  WHERE DATE(s.fecha_hora_zarpe) BETWEEN te.fecha_inicio AND te.fecha_fin), 0) / 100), 2);

-- Paso c) copiar a la tabla real (aquí actúa el trigger de sobreventa, pasajero por pasajero)
INSERT INTO reserva_pasajero (reserva_id, tipo_pasajero_id, nombres, apellidos, tipo_documento,
                              numero_documento, nacionalidad, precio_aplicado)
SELECT reserva_id, tipo_pasajero_id, nombres, apellidos, tipo_documento, numero_documento,
       nacionalidad, precio
FROM tmp_semilla_pasajero
ORDER BY orden;

DROP TEMPORARY TABLE tmp_semilla_pasajero;

-- reserva.total = suma de los precios aplicados (RN-04).
-- "actualizada_en = actualizada_en" evita que el ON UPDATE le ponga la hora de hoy.
UPDATE reserva r
SET r.total = (SELECT SUM(rp.precio_aplicado) FROM reserva_pasajero rp WHERE rp.reserva_id = r.id),
    r.actualizada_en = r.actualizada_en;

-- ---------------------------------------------------------------------
-- 15. pago · 14 pagos: verificados, uno rechazado, uno reportado y uno
--     partido en dos (reserva 9). El monto sale del total de la reserva.
-- ---------------------------------------------------------------------
INSERT INTO pago (reserva_id, metodo, monto, numero_operacion, estado, reportado_en,
                  verificado_por, verificado_en, observacion)
SELECT r.id, 'yape', r.total, '10450001', 'verificado', r.creada_en + INTERVAL 20 MINUTE, 2, r.creada_en + INTERVAL 90 MINUTE, NULL
FROM reserva r WHERE r.id = 1
UNION ALL
SELECT r.id, 'yape', r.total, '10450002', 'verificado', r.creada_en + INTERVAL 25 MINUTE, 2, r.creada_en + INTERVAL 80 MINUTE, NULL
FROM reserva r WHERE r.id = 2
UNION ALL
SELECT r.id, 'efectivo_muelle', r.total, NULL, 'verificado', s.fecha_hora_zarpe - INTERVAL 30 MINUTE, 2, s.fecha_hora_zarpe - INTERVAL 30 MINUTE, 'Cobrado en el muelle'
FROM reserva r JOIN salida s ON s.id = r.salida_id WHERE r.id = 3
UNION ALL
SELECT r.id, 'pos', r.total, 'POS-778812', 'verificado', s.fecha_hora_zarpe - INTERVAL 40 MINUTE, 2, s.fecha_hora_zarpe - INTERVAL 40 MINUTE, 'Tarjeta en el muelle'
FROM reserva r JOIN salida s ON s.id = r.salida_id WHERE r.id = 4
UNION ALL
SELECT r.id, 'yape', r.total, '10450005', 'verificado', r.creada_en + INTERVAL 15 MINUTE, 2, r.creada_en + INTERVAL 60 MINUTE, NULL
FROM reserva r WHERE r.id = 5
UNION ALL
SELECT r.id, 'yape', r.total, '10450007', 'verificado', r.creada_en + INTERVAL 30 MINUTE, 2, r.creada_en + INTERVAL 70 MINUTE, NULL
FROM reserva r WHERE r.id = 7
UNION ALL
-- reserva 9: dos pagos parciales que juntos suman el total (S-12)
SELECT r.id, 'yape', ROUND(r.total / 2, 2), '10450009', 'verificado', r.creada_en + INTERVAL 10 MINUTE, 2, r.creada_en + INTERVAL 50 MINUTE, 'Primer pago (mitad)'
FROM reserva r WHERE r.id = 9
UNION ALL
SELECT r.id, 'yape', r.total - ROUND(r.total / 2, 2), '10450010', 'verificado', r.creada_en + INTERVAL 40 MINUTE, 2, r.creada_en + INTERVAL 70 MINUTE, 'Segundo pago (resto)'
FROM reserva r WHERE r.id = 9
UNION ALL
SELECT r.id, 'pos', r.total, 'POS-778901', 'verificado', r.creada_en + INTERVAL 15 MINUTE, 2, r.creada_en + INTERVAL 15 MINUTE, 'Pagó con tarjeta en la oficina'
FROM reserva r WHERE r.id = 12
UNION ALL
SELECT r.id, 'yape', r.total, '10450015', 'verificado', r.creada_en + INTERVAL 20 MINUTE, 2, r.creada_en + INTERVAL 75 MINUTE, NULL
FROM reserva r WHERE r.id = 15
UNION ALL
SELECT r.id, 'yape', r.total, '10450016', 'verificado', r.creada_en + INTERVAL 20 MINUTE, 2, r.creada_en + INTERVAL 60 MINUTE, NULL
FROM reserva r WHERE r.id = 16
UNION ALL
SELECT r.id, 'yape', r.total, '10450018', 'rechazado', r.creada_en + INTERVAL 30 MINUTE, 2, r.creada_en + INTERVAL 60 MINUTE, 'Número de operación no encontrado en Yape'
FROM reserva r WHERE r.id = 18
UNION ALL
SELECT r.id, 'yape', r.total, '10450019', 'reportado', r.creada_en + INTERVAL 20 MINUTE, NULL, NULL, NULL
FROM reserva r WHERE r.id = 19
UNION ALL
SELECT r.id, 'plin', r.total, '20330021', 'verificado', r.creada_en + INTERVAL 15 MINUTE, 2, r.creada_en + INTERVAL 45 MINUTE, NULL
FROM reserva r WHERE r.id = 21;

-- ---------------------------------------------------------------------
-- 16. hospedaje · sigue la rotación RN-10 (ver docs/fase-1-base-datos.md).
--     monto_familia = personas × S/ 40.00 (PAGO_FAMILIA_PERSONA_NOCHE, P3).
-- ---------------------------------------------------------------------
INSERT INTO hospedaje (reserva_id, familia_id, fecha_noche, personas, monto_familia, estado, motivo_reasignacion) VALUES
(4,  1, @hoy - INTERVAL 6 DAY,  3, 120.00, 'cumplido',  NULL),
(5,  2, @hoy - INTERVAL 6 DAY,  2,  80.00, 'cumplido',  NULL),
(1,  6, @hoy - INTERVAL 12 DAY, 2,  80.00, 'cumplido',  NULL),
(14, 3, @hoy + INTERVAL 1 DAY,  2,  80.00, 'asignado',  NULL),
(16, 4, @hoy + INTERVAL 1 DAY,  2,  80.00, 'cancelado', NULL),
(15, 1, @hoy + INTERVAL 1 DAY,  2,  80.00, 'cancelado', 'Reprogramada a la salida 12 por alerta de oleaje'),
(15, 4, @hoy + INTERVAL 2 DAY,  2,  80.00, 'asignado',  NULL),
(21, 1, @hoy + INTERVAL 2 DAY,  1,  40.00, 'asignado',  NULL),
(23, 7, @hoy + INTERVAL 3 DAY,  2,  80.00, 'asignado',  NULL);

-- ---------------------------------------------------------------------
-- 17. abordaje · todos los pasajeros de las reservas "abordada",
--     registrados 20 minutos antes del zarpe por el guía (o el capitán).
-- ---------------------------------------------------------------------
INSERT INTO abordaje (reserva_pasajero_id, salida_id, registrado_por, registrado_en, metodo)
SELECT rp.id, r.salida_id, COALESCE(s.guia_id, s.capitan_id),
       s.fecha_hora_zarpe - INTERVAL 20 MINUTE,
       IF(rp.id % 3 = 0, 'manual', 'qr')
FROM reserva_pasajero rp
JOIN reserva r ON r.id = rp.reserva_id
JOIN salida s  ON s.id = r.salida_id
WHERE r.estado = 'abordada'
ORDER BY rp.id;

-- ---------------------------------------------------------------------
-- 18. alerta_lago · la 1 está VIGENTE ahora y es naranja sobre Amantaní:
--     por eso la salida 9 (Uros-Amantaní-Taquile de mañana) está suspendida.
-- ---------------------------------------------------------------------
INSERT INTO alerta_lago (id, tipo, nivel, titulo, descripcion, fuente, comunidad_id,
                         vigente_desde, vigente_hasta, registrada_por) VALUES
(1, 'oleaje',   'naranja',  'Oleaje fuerte en el sector de Amantaní',
    'Vientos del oeste con oleaje de más de 1 m. Se recomienda no navegar a Amantaní.',
    'SENAMHI', 3, TIMESTAMP(@hoy, '00:00'), TIMESTAMP(@hoy + INTERVAL 2 DAY, '06:00'), 2),
(2, 'helada',   'amarillo', 'Heladas en la madrugada',
    'Temperaturas bajo cero antes del amanecer. Llevar abrigo para las salidas tempranas.',
    'SENAMHI', NULL, TIMESTAMP(@hoy, '00:00'), TIMESTAMP(@hoy + INTERVAL 1 DAY, '09:00'), 2),
(3, 'tormenta', 'rojo',     'Tormenta eléctrica sobre el lago',
    'La Capitanía cerró la navegación durante la tarde.',
    'Capitania', NULL, TIMESTAMP(@hoy - INTERVAL 15 DAY, '13:00'), TIMESTAMP(@hoy - INTERVAL 15 DAY, '20:00'), 2),
(4, 'neblina',  'amarillo', 'Neblina densa en la bahía de Puno',
    'Poca visibilidad cerca de los Uros; las lanchas salieron con retraso.',
    'Agencia', 1, TIMESTAMP(@hoy - INTERVAL 9 DAY, '05:00'), TIMESTAMP(@hoy - INTERVAL 9 DAY, '09:00'), 2),
(5, 'granizo',  'naranja',  'Granizada en Taquile',
    'Aviso de la comunidad: caminos resbalosos hacia la plaza.',
    'Comunidad', 2, TIMESTAMP(@hoy - INTERVAL 30 DAY, '14:00'), TIMESTAMP(@hoy - INTERVAL 30 DAY, '18:00'), 2),
(6, 'otro',     'verde',    'Fiesta comunal en Llachón',
    'Habrá mucha gente en el muelle; el desembarco será por el muelle principal.',
    'Comunidad', 4, TIMESTAMP(@hoy + INTERVAL 3 DAY, '06:00'), TIMESTAMP(@hoy + INTERVAL 4 DAY, '20:00'), 2);

-- ---------------------------------------------------------------------
-- 19. resena · solo de reservas abordadas y ya viajadas (RN-13)
-- ---------------------------------------------------------------------
INSERT INTO resena (reserva_id, puntuacion, comentario, idioma, estado, moderada_por, creada_en) VALUES
(1, 4, 'Llachón nos recibió como en casa. La lancha salió puntual.',         'es', 'publicada', 2,    @hoy - INTERVAL 10 DAY),
(2, 5, 'Taquile es precioso y el guía explicó muy bien los tejidos.',        'es', 'publicada', 2,    @hoy - INTERVAL 6 DAY),
(3, 4, 'Beautiful day on the lake. Bring sunscreen and a warm jacket!',      'en', 'publicada', 2,    @hoy - INTERVAL 6 DAY),
(4, 5, 'Our host family in Amantaní was wonderful. Unforgettable sunset.',   'en', 'pendiente', NULL, @hoy - INTERVAL 4 DAY),
(5, 1, 'Mejor contraten con otra agencia, escríbanme por WhatsApp.',         'es', 'rechazada', 2,    @hoy - INTERVAL 4 DAY),
(7, 5, 'Fuimos con los niños y les encantó subir a la balsa de totora.',     'es', 'publicada', 2,    @hoy - INTERVAL 1 DAY);

-- ---------------------------------------------------------------------
-- 20. bitacora · inicios de sesión y cambios de estado (RN-14)
-- ---------------------------------------------------------------------
INSERT INTO bitacora (usuario_id, accion, tabla_afectada, registro_id, detalle, ip, creado_en) VALUES
(5,    'cambio_estado', 'salida', 2,  JSON_OBJECT('de', 'zarpo', 'a', 'finalizada', 'motivo', NULL),
       '192.168.1.25', TIMESTAMP(@hoy - INTERVAL 7 DAY, '16:40')),
(2,    'cambio_estado', 'salida', 5,  JSON_OBJECT('de', 'programada', 'a', 'cancelada',
       'motivo', 'Falla del motor: la lancha pasó a revisión'), '192.168.1.11', TIMESTAMP(@hoy - INTERVAL 2 DAY, '18:00')),
(NULL, 'cambio_estado', 'reserva', 20, JSON_OBJECT('de', 'pendiente_pago', 'a', 'vencida', 'origen', 'flask reservas vencer'),
       NULL, TIMESTAMP(@hoy - INTERVAL 1 DAY, '11:05')),
(1,    'inicio_sesion', 'usuario', 1, JSON_OBJECT('resultado', 'ok'), '192.168.1.10', TIMESTAMP(@hoy - INTERVAL 1 DAY, '08:02')),
(2,    'inicio_sesion', 'usuario', 2, JSON_OBJECT('resultado', 'ok'), '192.168.1.11', NOW() - INTERVAL 70 MINUTE),
(2,    'cambio_estado', 'salida', 9,  JSON_OBJECT('de', 'programada', 'a', 'suspendida',
       'motivo', 'Alerta naranja de oleaje en Amantaní (SENAMHI)', 'alerta_id', 1), '192.168.1.11', NOW() - INTERVAL 60 MINUTE),
(3,    'inicio_sesion', 'usuario', 3, JSON_OBJECT('resultado', 'ok'), '192.168.1.23', NOW() - INTERVAL 50 MINUTE),
(NULL, 'cambio_estado', 'reserva', 16, JSON_OBJECT('de', 'pagada', 'a', 'cancelada', 'motivo', 'salida suspendida'),
       '203.0.113.45', NOW() - INTERVAL 40 MINUTE),
(NULL, 'devolucion_solicitada', 'reserva', 16, JSON_OBJECT('monto_verificado', (SELECT total FROM reserva WHERE id = 16),
       'motivo', 'salida suspendida por alerta'), '203.0.113.45', NOW() - INTERVAL 40 MINUTE),
(NULL, 'reprogramacion', 'reserva', 15, JSON_OBJECT('desde_salida', 9, 'a_salida', 12),
       '203.0.113.77', NOW() - INTERVAL 30 MINUTE),
(NULL, 'cambio_estado', 'hospedaje', 6, JSON_OBJECT('de', 'asignado', 'a', 'cancelado', 'motivo', 'reprogramación'),
       '203.0.113.77', NOW() - INTERVAL 30 MINUTE),
(2,    'cambio_estado', 'pago', (SELECT id FROM pago WHERE numero_operacion = '10450010'),
       JSON_OBJECT('de', 'reportado', 'a', 'verificado'), '192.168.1.11', NOW() - INTERVAL 20 MINUTE),
(2,    'cambio_estado', 'pago', (SELECT id FROM pago WHERE numero_operacion = '10450018'),
       JSON_OBJECT('de', 'reportado', 'a', 'rechazado', 'observacion', 'Número de operación no encontrado en Yape'),
       '192.168.1.11', NOW() - INTERVAL 15 MINUTE);

-- Último acceso de los usuarios demo (coherente con la bitácora)
UPDATE usuario SET ultimo_acceso = TIMESTAMP(@hoy - INTERVAL 1 DAY, '08:02') WHERE id = 1;
UPDATE usuario SET ultimo_acceso = NOW() - INTERVAL 70 MINUTE WHERE id = 2;
UPDATE usuario SET ultimo_acceso = NOW() - INTERVAL 50 MINUTE WHERE id = 3;

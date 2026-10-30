-- =====================================================================
-- 00_crear_bd_usuario.sql · Titicaca Vivo
-- Crea las 2 bases (la de trabajo y la de pruebas) y el usuario de la app.
-- Se ejecuta UNA vez, como root. La forma recomendada (PASO 4 de INSTRUCCIONES.txt):
--   python scripts/crear_bd.py
-- Ese script pone aquí la contraseña de BD_CONTRASENA del .env sin editar este archivo.
-- Si lo haces a mano en phpMyAdmin (pestaña SQL): pega el contenido y cambia
-- 'CAMBIA_ESTA_CLAVE' EN EL CUADRO DE phpMyAdmin, no en este archivo, y escribe esa
-- misma contraseña en BD_CONTRASENA del .env. Este archivo nunca lleva la contraseña
-- real: va en el ZIP de entrega (la prueba test_el_script_de_usuario_no_lleva_contrasena).
-- =====================================================================

CREATE DATABASE IF NOT EXISTS titicaca_vivo
  CHARACTER SET utf8mb4 COLLATE utf8mb4_spanish_ci;

CREATE DATABASE IF NOT EXISTS titicaca_vivo_pruebas
  CHARACTER SET utf8mb4 COLLATE utf8mb4_spanish_ci;

-- Un usuario para localhost (IPv4 e IPv6) y otro para 'localhost' por socket/pipe.
CREATE USER IF NOT EXISTS 'titicaca_app'@'localhost' IDENTIFIED BY 'CAMBIA_ESTA_CLAVE';
CREATE USER IF NOT EXISTS 'titicaca_app'@'127.0.0.1' IDENTIFIED BY 'CAMBIA_ESTA_CLAVE';

-- Todos los permisos, pero SOLO sobre estas dos bases: así 'flask bd reiniciar'
-- puede borrar y volver a crear su base, crear triggers y procedimientos.
GRANT ALL PRIVILEGES ON titicaca_vivo.* TO 'titicaca_app'@'localhost';
GRANT ALL PRIVILEGES ON titicaca_vivo_pruebas.* TO 'titicaca_app'@'localhost';
GRANT ALL PRIVILEGES ON titicaca_vivo.* TO 'titicaca_app'@'127.0.0.1';
GRANT ALL PRIVILEGES ON titicaca_vivo_pruebas.* TO 'titicaca_app'@'127.0.0.1';
FLUSH PRIVILEGES;

#!/bin/sh
# Arranque en la nube (Práctica 14): MariaDB dentro del contenedor, los datos de ejemplo, la clave
# de las cuentas demo y gunicorn escuchando en 0.0.0.0 y en el puerto que pone la plataforma (PORT).
#
# ¿Dura la base? Depende de dónde vivan sus archivos (MARIADB_DATOS):
#   - Render gratis: no hay disco que dure. La base se crea y se carga con la semilla en cada arranque.
#   - Railway con un volumen montado en /data y MARIADB_DATOS=/data/mysql: la base se carga UNA vez;
#     en los arranques siguientes se queda como está (reservas, usuarios nuevos, claves cambiadas).
set -e
cd "$(dirname "$0")/.."

echo "== Titicaca Vivo · arrancando en la nube =="
DATOS="${MARIADB_DATOS:-/var/lib/mysql}"
mkdir -p /run/mysqld "$DATOS"
# MariaDB corre como el usuario mysql: tiene que poder entrar a la carpeta (un volumen nuevo es de root).
chown mysql:mysql /run/mysqld "$DATOS"
chmod o+x "$(dirname "$DATOS")"
if [ ! -d "$DATOS/mysql" ]; then
  echo "Primera vez en $DATOS: se crean los archivos de MariaDB."
  mariadb-install-db --user=mysql --datadir="$DATOS" --skip-test-db > /tmp/mariadb-instalar.log 2>&1 \
    || { cat /tmp/mariadb-instalar.log; exit 1; }
fi
chown -R mysql:mysql /run/mysqld "$DATOS"
mariadbd --user=mysql --datadir="$DATOS" --bind-address=127.0.0.1 --skip-name-resolve --skip-log-bin \
  --innodb-buffer-pool-size=32M --performance-schema=OFF --max-connections=40 \
  > /tmp/mariadb.log 2>&1 &

i=0
until mariadb-admin --silent ping > /dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -gt 90 ]; then
    echo "MariaDB no arrancó:"; cat /tmp/mariadb.log; exit 1
  fi
  sleep 1
done
echo "MariaDB lista: $(mariadb -N -e 'SELECT VERSION()') · archivos en $DATOS"

# La base solo se ve desde adentro del contenedor; su clave se inventa en cada arranque.
export BD_HOST=127.0.0.1 BD_PUERTO=3306 BD_USUARIO=titicaca_app BD_NOMBRE=titicaca_vivo
BD_CONTRASENA="$(python -c 'import secrets; print(secrets.token_hex(16))')"
export BD_CONTRASENA
mariadb -e "CREATE USER IF NOT EXISTS 'titicaca_app'@'127.0.0.1' IDENTIFIED BY '${BD_CONTRASENA}';
  ALTER USER 'titicaca_app'@'127.0.0.1' IDENTIFIED BY '${BD_CONTRASENA}';
  GRANT ALL PRIVILEGES ON titicaca_vivo.* TO 'titicaca_app'@'127.0.0.1';
  FLUSH PRIVILEGES;"

TABLAS="$(mariadb -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'titicaca_vivo'")"
if [ "$TABLAS" -eq 0 ]; then
  echo "Cargando los datos de ejemplo (21 tablas, vistas y triggers)..."
  # «flask bd reiniciar» no corre en producción (candado contra borrar una base de verdad). Aquí
  # la base está vacía: solo ese comando corre como desarrollo.
  ENTORNO=desarrollo flask bd reiniciar --si --sin-respaldo
  if [ -n "$CLAVE_DEMO" ]; then
    flask usuarios clave-demo
  else
    echo "AVISO: falta CLAVE_DEMO; las cuentas demo usan las claves del repositorio."
  fi
else
  echo "La base ya tiene sus datos ($TABLAS tablas y vistas): no se vuelve a cargar."
  # Los cambios de la base después de cargarla (database/migraciones): cada archivo se puede
  # correr las veces que sea, así que se pasan todos en cada arranque.
  for migracion in database/migraciones/*.sql; do
    [ -f "$migracion" ] || continue
    mariadb titicaca_vivo < "$migracion"
    echo "Migración al día: $(basename "$migracion")"
  done
fi

export URL_PUBLICA="${URL_PUBLICA:-$RENDER_EXTERNAL_URL}"
echo "Escuchando en 0.0.0.0:${PORT:-10000} · ${URL_PUBLICA}"
exec gunicorn "app:crear_app()" --bind "0.0.0.0:${PORT:-10000}" --workers 1 --threads 8 \
  --timeout 120 --access-logfile - --error-logfile -

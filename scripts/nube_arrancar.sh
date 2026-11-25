#!/bin/sh
# Práctica 14 · arranque en Render: MariaDB dentro del contenedor, los datos de ejemplo, la clave
# de las cuentas demo y gunicorn escuchando en 0.0.0.0 y en el puerto que pone Render (PORT).
set -e
cd "$(dirname "$0")/.."

echo "== Titicaca Vivo · arrancando en la nube =="
mkdir -p /run/mysqld
chown mysql:mysql /run/mysqld
mariadbd --user=mysql --bind-address=127.0.0.1 --skip-name-resolve --skip-log-bin \
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
echo "MariaDB lista: $(mariadb -N -e 'SELECT VERSION()')"

# La base solo se ve desde adentro del contenedor; su clave se inventa en cada arranque.
export BD_HOST=127.0.0.1 BD_PUERTO=3306 BD_USUARIO=titicaca_app BD_NOMBRE=titicaca_vivo
BD_CONTRASENA="$(python -c 'import secrets; print(secrets.token_hex(16))')"
export BD_CONTRASENA
mariadb -e "CREATE USER IF NOT EXISTS 'titicaca_app'@'127.0.0.1' IDENTIFIED BY '${BD_CONTRASENA}';
  ALTER USER 'titicaca_app'@'127.0.0.1' IDENTIFIED BY '${BD_CONTRASENA}';
  GRANT ALL PRIVILEGES ON titicaca_vivo.* TO 'titicaca_app'@'127.0.0.1';
  FLUSH PRIVILEGES;"

echo "Cargando los datos de ejemplo (21 tablas, vistas y triggers)..."
# «flask bd reiniciar» no corre en producción (candado contra borrar una base de verdad). Esta
# base vive dentro del contenedor y es de demostración: solo ese comando corre como desarrollo.
ENTORNO=desarrollo flask bd reiniciar --si --sin-respaldo
if [ -n "$CLAVE_DEMO" ]; then
  flask usuarios clave-demo
else
  echo "AVISO: falta CLAVE_DEMO; las cuentas demo usan las claves del repositorio."
fi

export URL_PUBLICA="${URL_PUBLICA:-$RENDER_EXTERNAL_URL}"
echo "Escuchando en 0.0.0.0:${PORT:-10000} · ${URL_PUBLICA}"
exec gunicorn "app:crear_app()" --bind "0.0.0.0:${PORT:-10000}" --workers 1 --threads 8 \
  --timeout 120 --access-logfile - --error-logfile -

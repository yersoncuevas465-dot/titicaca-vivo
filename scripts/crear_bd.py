"""PASO 4 de INSTRUCCIONES.txt: crea las 2 bases y el usuario de MySQL con la contraseña del .env.

    python scripts/crear_bd.py                      # root sin contraseña (XAMPP recién instalado)
    python scripts/crear_bd.py --pedir-clave-root   # si el root de tu MySQL tiene contraseña

Ejecuta database/00_crear_bd_usuario.sql como root y pone la contraseña de BD_CONTRASENA (del
.env) donde el script dice CAMBIA_ESTA_CLAVE; si BD_CONTRASENA está vacía, genera una y la guarda.
Así la contraseña vive SOLO en el .env: el .sql no se edita y el ZIP de entrega nunca la lleva
(D-104). Si el usuario ya existía con otra contraseña, le pone la del .env. Se puede ejecutar
más de una vez.
"""

import argparse
import getpass
import secrets
import sys
from pathlib import Path

import pymysql

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import servidor  # noqa: E402
from app import bd, diagnostico  # noqa: E402

SCRIPT = RAIZ / "database" / "00_crear_bd_usuario.sql"
MARCA = "CAMBIA_ESTA_CLAVE"
USUARIO = "titicaca_app"             # el que crea 00_crear_bd_usuario.sql
HOSTS = ("localhost", "127.0.0.1")


def clave_de_la_app(env):
    """BD_CONTRASENA del .env. Si está vacía, genera una, la guarda en el .env y la devuelve."""
    clave = servidor.valor_en_env(env, "BD_CONTRASENA")
    if not clave:
        clave = secrets.token_urlsafe(18)
        servidor.fijar_en_env(env, "BD_CONTRASENA", clave)
    return clave


def sentencias(clave):
    """Las sentencias de 00_crear_bd_usuario.sql con la contraseña puesta, y un ALTER USER por
    host para que un usuario que ya existía quede con la misma contraseña del .env."""
    escapada = pymysql.converters.escape_string(clave)
    texto = SCRIPT.read_text(encoding="utf-8")
    lista = [s.replace(MARCA, escapada) for s in bd.dividir_sentencias(texto)]
    lista += [f"ALTER USER '{USUARIO}'@'{host}' IDENTIFIED BY '{escapada}'" for host in HOSTS]
    return lista


def main(argv=None):
    argumentos = argparse.ArgumentParser(description="Crea las bases y el usuario de Titicaca Vivo")
    argumentos.add_argument("--pedir-clave-root", action="store_true",
                            help="pregunta la contraseña del root de MySQL (XAMPP no tiene)")
    opciones = argumentos.parse_args(argv)

    print("Titicaca Vivo · crear las bases y el usuario de MySQL (PASO 4)")
    if SCRIPT.read_text(encoding="utf-8").count(f"IDENTIFIED BY '{MARCA}'") < 2:
        print(f"  [X]  {SCRIPT.name} ya no dice {MARCA}: alguien escribió una contraseña ahí.\n"
              f"       Qué hacer: vuelve a poner '{MARCA}' en las 2 líneas CREATE USER y ejecuta\n"
              "       este script otra vez (la contraseña va solo en el .env).")
        return 1
    servidor.preparar_env()
    env = RAIZ / ".env"
    habia_clave = bool(servidor.valor_en_env(env, "BD_CONTRASENA"))
    clave = clave_de_la_app(env)
    print("  [ok] Contraseña de titicaca_app: " +
          ("la de BD_CONTRASENA del .env" if habia_clave else "se generó una y se guardó en .env"))

    from app.config import Config

    clave_root = getpass.getpass("Contraseña de root: ") if opciones.pedir_clave_root else ""
    config = {"BD_HOST": Config.BD_HOST, "BD_PUERTO": Config.BD_PUERTO, "BD_USUARIO": "root",
              "BD_CONTRASENA": clave_root, "BD_NOMBRE": Config.BD_NOMBRE}
    try:
        conexion = pymysql.connect(host=Config.BD_HOST, port=int(Config.BD_PUERTO), user="root",
                                   password=clave_root, charset="utf8mb4", autocommit=True,
                                   connect_timeout=5)
    except pymysql.err.MySQLError as error:
        if diagnostico.codigo_de(error) == 1045:
            print("  [X]  MySQL no aceptó a root sin contraseña.\n"
                  "       Qué hacer:  python scripts/crear_bd.py --pedir-clave-root")
        else:
            primera, *resto = diagnostico.explicar(error, config).splitlines()
            print(f"  [X]  {primera}" + "".join(f"\n       {linea}" for linea in resto))
        return 1
    try:
        with conexion.cursor() as cur:
            for sentencia in sentencias(clave):
                cur.execute(sentencia)
    finally:
        conexion.close()
    print(f"  [ok] Bases titicaca_vivo y titicaca_vivo_pruebas, y usuario {USUARIO} "
          "(localhost y 127.0.0.1)")
    if Config.BD_USUARIO != USUARIO:
        print(f"  [!]  El .env dice BD_USUARIO={Config.BD_USUARIO}: el script crea '{USUARIO}'.")
    print("\n  Siguiente paso (PASO 5):  flask bd reiniciar --si   (las 20 tablas con los datos)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

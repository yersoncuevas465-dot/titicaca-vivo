"""Servidor de Titicaca Vivo para Windows (waitress).

`flask run` es solo para desarrollo. Para la demostración o la red de la agencia:

    python servidor.py                      # http://127.0.0.1:8080
    python servidor.py --abrir              # y abre el navegador (lo usa INICIAR.bat)
    python servidor.py --host 0.0.0.0       # visible para los celulares de la misma red
    python servidor.py --revisar            # solo revisa que todo esté listo, sin arrancar

Antes de abrir el puerto revisa, en orden, lo que suele fallar en una PC nueva: la versión de
Python, las dependencias, el archivo .env, MySQL, la base (tablas, vistas, triggers y datos) y
el puerto. Si algo falta, dice exactamente qué hacer y no arranca. El paso a paso completo está
en INSTRUCCIONES.txt.
"""

import argparse
import importlib.util
import re
import secrets
import shutil
import socket
import sys
import threading
import webbrowser
from datetime import date
from importlib.metadata import version
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PYTHON_MINIMO = (3, 12)
# Paquete de requirements.txt → módulo que se importa
DEPENDENCIAS = {
    "Flask": "flask", "PyMySQL": "pymysql", "Flask-WTF": "flask_wtf", "Flask-Login": "flask_login",
    "Flask-Limiter": "flask_limiter", "bcrypt": "bcrypt", "python-dotenv": "dotenv",
    "tzdata": "tzdata", "qrcode": "qrcode", "reportlab": "reportlab", "waitress": "waitress",
}
ACTIVAR = r"& $env:USERPROFILE\.venvs\titicaca_vivo\Scripts\Activate.ps1"
TODA_LA_RED = "0.0.0.0"  # noqa: S104 (solo si se pide con --host, para los celulares de la red)


def bien(texto):
    print(f"  [ok] {texto}")


def mal(texto):
    """La primera línea es el problema; las siguientes, lo que hay que hacer."""
    primera, *resto = texto.splitlines()
    print(f"  [X]  {primera}")
    for linea in resto:
        print(f"       {linea}")


def revisar_python():
    actual = ".".join(str(n) for n in sys.version_info[:3])
    if sys.version_info[:2] < PYTHON_MINIMO:
        return False, (f"Python {actual}: el proyecto necesita 3.12 o 3.13.\n"
                       "Qué hacer: instala Python 3.13 y crea el entorno con  py -3.13 -m venv\n"
                       "(INSTRUCCIONES.txt, PASO 2).")
    return True, f"Python {actual}"


def revisar_dependencias():
    faltan = [paquete for paquete, modulo in DEPENDENCIAS.items()
              if importlib.util.find_spec(modulo) is None]
    if faltan:
        return False, (f"Faltan dependencias en este Python: {', '.join(faltan)}.\n"
                       f"Se está usando {sys.executable}\n"
                       "Qué hacer: usa el entorno virtual del proyecto: doble clic en\n"
                       "INICIAR.bat, o en PowerShell:\n"
                       f"   {ACTIVAR}\n"
                       "   pip install -r requirements.txt\n"
                       "   python servidor.py\n"
                       "Si el entorno no existe, créalo (INSTRUCCIONES.txt, PASO 2).")
    principales = ", ".join(f"{p} {version(p)}" for p in ("Flask", "PyMySQL", "waitress"))
    return True, f"Dependencias instaladas ({principales})"


def valor_en_env(env, clave):
    """El valor de CLAVE en el .env ('' si no está o está vacía)."""
    actual = re.search(rf"(?m)^{clave}=(.*)$", env.read_text(encoding="utf-8"))
    return actual.group(1).strip().strip("'\"") if actual else ""


def fijar_en_env(env, clave, valor):
    """Escribe CLAVE=valor en el .env: cambia esa línea si ya está o la agrega al final."""
    texto = env.read_text(encoding="utf-8")
    linea = f"{clave}={valor}"
    actual = re.search(rf"(?m)^{clave}=.*$", texto)
    if actual:
        texto = texto[:actual.start()] + linea + texto[actual.end():]
    else:
        texto = texto.rstrip("\n") + f"\n{linea}\n"
    env.write_text(texto, encoding="utf-8")


def preparar_env(raiz=RAIZ):
    """Deja el .env listo: lo crea desde .env.example y genera la SECRET_KEY si falta.

    La SECRET_KEY firma las cookies de sesión: se genera una al azar en cada PC y nunca sale
    del .env (el ZIP de entrega no lo lleva). Devuelve la lista de lo que hizo."""
    env, ejemplo = raiz / ".env", raiz / ".env.example"
    hechos = []
    if not env.exists():
        if not ejemplo.exists():
            raise FileNotFoundError("En la carpeta del proyecto no están ni .env ni .env.example.")
        shutil.copyfile(ejemplo, env)
        hechos.append("Se creó .env a partir de .env.example")
    if not valor_en_env(env, "SECRET_KEY"):
        fijar_en_env(env, "SECRET_KEY", secrets.token_hex(32))
        hechos.append("Se generó una SECRET_KEY nueva y se guardó en .env")
    return hechos


def aviso_de_fechas(estado, hoy):
    """La semilla pone las salidas a partir del día en que se cargó la base. Si se cargó otro
    día, la demostración ya no tiene las salidas «de hoy»: se avisa (no impide arrancar)."""
    cargada = estado.get("cargada_en")
    recargar = "Antes de presentar:  flask bd reiniciar --si  (pone las fechas de la demo en HOY)."
    if cargada and cargada.date() < hoy:
        dias = (hoy - cargada.date()).days
        return (f"La base se cargó el {cargada:%d/%m/%Y} (hace {dias} día(s)): las salidas de la "
                f"semilla están corridas.\n{recargar}")
    if not estado.get("salidas_desde_hoy"):
        return f"No hay salidas de hoy en adelante.\n{recargar}"
    return None


def puerto_ocupado(puerto):
    """True si algo ya escucha en ese puerto de esta PC (por ejemplo, otra ventana del servidor)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", puerto)) == 0


def ip_en_la_red():
    """IP de esta PC en la red local (para abrir la app desde un celular), o None."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))     # UDP: no envía nada, solo elige la interfaz
            return s.getsockname()[0]
    except OSError:
        return None


def revisar(opciones):
    """Revisa todo en orden y se detiene en el primer problema.

    Devuelve la configuración de la app (un dict) si se puede arrancar, o None."""
    print("Titicaca Vivo · revisión antes de arrancar")
    for paso in (revisar_python, revisar_dependencias):
        ok, texto = paso()
        (bien if ok else mal)(texto)
        if not ok:
            return None

    try:
        hechos = preparar_env()
    except (OSError, UnicodeDecodeError) as error:
        mal(f"No se pudo preparar el archivo .env: {error}\n"
            "Qué hacer: copia .env.example como .env (INSTRUCCIONES.txt, PASO 3).")
        return None
    for hecho in hechos:
        bien(hecho)

    # Recién ahora se importa la app: config.py lee el .env al importarse.
    from app import diagnostico
    from app.config import Config

    config = {clave: getattr(Config, clave) for clave in dir(Config) if clave.isupper()}
    bien(f"Archivo .env con SECRET_KEY (entorno {config['ENTORNO']})")

    problema, estado = diagnostico.revisar(config)
    if estado.get("version"):
        bien(f"MySQL responde en {config['BD_HOST']}:{config['BD_PUERTO']} "
             f"(MariaDB {estado['version'].split('-')[0]})")
    if problema:
        mal(problema)
        return None
    bien(f"Base {config['BD_NOMBRE']}: {estado['tablas']} tablas, {estado['vistas']} vistas, "
         f"{estado['triggers']} triggers y {estado['procedimientos']} procedimiento")
    bien(f"Datos: {estado['filas']} filas · {estado['salidas_hoy']} salida(s) hoy · "
         f"{estado['salidas_desde_hoy']} de hoy en adelante")
    aviso = aviso_de_fechas(estado, date.today())
    if aviso:
        primera, segunda = aviso.splitlines()
        print(f"  [!]  {primera}\n       {segunda}")

    if puerto_ocupado(opciones.puerto):
        texto = (f"El puerto {opciones.puerto} ya está en uso: ¿hay otra ventana con el servidor?\n"
                 "Qué hacer: ciérrala (Ctrl + C) o usa otro:  python servidor.py --puerto 8081")
        if not opciones.revisar:
            mal(texto)
            return None
        print("  [!]  " + texto.splitlines()[0])
    else:
        bien(f"Puerto {opciones.puerto} libre")
    return config


def url_local(opciones):
    host = "127.0.0.1" if opciones.host in (TODA_LA_RED, "localhost") else opciones.host
    return f"http://{host}:{opciones.puerto}"


def mostrar_aviso(opciones, config):
    url = url_local(opciones)
    linea = "=" * 66
    print(linea)
    print(f"  Titicaca Vivo {config['VERSION']} · servidor encendido")
    print(f"  Abre en el navegador:  {url}")
    print(f"  Panel del personal:    {url}/entrar")
    if config["ENTORNO"] != "produccion":
        print("      admin / Admin-Titicaca26    ·    operador / Operador-Titicaca26")
        print("      (los 6 usuarios y las reservas de prueba están en USUARIOS_DEMO.txt)")
        if config.get("CORREO_SIMULAR"):
            print("  ¿Olvidaste tu contraseña?: el código de 6 dígitos aparece AQUÍ, en esta")
            print("      ventana ([CORREO SIMULADO]), porque el correo está en modo simulación.")
    if config.get("RESPALDO_AUTOMATICO"):
        horas = config.get("RESPALDO_CADA_HORAS", 24)
        print(f"  Respaldo automático: cada {horas} h en la carpeta respaldos "
              "(Panel → Respaldos)")
    ip = ip_en_la_red() if opciones.host == TODA_LA_RED else None
    if ip:
        print(f"  Desde un celular de la misma red:  http://{ip}:{opciones.puerto}")
    elif opciones.host != TODA_LA_RED:
        print("  Para abrirla desde un celular:  python servidor.py --host 0.0.0.0")
    print("  Para detenerlo: Ctrl + C en esta ventana")
    print(linea, flush=True)


def main(argv=None):
    argumentos = argparse.ArgumentParser(description="Servidor waitress de Titicaca Vivo")
    argumentos.add_argument("--host", default="127.0.0.1", help="0.0.0.0 para toda la red local")
    argumentos.add_argument("--puerto", type=int, default=8080)
    argumentos.add_argument("--hilos", type=int, default=8)
    argumentos.add_argument("--abrir", action="store_true", help="abre el navegador al arrancar")
    argumentos.add_argument("--revisar", action="store_true",
                            help="solo revisa que todo esté listo; no arranca el servidor")
    opciones = argumentos.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        # En la consola de Windows los acentos salen bien solos; si la salida va a un archivo o a
        # otro programa, se escribe en UTF-8. Y un carácter raro nunca hace fallar el aviso.
        codificacion = {} if sys.stdout.isatty() else {"encoding": "utf-8"}
        sys.stdout.reconfigure(errors="replace", **codificacion)

    config = revisar(opciones)
    if config is None:
        print("\n  No se arrancó el servidor. El paso a paso está en INSTRUCCIONES.txt.")
        return 1
    if opciones.revisar:
        print("\n  Todo listo. Para arrancar:  python servidor.py   (o doble clic en INICIAR.bat)")
        return 0

    from waitress import serve

    from app import crear_app, tareas

    app = crear_app()
    # Cada 5 min vence las reservas sin pago a tiempo; cada hora revisa el respaldo automático
    tareas.iniciar(app)
    mostrar_aviso(opciones, config)
    app.logger.info("waitress escuchando en http://%s:%s con %s hilos",
                    opciones.host, opciones.puerto, opciones.hilos)
    if opciones.abrir:
        threading.Timer(1.5, webbrowser.open, [url_local(opciones)]).start()
    try:
        serve(app, host=opciones.host, port=opciones.puerto, threads=opciones.hilos,
              ident="titicaca-vivo")
    except KeyboardInterrupt:
        print("\n  Servidor detenido.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""ZIP de la entrega (F8): todo el proyecto SIN el .env, sin entornos virtuales, sin cachés y sin
registros. Por defecto queda FUERA de la carpeta del proyecto, en ../entrega/.

    python scripts/empaquetar.py                      # → ../entrega/titicaca_vivo-<VERSION>.zip
    python scripts/empaquetar.py --destino C:\\ruta\\entrega.zip

Antes de escribir, revisa que ningún archivo lleve un valor secreto del .env (SECRET_KEY,
BD_CONTRASENA): si encuentra uno, no arma el ZIP.
"""

import argparse
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.config import Config  # noqa: E402

# Carpetas que no van, estén donde estén (entornos virtuales, cachés, control de versiones, los
# respaldos de la base, que llevan datos personales, y la configuración local del asistente).
CARPETAS_FUERA = {".venv", "venv", "env", "__pycache__", ".pytest_cache", ".ruff_cache",
                  "htmlcov", ".git", "logs", "entrega", ".claude", "respaldos", "subidas"}
# Archivos que no van: el .env (secretos), la cobertura y los guiones del video del equipo (son
# para grabar la exposición, no parte del programa).
ARCHIVOS_FUERA = {".env", ".coverage", "DIALOGO_VIDEO.txt", "GUION_VIDEO.md",
                  "DEMO_BASE_DE_DATOS.txt", "TAREAS_EQUIPO.txt", "TAREAS_ZULEMA.txt",
                  "TAREAS_SHANELL.txt"}
EXTENSIONES_FUERA = {".pyc", ".pyo", ".log", ".zip"}
SECRETOS = ("SECRET_KEY", "BD_CONTRASENA")


def archivos(raiz=RAIZ):
    """Rutas (relativas a la raíz) de lo que va en el ZIP, en orden alfabético."""
    lista = []
    for ruta in raiz.rglob("*"):
        relativa = ruta.relative_to(raiz)
        if not ruta.is_file() or CARPETAS_FUERA & set(relativa.parts[:-1]):
            continue
        nombre = relativa.name
        if nombre in ARCHIVOS_FUERA or ruta.suffix in EXTENSIONES_FUERA:
            continue
        if nombre.startswith(".env") and nombre != ".env.example":     # .env.local, .env.prod…
            continue
        lista.append(relativa)
    return sorted(lista, key=lambda r: r.as_posix())


def secretos_del_env(raiz=RAIZ):
    """Los valores de SECRET_KEY y BD_CONTRASENA del .env (los que no deben salir)."""
    env = raiz / ".env"
    if not env.exists():
        return []
    valores = []
    for linea in env.read_text(encoding="utf-8").splitlines():
        clave, _, valor = linea.partition("=")
        if clave.strip() in SECRETOS and len(valor.strip()) >= 6:
            valores.append(valor.strip())
    return valores


def archivos_con_secretos(lista, raiz=RAIZ):
    """Los archivos de la lista que contienen algún valor secreto del .env."""
    secretos = [s.encode("utf-8") for s in secretos_del_env(raiz)]
    return [r for r in lista if any(s in (raiz / r).read_bytes() for s in secretos)]


def armar(destino, raiz=RAIZ):
    """Escribe el ZIP (todo dentro de la carpeta titicaca_vivo/). Devuelve la lista de archivos."""
    lista = archivos(raiz)
    con_secretos = archivos_con_secretos(lista, raiz)
    if con_secretos:
        raise SystemExit(f"No se armó el ZIP: estos archivos llevan un secreto del .env: "
                         f"{[r.as_posix() for r in con_secretos]}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w", compression=zipfile.ZIP_DEFLATED) as zip_:
        for relativa in lista:
            zip_.write(raiz / relativa, "titicaca_vivo/" + relativa.as_posix())
    return lista


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--destino", type=Path,
                        default=RAIZ.parent / "entrega" / f"titicaca_vivo-{Config.VERSION}.zip")
    destino = parser.parse_args().destino.resolve()
    lista = armar(destino)
    print(f"{destino}: {len(lista)} archivos, {destino.stat().st_size / 1024:.0f} KB")
    print("Sin .env, sin entorno virtual, sin cachés ni registros; sin secretos del .env.")


if __name__ == "__main__":
    main()

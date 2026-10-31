"""Genera los hash bcrypt de los usuarios demo y los escribe en database/03_datos.sql.

Así el .sql trae los hash ya calculados y se puede importar en phpMyAdmin
sin ejecutar Python. Las contraseñas demo están documentadas en el README.

Uso (desde la carpeta titicaca_vivo):
    python scripts/generar_hashes.py            # reescribe el bloque de usuarios
    python scripts/generar_hashes.py --mostrar  # solo imprime el INSERT, no toca el archivo
"""

import argparse
import re
import sys
from pathlib import Path

import bcrypt

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO_SEMILLA = RAIZ / "database" / "03_datos.sql"
INICIO, FIN = "-- [[USUARIOS_INICIO]]", "-- [[USUARIOS_FIN]]"
COSTO_BCRYPT = 12

# Cada fila: (id, rol_id, nombre_usuario, nombre_completo, correo, telefono,
#             comunidad_id, licencia, contraseña)
# Personas ficticias. Roles: 1 admin, 2 operador, 3 guia, 4 capitan, 5 residente (v2.9).
USUARIOS_DEMO = [
    (1, 1, "admin", "Lucía Mamani Quispe", "admin@titicaca-vivo.example", "900000101",
     None, None, "Admin-Titicaca26"),
    (2, 2, "operador", "Jorge Apaza Huanca", "operador@titicaca-vivo.example", "900000102",
     None, None, "Operador-Titicaca26"),
    (3, 3, "guia.elena", "Elena Yucra Cruz", "elena.yucra@titicaca-vivo.example", "900000103",
     3, None, "Guia-Titicaca26"),
    (4, 3, "guia.marco", "Marco Cutipa Flores", None, "900000104",
     4, None, "Guia-Titicaca26"),
    (5, 4, "capitan.teodoro", "Teodoro Choque Pari", None, "900000105",
     None, "LIC-PUN-00123", "Capitan-Titicaca26"),
    (6, 4, "capitan.fermin", "Fermín Ccama Turpo", None, "900000106",
     None, "LIC-PUN-00456", "Capitan-Titicaca26"),
    (7, 5, "residente.juana", "Juana Machaca Huatta", None, "900000107",
     2, None, "Residente-Titicaca26"),
    (8, 5, "residente.felix", "Félix Cari Ticona", "felix.cari@titicaca-vivo.example", "900000108",
     3, None, "Residente-Titicaca26"),
    (9, 5, "residente.sonia", "Sonia Suaña Lujano", None, "900000109",
     1, None, "Residente-Titicaca26"),
]


def literal_sql(valor):
    """Convierte un valor de Python en un literal SQL (solo para este archivo de semilla)."""
    if valor is None:
        return "NULL"
    if isinstance(valor, int):
        return str(valor)
    return "'" + str(valor).replace("\\", "\\\\").replace("'", "''") + "'"


def generar_insert():
    filas = []
    for (id_, rol_id, usuario, nombre, correo, telefono, comunidad_id, licencia,
         contrasena) in USUARIOS_DEMO:
        hash_ = bcrypt.hashpw(contrasena.encode("utf-8"),
                              bcrypt.gensalt(rounds=COSTO_BCRYPT)).decode("ascii")
        valores = [id_, rol_id, usuario, nombre, correo, telefono, hash_, comunidad_id,
                   licencia, 1, "@hoy - INTERVAL 200 DAY"]
        textos = [literal_sql(v) for v in valores[:-1]] + [valores[-1]]
        filas.append("(" + ", ".join(textos) + ")")
    return (
        "INSERT INTO usuario (id, rol_id, nombre_usuario, nombre_completo, correo, telefono,\n"
        "                     hash_contrasena, comunidad_id, licencia_navegacion, activo,\n"
        "                     creado_en) VALUES\n"
        + ",\n".join(filas) + ";"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mostrar", action="store_true", help="solo imprime el INSERT")
    args = parser.parse_args()

    insert = generar_insert()
    if args.mostrar:
        print(insert)
        return 0

    texto = ARCHIVO_SEMILLA.read_text(encoding="utf-8")
    patron = re.compile(re.escape(INICIO) + r".*?" + re.escape(FIN), re.S)
    if not patron.search(texto):
        print(f"No encontré los marcadores {INICIO} / {FIN} en {ARCHIVO_SEMILLA}", file=sys.stderr)
        return 1
    bloque = f"{INICIO}\n{insert}\n{FIN}"
    texto = patron.sub(lambda _: bloque, texto, count=1)
    ARCHIVO_SEMILLA.write_text(texto, encoding="utf-8", newline="\n")
    print(f"{len(USUARIOS_DEMO)} usuarios escritos en {ARCHIVO_SEMILLA.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

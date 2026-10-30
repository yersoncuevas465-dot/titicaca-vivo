"""EXPLAIN de las 3 consultas más importantes (sección 11: "muestra el EXPLAIN de las 3 más
importantes"). Se corre contra la base del .env (o la que diga --base) y escribe el resultado.

    python scripts/explicar_consultas.py                       # en pantalla
    python scripts/explicar_consultas.py --salida docs/evidencias/f7-explain.txt

Las 3 consultas son las mismas que usa el modelo:
1. RN-01/RN-02: contar los ocupados de una salida (se hace en CADA reserva, con bloqueo).
2. Plata: las salidas de un día con sus cupos (la portada y /salidas, las más visitadas).
3. RN-10: elegir la familia anfitriona que toca (rotación justa).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import bd  # noqa: E402
from app.config import Config  # noqa: E402

CONSULTAS = {
    "1. Ocupados de una salida (RN-01/RN-02, en cada reserva)": (
        """
        SELECT COUNT(*) AS ocupados
        FROM reserva_pasajero rp
        JOIN reserva r ON r.id = rp.reserva_id
        WHERE r.salida_id = %s
          AND (r.estado IN ('confirmada','pagada','abordada')
               OR (r.estado = 'pendiente_pago' AND r.vence_en > NOW()))
        """,
        (10,),
    ),
    "2. Salidas de un día con sus cupos (portada y /salidas)": (
        """
        SELECT v.salida_id, v.fecha_hora_zarpe, v.ruta_nombre, v.cupo, v.ocupados, v.libres,
               v.estado_publico
        FROM v_disponibilidad_salida v
        WHERE v.fecha_hora_zarpe >= CURDATE()
          AND v.fecha_hora_zarpe <  CURDATE() + INTERVAL 1 DAY
          AND v.estado <> 'cancelada'
        ORDER BY v.fecha_hora_zarpe
        """,
        (),
    ),
    "3. Familia que toca por rotación (RN-10)": (
        """
        SELECT f.id,
               (SELECT COUNT(*) FROM hospedaje h
                WHERE h.familia_id = f.id AND h.estado IN ('asignado','cumplido')
                  AND h.fecha_noche BETWEEN CURDATE() - INTERVAL 30 DAY
                                        AND CURDATE() - INTERVAL 1 DAY
               ) AS noches_30_dias,
               (SELECT MAX(h.fecha_noche) FROM hospedaje h
                WHERE h.familia_id = f.id AND h.estado IN ('asignado','cumplido')
                  AND h.fecha_noche < CURDATE()) AS ultima_noche
        FROM familia_anfitriona f
        WHERE f.comunidad_id = %s AND f.activa = 1 AND f.capacidad_personas >= %s
          AND NOT EXISTS (SELECT 1 FROM hospedaje h
                          WHERE h.familia_id = f.id AND h.fecha_noche = CURDATE()
                            AND h.estado IN ('asignado','cumplido'))
        ORDER BY noches_30_dias, ultima_noche IS NOT NULL, ultima_noche, f.id
        LIMIT 1
        """,
        (3, 2),
    ),
}
COLUMNAS = ("id", "select_type", "table", "type", "possible_keys", "key", "key_len", "ref", "rows",
            "Extra")


def explicar(conexion):
    """Devuelve {título: [filas del EXPLAIN]} de las 3 consultas."""
    resultado = {}
    with conexion.cursor() as cursor:
        # Estadísticas al día: el optimizador elige el plan con ellas.
        cursor.execute("ANALYZE TABLE salida, reserva, reserva_pasajero, hospedaje, "
                       "familia_anfitriona")
        cursor.fetchall()
        for titulo, (sql, parametros) in CONSULTAS.items():
            cursor.execute("EXPLAIN " + sql, parametros)
            resultado[titulo] = cursor.fetchall()
    return resultado


def _texto(valor):
    return "NULL" if valor is None else str(valor)


def como_texto(resultado):
    lineas = []
    for titulo, filas in resultado.items():
        lineas += ["", titulo, "-" * len(titulo)]
        celdas = [[_texto(f.get(c)) for c in COLUMNAS] for f in filas]
        anchos = [max(len(c), *(len(fila[i]) for fila in celdas)) for i, c in enumerate(COLUMNAS)]
        lineas.append(" | ".join(c.ljust(anchos[i]) for i, c in enumerate(COLUMNAS)))
        for fila in celdas:
            lineas.append(" | ".join(valor.ljust(anchos[i]) for i, valor in enumerate(fila)))
    return "\n".join(lineas) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", help="nombre de la base (por defecto, BD_NOMBRE del .env)")
    parser.add_argument("--salida", help="archivo donde guardar el resultado")
    args = parser.parse_args()
    config = {k: getattr(Config, k) for k in dir(Config) if k.startswith("BD_")}
    conexion = bd.conectar(config, base=args.base)
    try:
        texto = como_texto(explicar(conexion))
    finally:
        conexion.close()
    if args.salida:
        Path(args.salida).write_text(texto, encoding="utf-8")
    print(texto)


if __name__ == "__main__":
    main()

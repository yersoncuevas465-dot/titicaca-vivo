"""Nivel Plata: cada pantalla lee de la base y no hay datos del negocio fijos en el HTML.

Tres pruebas complementarias:
1. Ninguna plantilla tiene escrito un dato que esté en la base.
2. Si se cambia un dato en la base, la página muestra el valor nuevo.
3. Si la base no responde, ninguna página pública puede mostrarse.
"""

from pathlib import Path

import pymysql
import pytest

from app import crear_app
from app.config import ConfigPruebas
from tests.conftest import ejecutar_y_confirmar, precio_en_pagina

PLANTILLAS = Path(__file__).resolve().parent.parent / "app" / "plantillas"


def datos_del_negocio(app):
    """Textos que están en la base y que NO deberían aparecer escritos en una plantilla."""
    from app import bd

    conexion = bd.conectar(app.config)
    try:
        with conexion.cursor() as cursor:
            # Devuelve nombres y textos del negocio de varias tablas en una sola lista.
            cursor.execute(
                """
                SELECT nombre AS texto FROM comunidad
                UNION SELECT nombre FROM ruta
                UNION SELECT codigo FROM ruta
                UNION SELECT muelle_salida FROM ruta
                UNION SELECT nombre FROM embarcacion
                UNION SELECT matricula FROM embarcacion
                UNION SELECT nombre_familia FROM familia_anfitriona
                UNION SELECT titulo FROM alerta_lago
                UNION SELECT nombre FROM tipo_pasajero
                UNION SELECT nombre FROM temporada
                UNION SELECT codigo FROM reserva
                """
            )
            return [fila["texto"] for fila in cursor.fetchall()]
    finally:
        conexion.close()


def test_ninguna_plantilla_tiene_datos_del_negocio_escritos(app):
    textos = datos_del_negocio(app)
    assert len(textos) > 50
    encontrados = []
    for archivo in PLANTILLAS.rglob("*.html"):
        contenido = archivo.read_text(encoding="utf-8")
        encontrados += [(archivo.name, t) for t in textos if t in contenido]
    assert encontrados == [], f"Datos fijos en plantillas: {encontrados}"


def test_ningun_precio_escrito_a_mano_en_las_plantillas():
    import re

    for archivo in PLANTILLAS.rglob("*.html"):
        assert not re.search(r"S/\s*\d", archivo.read_text(encoding="utf-8")), archivo.name


@pytest.mark.parametrize("sql_cambio, sql_vuelta, url, esperado", [
    ("UPDATE comunidad SET nombre = 'Taquile (prueba Plata)' WHERE slug = 'taquile'",
     "UPDATE comunidad SET nombre = 'Taquile' WHERE slug = 'taquile'",
     "/comunidades", "Taquile (prueba Plata)"),
    ("UPDATE salida SET cupo = 24 WHERE id = 10",
     "UPDATE salida SET cupo = 25 WHERE id = 10",
     "/salidas/10", "4 de 24 lugares ocupados"),
    ("UPDATE tarifa SET precio_base = 85.50 WHERE ruta_id = 2 AND tipo_pasajero_id = 1 "
     "AND vigente_desde = '2026-01-01'",
     "UPDATE tarifa SET precio_base = 80.00 WHERE ruta_id = 2 AND tipo_pasajero_id = 1 "
     "AND vigente_desde = '2026-01-01'",
     "/salidas/10", ("precio", 10, "85.50")),           # con el recargo de temporada, si hay
    ("UPDATE alerta_lago SET titulo = 'Oleaje (prueba Plata)' WHERE id = 1",
     "UPDATE alerta_lago SET titulo = 'Oleaje fuerte en el sector de Amantaní' WHERE id = 1",
     "/", "Oleaje (prueba Plata)"),
    ("UPDATE familia_anfitriona SET capacidad_personas = 9 WHERE id = 1",
     "UPDATE familia_anfitriona SET capacidad_personas = 6 WHERE id = 1",
     "/comunidades/amantani", "Hasta 9 personas"),
])
def test_cambiar_un_dato_en_la_base_cambia_la_pagina(app, cliente, sql_cambio, sql_vuelta, url, esperado):
    if isinstance(esperado, tuple):                  # un precio: «S/ 85.50» o, en temporada, más
        esperado = precio_en_pagina(app, *esperado[1:])
    assert esperado not in cliente.get(url).get_data(True)
    ejecutar_y_confirmar(app, sql_cambio)
    try:
        assert esperado in cliente.get(url).get_data(True)       # recargar muestra el dato nuevo
    finally:
        ejecutar_y_confirmar(app, sql_vuelta)


@pytest.mark.parametrize("url", ["/", "/salidas", "/salidas/10", "/comunidades",
                                 "/comunidades/amantani", "/alertas"])
def test_sin_base_ninguna_pagina_publica_puede_mostrarse(url):
    class ConfigSinBase(ConfigPruebas):
        BD_PUERTO = 1

    app = crear_app(ConfigSinBase)
    app.config["PROPAGATE_EXCEPTIONS"] = False
    respuesta = app.test_client().get(url)
    assert respuesta.status_code == 500          # no hay datos de respaldo escritos en el HTML


def test_consultas_por_pagina_no_crecen_con_los_datos(app, cliente, monkeypatch):
    """Sin N+1: cada página hace un número fijo de consultas, sin importar cuántas filas haya."""
    contador = {"n": 0}
    original = pymysql.cursors.Cursor.execute

    def contar(self, consulta, args=None):
        # Solo los SELECT (el "SET time_zone..." de cada conexión nueva no es una consulta de datos)
        if consulta.lstrip().upper().startswith("SELECT"):
            contador["n"] += 1
        return original(self, consulta, args)

    monkeypatch.setattr(pymysql.cursors.Cursor, "execute", contar)
    # La salida y la comunidad llevan su mapa (v2.1): 2 consultas fijas más, las mismas que usa la
    # portada (comunidades y paradas de todas las rutas en UNA consulta), tenga 1 o 50 paradas.
    # La portada suma 1 desde la v2.9: los 3 productos más nuevos (LIMIT), haya 3 o 300.
    esperadas = {"/": 6, "/salidas": 3, "/salidas/10": 7, "/comunidades": 2,
                 "/comunidades/amantani": 6, "/alertas": 1}
    for url, maximo in esperadas.items():
        contador["n"] = 0
        assert cliente.get(url).status_code == 200
        assert contador["n"] <= maximo, (url, contador["n"])

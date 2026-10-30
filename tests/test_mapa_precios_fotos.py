"""Servicio del mapa, regla de precio RN-04 y preparación de fotos."""

from decimal import Decimal

import pytest
from PIL import Image

from app import bd
from app.modelos import tarifa
from app.servicios import mapa


def test_proyeccion_de_las_esquinas():
    assert mapa.proyectar(mapa.LAT_NORTE, mapa.LON_OESTE) == (0, 0)
    assert mapa.proyectar(mapa.LAT_SUR, mapa.LON_ESTE) == (mapa.ANCHO, mapa.ALTO)


def test_una_unidad_del_mapa_son_unos_100_metros():
    # 0.1° de latitud ≈ 11 km → unas 110 unidades
    _, y1 = mapa.proyectar(-15.70, -69.80)
    _, y2 = mapa.proyectar(-15.80, -69.80)
    assert 105 <= y2 - y1 <= 115


def test_ruta_que_sale_de_la_bahia_pasa_por_la_boca():
    boca = mapa.proyectar(*mapa.BOCA_BAHIA)
    uros, amantani, luquina = (98, 283), (374, 115), (224, 270)
    assert mapa.trazo_de_ruta([uros, amantani]) == [uros, boca, amantani]
    assert mapa.trazo_de_ruta([uros, luquina]) == [uros, luquina]          # se queda en la bahía


def test_construir_mapa():
    comunidades = [
        {"slug": "a", "nombre": "A", "idioma_originario": "quechua", "latitud": Decimal("-15.70"), "longitud": Decimal("-69.65")},
        {"slug": "b", "nombre": "B", "idioma_originario": "aimara", "latitud": None, "longitud": None},
    ]
    paradas = [
        {"ruta_id": 1, "codigo": "R1", "nombre": "Ruta 1", "slug": "a", "latitud": Decimal("-15.70"), "longitud": Decimal("-69.65")},
    ]
    datos = mapa.construir(comunidades, paradas)
    assert [c["slug"] for c in datos["comunidades"]] == ["a"]               # sin coordenadas: no se dibuja
    assert datos["comunidades"][0]["ancla"] == "end"                        # cerca del borde: texto a la izquierda
    ruta = datos["rutas"][0]
    assert ruta["puntos"][0] == mapa.proyectar(*mapa.PUNO)                 # toda ruta sale de Puno
    assert ruta["color"] == mapa.COLORES_RUTA[0]


@pytest.mark.parametrize("base, recargo, esperado", [
    ("80.00", "0", "80.00"),
    ("80.00", "15", "92.00"),
    ("33.33", "10", "36.66"),       # 36.663 → 36.66
    ("0.05", "10", "0.06"),         # 0.055 → 0.06 (la mitad sube, igual que ROUND en MariaDB)
    ("150.00", None, "150.00"),     # sin temporada
])
def test_calcular_precio(base, recargo, esperado):
    assert tarifa.calcular_precio(Decimal(base), recargo) == Decimal(esperado)


def test_precio_de_una_salida_en_temporada(app):
    """RN-04: si la fecha de la salida cae en una temporada, se aplica su recargo."""
    with app.test_request_context():
        conexion = bd.obtener_conexion()
        with conexion.cursor() as cursor:
            # Temporada de prueba que contiene la fecha de la salida 10 (se deshace al terminar).
            cursor.execute(
                "INSERT INTO temporada (nombre, fecha_inicio, fecha_fin, recargo_porcentaje) "
                "SELECT 'Temporada de prueba', DATE(fecha_hora_zarpe), DATE(fecha_hora_zarpe), 20 "
                "FROM salida WHERE id = 10"
            )
        precios = {p["codigo"]: p for p in tarifa.precios_para_salida(10)}
        assert precios["adulto_nacional"]["precio"] == Decimal("96.00")        # 80 × 1.20
        assert precios["adulto_extranjero"]["precio"] == Decimal("144.00")     # 120 × 1.20
        assert precios["nino"]["temporada"] == "Temporada de prueba"
        conexion.rollback()
        assert tarifa.precios_para_salida(10)[0]["precio"] == Decimal("80.00")


def test_tarifa_vigente_es_la_mas_reciente(app):
    """Con dos tarifas vigentes, gana la de vigente_desde más reciente."""
    with app.test_request_context():
        conexion = bd.obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute(
                "INSERT INTO tarifa (ruta_id, tipo_pasajero_id, precio_base, vigente_desde) "
                "VALUES (2, 1, 99.00, CURDATE() - INTERVAL 1 DAY)"
            )
        precios = {p["codigo"]: p for p in tarifa.precios_para_salida(10)}
        assert precios["adulto_nacional"]["precio"] == Decimal("99.00")
        conexion.rollback()


def test_preparar_foto_deja_webp_de_40_kb_o_menos(tmp_path, monkeypatch):
    from scripts import preparar_foto

    monkeypatch.setattr(preparar_foto, "CARPETA", tmp_path)
    origen = tmp_path / "grande.png"
    Image.effect_mandelbrot((2000, 1500), (-2, -1.5, 1, 1.5), 60).convert("RGB").save(origen)
    destino, peso, _ = preparar_foto.preparar(origen, "prueba")
    assert peso <= 40 * 1024
    with Image.open(destino) as resultado:
        assert resultado.size == (640, 400) and resultado.format == "WEBP"
    with pytest.raises(ValueError):
        preparar_foto.preparar(origen, "../fuera")

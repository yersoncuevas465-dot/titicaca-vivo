"""El «desde» de cada ruta es el precio de ADULTO, no el de niño (observación del docente,
Práctica 9: «El desde engaña al turista»)."""

from app.modelos import ruta
from tests.conftest import consultar_valor

TARIFA_VIGENTE = """SELECT MIN(t.precio_base) AS precio FROM tarifa t
                    JOIN ruta r ON r.id = t.ruta_id
                    JOIN tipo_pasajero tp ON tp.id = t.tipo_pasajero_id
                    WHERE r.codigo = %s AND tp.codigo = %s
                      AND t.vigente_desde <= CURDATE()
                      AND (t.vigente_hasta IS NULL OR t.vigente_hasta >= CURDATE())"""


def test_el_desde_de_cada_ruta_es_el_precio_de_adulto(app):
    with app.app_context():
        uros = next(r for r in ruta.listar_activas() if r["codigo"] == "URO-MD")
    adulto = consultar_valor(app, TARIFA_VIGENTE, ("URO-MD", "adulto_nacional"))
    nino = consultar_valor(app, TARIFA_VIGENTE, ("URO-MD", "nino"))
    assert uros["desde"] == adulto          # el adulto que paga menos
    assert uros["desde"] > nino             # y no el precio del niño


def test_la_portada_dice_adulto_desde(cliente):
    assert "Adulto desde" in cliente.get("/").get_data(True)
    cliente.get("/idioma/en")
    assert "Adults from" in cliente.get("/").get_data(True)

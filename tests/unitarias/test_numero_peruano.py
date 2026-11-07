"""Números al estilo peruano que no son soles ni porcentajes: el tipo de cambio de SUNAT y el
promedio de las reseñas; y los dólares sin coma de miles (observación del docente: «cifras al
estilo inglés»). No usan la base."""

from decimal import Decimal

import pytest

from app.servicios.formato import dolares, numero


@pytest.mark.parametrize(("valor", "decimales", "esperado"), [
    (Decimal("3.461"), None, "3,461"),           # tipo de cambio: se ve igual que en SUNAT
    (Decimal("3.5"), None, "3,5"),
    (Decimal("4.5000"), 1, "4,5"),               # promedio de reseñas que llega de AVG()
    (4.56, 1, "4,6"),
    (Decimal("1250"), None, "1 250"),        # miles con espacio que no se corta
    (None, None, ""),
])
def test_un_numero_se_escribe_al_estilo_peruano(valor, decimales, esperado):
    assert numero(valor, decimales) == esperado


def test_los_dolares_no_llevan_coma_de_miles():
    assert dolares(Decimal("4000"), {"venta": Decimal("3.461")}) == "US$ 1 156"
    assert dolares(Decimal("80.00"), {"venta": Decimal("3.5")}) == "US$ 23"

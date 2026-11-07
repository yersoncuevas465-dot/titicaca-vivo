"""El turista escribe o elige su país por el NOMBRE y el sistema guarda el código (observación
del docente, Práctica 9: «Un turista no sabe que Francia es FR»). No usa la base."""

import pytest

from app.servicios.paises import codigo_de


@pytest.mark.parametrize("escrito, codigo", [
    ("Perú", "PE"), ("peru", "PE"), ("  Francia ", "FR"), ("ESTADOS UNIDOS", "US"),
    ("PE", "PE"), ("fr", "FR"),
])
def test_el_pais_por_su_nombre_o_por_su_codigo(escrito, codigo):
    assert codigo_de(escrito) == codigo


def test_un_pais_que_no_existe_no_se_inventa():
    assert codigo_de("Narnia") == "NARNIA"
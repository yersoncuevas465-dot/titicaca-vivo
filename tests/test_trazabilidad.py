"""La matriz de trazabilidad (docs/trazabilidad.md) se verifica sola: cada regla RN-01 a RN-15 tiene
su fila, y existe cada prueba, archivo, función, trigger y página que cita. Si alguien borra o
renombra algo de lo que la matriz promete, esta prueba falla (igual que test_documentacion.py hace
con las consultas explicadas)."""

import re
from pathlib import Path

import pytest
from werkzeug.exceptions import MethodNotAllowed, NotFound

RAIZ = Path(__file__).resolve().parent.parent
MATRIZ = (RAIZ / "docs" / "trazabilidad.md").read_text(encoding="utf-8")
CITAS = re.findall(r"`([^`\n]+)`", MATRIZ)                     # todo lo que va entre comillas `


def test_cada_regla_de_negocio_tiene_su_fila():
    faltan = [f"RN-{n:02d}" for n in range(1, 16) if f"| **RN-{n:02d}**" not in MATRIZ]
    assert faltan == []


def test_cada_prueba_citada_existe():
    codigo = "\n".join(p.read_text(encoding="utf-8") for p in (RAIZ / "tests").glob("test_*.py"))
    definidas = set(re.findall(r"def (test_\w+)", codigo))
    citadas = {m.group(0) for cita in CITAS for m in [re.match(r"test_\w+", cita)] if m}
    assert len(citadas) > 80
    assert sorted(citadas - definidas) == []


def _existe(archivo, nombre):
    texto = (RAIZ / archivo).read_text(encoding="utf-8")
    if archivo.endswith(".py"):
        return re.search(rf"(?m)^\s*(def|class) {nombre}\b|^{nombre}\s*=", texto) is not None
    return re.search(rf"\b{nombre}\b", texto) is not None


def test_cada_archivo_y_funcion_citados_existen():
    rotas = []
    for cita in CITAS:
        archivo, _, nombre = cita.partition("::")
        if not re.fullmatch(r"(app|database|scripts|tests|docs)/[\w/.-]*|servidor\.py", archivo):
            continue
        if not (RAIZ / archivo).exists():
            rotas.append(f"no existe {archivo}")
        elif nombre and not _existe(archivo, nombre):
            rotas.append(f"{archivo} no tiene {nombre}")
    assert rotas == []


@pytest.fixture
def rutas(app):
    return app.url_map.bind("localhost")


def test_cada_pantalla_citada_existe(rutas):
    pantallas = [c for c in CITAS if re.fullmatch(r"/[\w/.<>-]*", c)]
    assert len(pantallas) > 15
    faltan = []
    for url in pantallas:
        try:
            rutas.match(url)
        except MethodNotAllowed:
            pass                                               # existe, pero solo por POST
        except NotFound:
            faltan.append(url)
    assert faltan == []

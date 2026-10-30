"""F8 · Documentación (sección 15): docs/consultas-explicadas.md tiene al menos 15 SELECT, cada
uno con sus 5 partes, y cada consulta sigue IDÉNTICA a la del código. Si alguien cambia una
consulta y no el documento (o la mueve de línea), esta prueba falla."""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DOCUMENTO = RAIZ / "docs" / "consultas-explicadas.md"
PARTES = ("- **Pantalla:**", "```sql", "**Línea por línea**", "**Ejemplo con la semilla:**",
          "**Índice (EXPLAIN)**")


def sin_espacios(texto):
    return re.sub(r"\s+", " ", texto).strip()


def secciones():
    """[(título, texto de la sección, SQL del bloque ```sql)] de cada consulta del documento."""
    resultado = []
    for seccion in re.split(r"\n### \d+\. ", DOCUMENTO.read_text(encoding="utf-8"))[1:]:
        bloque = re.search(r"```sql\n(.*?)```", seccion, re.S)
        resultado.append((seccion.splitlines()[0], seccion, bloque.group(1) if bloque else ""))
    return resultado


def test_hay_al_menos_15_consultas_con_sus_5_partes():
    lista = secciones()
    assert len(lista) >= 15
    for titulo, seccion, sql in lista:
        assert [p for p in PARTES if p not in seccion] == [], titulo
        assert "SELECT" in sql, titulo


def test_cada_consulta_del_documento_es_identica_a_la_del_codigo():
    archivos = [*(RAIZ / "app" / "modelos").glob("*.py"),
                RAIZ / "database" / "02_vistas_triggers.sql"]
    codigo = sin_espacios(" ".join(a.read_text(encoding="utf-8") for a in archivos))
    distintas = [titulo for titulo, _, sql in secciones() if sin_espacios(sql) not in codigo]
    assert distintas == []


def test_el_enlace_de_cada_consulta_apunta_a_su_linea():
    """«Dónde está: archivo:línea» lleva al comienzo de la consulta (o a la línea anterior)."""
    mal = []
    for titulo, seccion, sql in secciones():
        archivo, linea = re.search(r"\[([\w/.]+):(\d+)\]", seccion).groups()
        lineas = (RAIZ / archivo).read_text(encoding="utf-8").splitlines()
        ventana = "\n".join(lineas[int(linea) - 1:int(linea) + 1])
        if sql.splitlines()[0].strip() not in ventana:
            mal.append(f"{titulo} → {archivo}:{linea}")
    assert mal == []

"""El separador de sentencias SQL y los comandos `flask bd ...`."""

from app import bd, crear_app
from app.config import Config, ConfigPruebas


def test_separa_sentencias_simples():
    assert bd.dividir_sentencias("SELECT 1;\nSELECT 2;") == ["SELECT 1", "SELECT 2"]


def test_no_corta_en_un_punto_y_coma_dentro_de_un_texto():
    sql = "INSERT INTO t VALUES ('a;b', \"c;d\", 'it''s; ok', 'barra \\'; sigue');SELECT 2;"
    assert bd.dividir_sentencias(sql) == [
        "INSERT INTO t VALUES ('a;b', \"c;d\", 'it''s; ok', 'barra \\'; sigue')", "SELECT 2"]


def test_quita_comentarios_pero_no_los_que_estan_dentro_de_un_texto():
    sql = "-- comentario;\nSELECT '--no;' AS a; # otro;\n/* bloque; */ SELECT 3;"
    assert bd.dividir_sentencias(sql) == ["SELECT '--no;' AS a", "SELECT 3"]


def test_respeta_delimiter_para_triggers():
    sql = (
        "DROP TRIGGER IF EXISTS x;\n"
        "DELIMITER $$\n"
        "CREATE TRIGGER x BEFORE INSERT ON t FOR EACH ROW\nBEGIN\n  SET @a = 1;\n  SET @b = 2;\nEND$$\n"
        "DELIMITER ;\n"
        "SELECT 1;\n"
    )
    sentencias = bd.dividir_sentencias(sql)
    assert len(sentencias) == 3
    assert sentencias[1].startswith("CREATE TRIGGER x") and "SET @b = 2;" in sentencias[1]
    assert sentencias[2] == "SELECT 1"


def test_los_scripts_reales_se_dividen_bien():
    carpeta = Config.CARPETA_SQL
    conteo = {
        nombre: len(bd.dividir_sentencias((carpeta / nombre).read_text(encoding="utf-8")))
        for nombre in bd.ORDEN_SCRIPTS
    }
    # 02: 3 SET + 2 vistas + 5 DROP + 4 triggers + 1 procedimiento
    assert conteo["02_vistas_triggers.sql"] == 15
    assert all(n > 0 for n in conteo.values())


def test_flask_bd_contar(app):
    resultado = app.test_cli_runner().invoke(args=["bd", "contar"])
    assert resultado.exit_code == 0
    assert "20 tablas" in resultado.output


def test_flask_bd_reiniciar_recrea_la_base_de_pruebas(app):
    resultado = app.test_cli_runner().invoke(args=["bd", "reiniciar", "--si"])
    assert resultado.exit_code == 0, resultado.output
    assert "03_datos.sql" in resultado.output
    assert "reserva_pasajero       58" in resultado.output


def test_flask_bd_reiniciar_se_niega_en_produccion():
    class ConfigProduccion(ConfigPruebas):
        ENTORNO = "produccion"

    resultado = crear_app(ConfigProduccion).test_cli_runner().invoke(args=["bd", "reiniciar", "--si"])
    assert resultado.exit_code != 0
    assert "producción" in resultado.output


def test_flask_bd_reiniciar_pide_confirmacion(app):
    resultado = app.test_cli_runner().invoke(args=["bd", "reiniciar"], input="n\n")
    assert resultado.exit_code != 0
    assert "BORRARÁ" in resultado.output


def test_nombre_de_base_invalido_se_rechaza():
    import pytest

    with pytest.raises(ValueError):
        bd.reiniciar_base(ConfigPruebas.__dict__ | {"BD_NOMBRE": "x`; DROP DATABASE mysql; --"})


# --- ZIP de la entrega (F8) ----------------------------------------------------------------------

def _proyecto_de_juguete(raiz):
    """Un proyecto mínimo con todo lo que NO debe ir en el ZIP."""
    for ruta, texto in {
        ".env": "SECRET_KEY=clave-super-secreta-123\nBD_CONTRASENA=otra-clave-456\n",
        ".env.example": "SECRET_KEY=\nBD_CONTRASENA=\n",
        ".env.local": "SECRET_KEY=x\n",
        ".coverage": "datos", "app/a.py": "x = 1\n", "app/__pycache__/a.cpython-311.pyc": "b",
        ".venv/Lib/site.py": "", "logs/app.log": "arranque", ".pytest_cache/v": "",
        "docs/leeme.md": "# hola\n",
    }.items():
        archivo = raiz / ruta
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(texto, encoding="utf-8")


def test_el_zip_no_lleva_env_ni_venv_ni_caches_ni_registros(tmp_path):
    from scripts import empaquetar

    _proyecto_de_juguete(tmp_path)
    nombres = [r.as_posix() for r in empaquetar.archivos(tmp_path)]
    assert nombres == [".env.example", "app/a.py", "docs/leeme.md"]


def test_el_zip_no_se_arma_si_un_archivo_lleva_un_secreto_del_env(tmp_path):
    import pytest

    from scripts import empaquetar

    _proyecto_de_juguete(tmp_path)
    (tmp_path / "docs" / "notas.md").write_text("la clave es otra-clave-456", encoding="utf-8")
    with pytest.raises(SystemExit, match="notas.md"):
        empaquetar.armar(tmp_path / "salida" / "entrega.zip", tmp_path)
    assert not (tmp_path / "salida" / "entrega.zip").exists()


def test_el_proyecto_real_se_puede_empaquetar_sin_secretos(tmp_path):
    import zipfile

    from scripts import empaquetar

    lista = empaquetar.armar(tmp_path / "entrega.zip")
    nombres = zipfile.ZipFile(tmp_path / "entrega.zip").namelist()
    assert len(nombres) == len(lista) > 100
    assert "titicaca_vivo/.env.example" in nombres and "titicaca_vivo/README.md" in nombres
    assert "titicaca_vivo/.env" not in nombres
    assert not [n for n in nombres if "__pycache__" in n or n.endswith((".pyc", ".log"))]

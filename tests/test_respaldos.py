"""Respaldos de la base (D-116 a D-118): crear uno y restaurarlo deja la base IDÉNTICA, el
automático, la página del admin, la descarga, el reporte general para Excel, los comandos de
consola y que los respaldos nunca vayan en el ZIP de entrega."""

import io
import os
import re
import time
import zipfile
from pathlib import Path

import pytest

from app import bd, tareas
from app.modelos import respaldo
from scripts import empaquetar
from tests.conftest import consultar_valor, iniciar_sesion, token_csrf

RAIZ = Path(__file__).resolve().parent.parent
SQL_AUTO_INCREMENT = ("SELECT AUTO_INCREMENT FROM information_schema.TABLES "
                      "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'reserva'")


@pytest.fixture
def carpeta(app, tmp_path):
    """Cada prueba guarda sus respaldos en su propia carpeta temporal."""
    anterior = app.config["RESPALDOS_CARPETA"]
    app.config["RESPALDOS_CARPETA"] = tmp_path
    yield tmp_path
    app.config["RESPALDOS_CARPETA"] = anterior


def sumas(app):
    """CHECKSUM de cada tabla, menos la bitácora (que cambia al anotar los respaldos)."""
    conexion = bd.conectar(app.config)
    try:
        with conexion.cursor() as cur:
            cur.execute("CHECKSUM TABLE " + ", ".join(t for t in bd.TABLAS if t != "bitacora"))
            return {fila["Table"]: fila["Checksum"] for fila in cur.fetchall()}
    finally:
        conexion.close()


def bitacora_hasta(app, ultimo_id):
    conexion = bd.conectar(app.config)
    try:
        with conexion.cursor() as cur:
            cur.execute("SELECT * FROM bitacora WHERE id <= %s ORDER BY id", (ultimo_id,))
            return cur.fetchall()
    finally:
        conexion.close()


# --- Crear y restaurar -----------------------------------------------------------------------------

def test_un_respaldo_restaurado_deja_la_base_identica(app, carpeta):
    antes, ultimo = sumas(app), consultar_valor(app, "SELECT MAX(id) FROM bitacora")
    bitacora_antes, auto_incremento = bitacora_hasta(app, ultimo), consultar_valor(app, SQL_AUTO_INCREMENT)
    with app.app_context():
        hecho = respaldo.crear("consola", ip="consola")
    ruta = carpeta / hecho["nombre"]
    texto = ruta.read_text(encoding="utf-8")
    assert hecho["tablas"] == 20 and hecho["filas"] > 200 and hecho["tipo"] == "Consola"
    assert texto.startswith(respaldo.CABECERA) and f"{respaldo.FIN}: 20 tablas" in texto
    assert "DEFINER" not in texto and "DELIMITER $$" in texto        # se restaura con cualquier usuario
    # Los triggers se crean DESPUÉS de cargar los datos: no frenan la carga
    assert texto.index("INSERT INTO `reserva_pasajero`") < texto.index("CREATE TRIGGER trg_reserva_pasajero_bi")

    with app.app_context():
        sentencias, previo = respaldo.restaurar(ruta, ip="consola")
    assert sentencias > 40 and previo["tipo"] == "Antes de restaurar"
    assert (carpeta / previo["nombre"]).is_file()
    assert sumas(app) == antes                                          # cada tabla, idéntica
    assert bitacora_hasta(app, ultimo) == bitacora_antes
    assert consultar_valor(app, "SELECT accion FROM bitacora ORDER BY id DESC LIMIT 1") == "respaldo_restaurado"
    assert consultar_valor(app, SQL_AUTO_INCREMENT) == auto_incremento
    # Vuelven las 2 vistas, el procedimiento y los 4 triggers, en modo estricto
    assert consultar_valor(app, "SELECT COUNT(*) FROM information_schema.VIEWS "
                                "WHERE TABLE_SCHEMA = DATABASE()") == 2
    assert consultar_valor(app, "SELECT COUNT(*) FROM information_schema.ROUTINES "
                                "WHERE ROUTINE_SCHEMA = DATABASE()") == 1
    assert consultar_valor(app, "SELECT COUNT(*) FROM information_schema.TRIGGERS "
                                "WHERE TRIGGER_SCHEMA = DATABASE() "
                                "AND SQL_MODE LIKE '%STRICT_TRANS_TABLES%'") == 4


def test_el_respaldo_se_divide_en_sentencias_como_en_phpmyadmin(app, carpeta):
    with app.app_context():
        hecho = respaldo.crear("consola", ip="consola")
    sentencias = bd.dividir_sentencias((carpeta / hecho["nombre"]).read_text(encoding="utf-8"))
    triggers = [s for s in sentencias if s.startswith("CREATE TRIGGER")]
    assert len(triggers) == 4 and all(s.rstrip().endswith("END") for s in triggers)
    assert sum(s.startswith("CREATE TABLE") for s in sentencias) == 20


def test_no_se_restaura_un_archivo_que_no_es_un_respaldo_completo(app, carpeta):
    with app.app_context():
        hecho = respaldo.crear("consola", ip="consola")
    cortado = carpeta / "respaldo_20260101_000000.sql"
    cortado.write_text((carpeta / hecho["nombre"]).read_text(encoding="utf-8")[:3000], encoding="utf-8")
    otro = carpeta / "otro.sql"
    otro.write_text("DROP TABLE reserva;", encoding="utf-8")
    for archivo in (cortado, otro, carpeta / "no-existe.sql"):
        with app.app_context(), pytest.raises(respaldo.ErrorNegocio):
            respaldo.restaurar(archivo)
    assert consultar_valor(app, "SELECT COUNT(*) FROM reserva") > 0      # no se tocó nada


def test_se_guardan_solo_los_mas_nuevos(app, carpeta, monkeypatch):
    monkeypatch.setitem(app.config, "RESPALDOS_CONSERVAR", 3)
    viejos = []
    for dia in range(1, 6):
        viejo = carpeta / f"respaldo_2026010{dia}_000000.sql"
        viejo.write_text("-- viejo", encoding="utf-8")
        momento = time.time() - (10 - dia) * 86400
        os.utime(viejo, (momento, momento))
        viejos.append(viejo.name)
    with app.app_context():
        hecho = respaldo.crear("consola", ip="consola")
        quedan = [r["nombre"] for r in respaldo.listar()]
    assert quedan == [hecho["nombre"], viejos[4], viejos[3]]


def test_el_respaldo_automatico_solo_cuando_hace_falta(app, carpeta):
    with app.app_context():
        primero = respaldo.crear_si_hace_falta()
        assert primero["tipo"] == "Automático" and primero["nombre"].endswith("_auto.sql")
        assert respaldo.crear_si_hace_falta() is None                  # el último tiene menos de 24 h
        hace_25_horas = time.time() - 25 * 3600
        os.utime(carpeta / primero["nombre"], (hace_25_horas, hace_25_horas))
        assert respaldo.crear_si_hace_falta()["tipo"] == "Automático"
    detalle = consultar_valor(app, "SELECT CONCAT(IFNULL(usuario_id, '-'), ' ', ip) FROM bitacora "
                                   "WHERE accion = 'respaldo_creado' ORDER BY id DESC LIMIT 1")
    assert detalle == "- servidor"


def test_el_hilo_de_tareas_del_servidor_crea_el_respaldo(app, carpeta, monkeypatch):
    tareas.hacer(app)                                                 # en las pruebas está apagado
    assert list(carpeta.glob("respaldo_*_auto.sql")) == []
    monkeypatch.setitem(app.config, "RESPALDO_AUTOMATICO", True)
    hilo = tareas.iniciar(app, espera_inicial=0, cada=3600)
    assert hilo.daemon and hilo.name == "tareas-automaticas"
    for _ in range(100):
        if list(carpeta.glob("respaldo_*_auto.sql")):
            break
        time.sleep(0.1)
    assert len(list(carpeta.glob("respaldo_*_auto.sql"))) == 1


# --- Página del admin, descarga y reporte general ----------------------------------------------

def test_crear_y_descargar_un_respaldo_desde_el_panel(app, cliente, carpeta):
    iniciar_sesion(cliente, "admin")
    pagina = cliente.get("/panel/respaldos")
    assert "Todavía no hay respaldos" in pagina.get_data(True)
    assert cliente.post("/panel/respaldos/crear",
                        data={"csrf_token": token_csrf(pagina)}).status_code == 303
    html = cliente.get("/panel/respaldos").get_data(True)
    nombre = re.search(r"<code>(respaldo_\d{8}_\d{6}\.sql)</code>", html).group(1)
    assert "Listo: se guardó" in html and "Manual" in html
    descarga = cliente.get(f"/panel/respaldos/{nombre}")
    try:
        assert descarga.status_code == 200 and "attachment" in descarga.headers["Content-Disposition"]
        assert descarga.headers["Cache-Control"] == "no-store"
        assert descarga.get_data(True).startswith(respaldo.CABECERA)
    finally:
        descarga.close()
    quien = consultar_valor(app, "SELECT COUNT(*) FROM bitacora WHERE usuario_id = 1 "
                                 "AND accion IN ('respaldo_creado', 'respaldo_descargado')")
    assert quien >= 2


@pytest.mark.parametrize("nombre", ["otro.sql", "respaldo_20260101_000000.sql", "respaldo_x.sql",
                                    ".env", "respaldo_20260101_000000.sql.parcial"])
def test_solo_se_descargan_respaldos_que_existen(cliente, carpeta, nombre):
    (carpeta / "otro.sql").write_text("-- no es un respaldo", encoding="utf-8")
    iniciar_sesion(cliente, "admin")
    assert cliente.get(f"/panel/respaldos/{nombre}").status_code == 404


@pytest.mark.parametrize("usuario", ["operador", "guia.elena", "capitan.teodoro"])
def test_solo_el_admin_maneja_los_respaldos(app, carpeta, usuario):
    cliente = app.test_client()
    iniciar_sesion(cliente, usuario)
    csrf = token_csrf(cliente.get("/panel"))
    assert cliente.get("/panel/respaldos").status_code == 403
    assert cliente.get("/panel/respaldos/reporte-general").status_code == 403
    assert cliente.post("/panel/respaldos/crear", data={"csrf_token": csrf}).status_code == 403
    assert list(carpeta.iterdir()) == []


def test_reporte_general_en_excel_sin_documentos(app, cliente, carpeta):
    iniciar_sesion(cliente, "admin")
    respuesta = cliente.get("/panel/respaldos/reporte-general")
    assert respuesta.status_code == 200 and respuesta.mimetype == "application/zip"
    with zipfile.ZipFile(io.BytesIO(respuesta.data)) as zip_:
        assert sorted(zip_.namelist()) == ["LEEME.txt", "hospedajes.csv", "pagos.csv",
                                           "reservas.csv", "salidas.csv"]
        reservas = zip_.read("reservas.csv").decode("utf-8")
        todo = "".join(zip_.read(n).decode("utf-8") for n in zip_.namelist())
    assert reservas.startswith("﻿Código,Estado,Método de pago") and "TV-33VR" in reservas
    assert "40998812" not in todo and "TZ1234567" not in todo          # sin documentos
    assert consultar_valor(app, "SELECT COUNT(*) FROM bitacora "
                                "WHERE accion = 'reporte_general_descargado'") >= 1


def test_el_admin_ve_cuando_fue_el_ultimo_respaldo(app, cliente, carpeta):
    iniciar_sesion(cliente, "admin")
    assert "Todavía no hay ninguno" in cliente.get("/panel").get_data(True)
    with app.app_context():
        respaldo.crear("consola", ip="consola")
    html = cliente.get("/panel").get_data(True)
    assert "Revisar los respaldos" in html and "(consola)" in html


# --- Consola ------------------------------------------------------------------------------------

def test_flask_bd_respaldar_y_restaurar(app, carpeta):
    consola = app.test_cli_runner()
    hecho = consola.invoke(args=["bd", "respaldar"])
    assert hecho.exit_code == 0 and "Listo:" in hecho.output and "20 tablas" in hecho.output
    nombre = next(carpeta.glob("respaldo_*_consola.sql")).name
    vuelta = consola.invoke(args=["bd", "restaurar", nombre, "--si"])    # basta con el nombre
    assert vuelta.exit_code == 0, vuelta.output
    assert "restaurada desde" in vuelta.output and "Antes se guardó" in vuelta.output
    otro = carpeta / "otro.sql"
    otro.write_text("DROP TABLE reserva;", encoding="utf-8")
    malo = consola.invoke(args=["bd", "restaurar", str(otro), "--si"])
    assert malo.exit_code != 0 and "no es un respaldo completo" in malo.output


def test_restaurar_pide_confirmacion(app, carpeta):
    resultado = app.test_cli_runner().invoke(args=["bd", "restaurar", "x.sql"], input="n\n")
    assert resultado.exit_code != 0 and "Se BORRARÁ" in resultado.output


def test_reiniciar_guarda_antes_un_respaldo(app, carpeta):
    resultado = app.test_cli_runner().invoke(args=["bd", "reiniciar", "--si"])
    assert resultado.exit_code == 0, resultado.output
    assert "Respaldo previo:" in resultado.output
    assert len(list(carpeta.glob("respaldo_*_antes-de-reiniciar.sql"))) == 1


# --- Fuera del ZIP de entrega y de git: llevan datos personales -----------------------------

def test_los_respaldos_no_van_en_el_zip_de_entrega_ni_en_git(tmp_path):
    (tmp_path / "respaldos").mkdir()
    (tmp_path / "respaldos" / "respaldo_20260101_000000.sql").write_text("-- datos", encoding="utf-8")
    (tmp_path / "app.py").write_text("print()", encoding="utf-8")
    assert [r.as_posix() for r in empaquetar.archivos(tmp_path)] == ["app.py"]
    assert "respaldos/" in (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()

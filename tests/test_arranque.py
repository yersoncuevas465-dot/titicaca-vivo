"""Arranque sin fallas: servidor.py revisa todo antes de abrir el puerto y, si algo falta (el .env,
MySQL, la base), dice exactamente qué hacer. Lo mismo `flask bd ...` y la página de error."""

import argparse
from datetime import date, datetime

import pymysql
import pytest

import servidor
from app import crear_app, diagnostico
from app.config import Config, ConfigPruebas
from scripts import crear_bd
from tests.conftest import iniciar_sesion


class ConfigSinBase(ConfigPruebas):
    BD_PUERTO = 1          # nadie escucha ahí: es como tener MySQL apagado


# --- El archivo .env ------------------------------------------------------------------------------

def test_preparar_env_crea_el_env_y_su_secret_key(tmp_path):
    (tmp_path / ".env.example").write_text("ENTORNO=desarrollo\nSECRET_KEY=\nBD_NOMBRE=x\n",
                                           encoding="utf-8")
    hechos = servidor.preparar_env(tmp_path)
    texto = (tmp_path / ".env").read_text(encoding="utf-8")
    assert len(hechos) == 2
    clave = next(linea for linea in texto.splitlines() if linea.startswith("SECRET_KEY="))
    assert len(clave.split("=", 1)[1]) == 64                       # secrets.token_hex(32)
    assert "BD_NOMBRE=x" in texto                                  # lo demás no se toca


def test_preparar_env_no_cambia_una_secret_key_que_ya_existe(tmp_path):
    (tmp_path / ".env").write_text("SECRET_KEY=ya-tengo-una\n", encoding="utf-8")
    assert servidor.preparar_env(tmp_path) == []
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "SECRET_KEY=ya-tengo-una\n"


def test_preparar_env_agrega_la_secret_key_si_falta_la_linea(tmp_path):
    (tmp_path / ".env").write_text("ENTORNO=desarrollo", encoding="utf-8")
    assert servidor.preparar_env(tmp_path) == ["Se generó una SECRET_KEY nueva y se guardó en .env"]
    assert "\nSECRET_KEY=" in (tmp_path / ".env").read_text(encoding="utf-8")


def test_sin_env_ni_ejemplo_avisa(tmp_path):
    with pytest.raises(FileNotFoundError):
        servidor.preparar_env(tmp_path)


def test_revisar_python_y_dependencias_en_este_entorno():
    assert servidor.revisar_python()[0]
    ok, texto = servidor.revisar_dependencias()
    assert ok and "Flask" in texto and "waitress" in texto


def test_si_falta_una_dependencia_dice_como_activar_el_entorno(monkeypatch):
    monkeypatch.setitem(servidor.DEPENDENCIAS, "paquete-que-no-existe", "paquete_que_no_existe")
    ok, texto = servidor.revisar_dependencias()
    assert not ok
    assert "paquete-que-no-existe" in texto and "Activate.ps1" in texto and "INICIAR.bat" in texto


# --- Diagnóstico de la base -----------------------------------------------------------------------

@pytest.mark.parametrize(("codigo", "pista"), [
    (2003, "Start en MySQL"),
    (1045, "BD_CONTRASENA"),
    (1049, "python scripts/crear_bd.py"),
    (1044, "python scripts/crear_bd.py"),
    (1146, "flask bd reiniciar --si"),
])
def test_cada_error_de_conexion_dice_que_hacer(app, codigo, pista):
    explicacion = diagnostico.explicar(pymysql.err.OperationalError(codigo, "x"), app.config)
    assert pista in explicacion
    assert "Qué hacer" in explicacion


def test_la_base_de_pruebas_esta_lista(app):
    problema, estado = diagnostico.revisar(app.config)
    assert problema is None
    assert (estado["tablas"], estado["vistas"], estado["triggers"], estado["procedimientos"]) == (21, 2, 4, 1)
    assert estado["filas"] > 200 and estado["salidas_hoy"] >= 1


def test_con_mysql_apagado_dice_que_lo_enciendas(app):
    problema, estado = diagnostico.revisar({**app.config, "BD_PUERTO": 1})
    assert "MySQL no responde" in problema and "XAMPP" in problema
    assert estado == {}


def test_con_la_contrasena_equivocada_dice_cual_cambiar(app):
    problema, _ = diagnostico.revisar({**app.config, "BD_CONTRASENA": "no-es-esta"})
    assert "BD_CONTRASENA" in problema


def test_con_una_base_que_no_existe_dice_que_script_ejecutar(app):
    problema, _ = diagnostico.revisar({**app.config, "BD_NOMBRE": "titicaca_vivo_no_existe"})
    assert "python scripts/crear_bd.py" in problema


# --- scripts/crear_bd.py (PASO 4) -----------------------------------------------------------------

def test_el_script_de_usuario_no_lleva_contrasena():
    """La contraseña real va solo en el .env: el .sql viaja en el ZIP de entrega."""
    texto = crear_bd.SCRIPT.read_text(encoding="utf-8")
    assert texto.count("IDENTIFIED BY 'CAMBIA_ESTA_CLAVE'") == 2


def test_crear_bd_pone_la_contrasena_del_env_sin_editar_el_sql():
    lista = crear_bd.sentencias("o'tra\\clave")
    usuarios = [s for s in lista if "IDENTIFIED BY" in s]
    assert len(usuarios) == 4                          # 2 CREATE USER + 2 ALTER USER (otra corrida)
    assert all("IDENTIFIED BY 'o\\'tra\\\\clave'" in s for s in usuarios)   # comillas escapadas
    assert not any("CAMBIA_ESTA_CLAVE" in s for s in lista)
    assert any(s.startswith("GRANT ALL PRIVILEGES ON titicaca_vivo_pruebas.*") for s in lista)


def test_crear_bd_genera_y_guarda_la_contrasena_si_falta(tmp_path):
    env = tmp_path / ".env"
    env.write_text("BD_USUARIO=titicaca_app\nBD_CONTRASENA=\n", encoding="utf-8")
    clave = crear_bd.clave_de_la_app(env)
    assert len(clave) >= 20 and f"BD_CONTRASENA={clave}" in env.read_text(encoding="utf-8")
    assert crear_bd.clave_de_la_app(env) == clave       # la segunda vez usa la misma


# --- servidor.py ----------------------------------------------------------------------------------

def opciones(**cambios):
    return argparse.Namespace(**{"host": "127.0.0.1", "puerto": 8080, "revisar": True, **cambios})


def test_servidor_no_arranca_sin_mysql_y_dice_que_hacer(monkeypatch, capsys):
    monkeypatch.setattr(servidor, "preparar_env", lambda: [])     # no tocar el .env real
    monkeypatch.setattr(Config, "BD_PUERTO", 1)
    assert servidor.revisar(opciones()) is None
    salida = capsys.readouterr().out
    assert "[ok] Python" in salida and "[X]  MySQL no responde" in salida and "XAMPP" in salida


def test_servidor_revisa_todo_y_muestra_la_base(app, monkeypatch, capsys):
    monkeypatch.setattr(servidor, "preparar_env", lambda: [])
    monkeypatch.setattr(Config, "BD_NOMBRE", ConfigPruebas.BD_NOMBRE)   # nunca la base de trabajo
    config = servidor.revisar(opciones(puerto=1))
    salida = capsys.readouterr().out
    assert config is not None and config["BD_NOMBRE"] == ConfigPruebas.BD_NOMBRE
    assert f"[ok] Base {ConfigPruebas.BD_NOMBRE}: 21 tablas, 2 vistas, 4 triggers" in salida
    assert "[ok] Puerto 1 libre" in salida and "[X]" not in salida


def test_avisa_si_la_base_se_cargo_otro_dia():
    hoy = date(2026, 10, 29)
    vieja = {"cargada_en": datetime(2026, 10, 27, 18, 50), "salidas_desde_hoy": 3}
    aviso = servidor.aviso_de_fechas(vieja, hoy)
    assert "27/10/2026 (hace 2 día(s))" in aviso and "flask bd reiniciar --si" in aviso
    assert servidor.aviso_de_fechas({"cargada_en": datetime(2026, 10, 29, 8), "salidas_desde_hoy": 3},
                                    hoy) is None
    assert "No hay salidas" in servidor.aviso_de_fechas({"cargada_en": None, "salidas_desde_hoy": 0}, hoy)


def test_main_devuelve_1_si_no_puede_arrancar(monkeypatch, capsys):
    monkeypatch.setattr(servidor, "preparar_env", lambda: [])
    monkeypatch.setattr(Config, "BD_PUERTO", 1)
    assert servidor.main(["--revisar"]) == 1
    assert "No se arrancó el servidor" in capsys.readouterr().out


def test_url_y_aviso_de_arranque(capsys):
    assert servidor.url_local(opciones(host=servidor.TODA_LA_RED, puerto=8081)) == "http://127.0.0.1:8081"
    servidor.mostrar_aviso(opciones(), {"VERSION": "2.0.0", "ENTORNO": "desarrollo"})
    salida = capsys.readouterr().out
    assert "http://127.0.0.1:8080/entrar" in salida and "Ctrl + C" in salida
    servidor.mostrar_aviso(opciones(), {"VERSION": "2.0.0", "ENTORNO": "produccion"})
    assert "Admin-Titicaca26" not in capsys.readouterr().out       # en producción, sin claves demo
    # D-111: con el correo simulado, el aviso dice dónde aparece el código de recuperación
    servidor.mostrar_aviso(opciones(), {"VERSION": "2.0.0", "ENTORNO": "desarrollo",
                                        "CORREO_SIMULAR": True})
    salida = capsys.readouterr().out
    assert "[CORREO SIMULADO]" in salida and "Respaldo automático" not in salida
    servidor.mostrar_aviso(opciones(), {"VERSION": "2.0.0", "ENTORNO": "desarrollo",
                                        "RESPALDO_AUTOMATICO": True, "RESPALDO_CADA_HORAS": 24})
    assert "Respaldo automático: cada 24 h" in capsys.readouterr().out


# --- flask bd y la página de error ----------------------------------------------------------------

@pytest.mark.parametrize("comando", [["bd", "contar"], ["bd", "reiniciar", "--si"],
                                     ["reservas", "vencer"]])
def test_los_comandos_sin_mysql_explican_que_hacer(comando):
    resultado = crear_app(ConfigSinBase).test_cli_runner().invoke(args=comando)
    assert resultado.exit_code == 1
    assert "MySQL no responde" in resultado.output and "Traceback" not in resultado.output


def test_pagina_sin_base_dice_que_no_hay_conexion():
    app = crear_app(ConfigSinBase)
    app.config["PROPAGATE_EXCEPTIONS"] = False
    respuesta = app.test_client().get("/salidas")
    html = respuesta.get_data(True)
    assert respuesta.status_code == 500
    assert "No hay conexión con la base de datos" in html
    assert "Start en MySQL" in html                                # pista para el equipo
    assert "Traceback" not in html


def test_en_produccion_la_pagina_sin_base_no_da_pistas_internas():
    class SinBaseEnProduccion(ConfigSinBase):
        ENTORNO = "produccion"

    app = crear_app(SinBaseEnProduccion)
    app.config["PROPAGATE_EXCEPTIONS"] = False
    html = app.test_client().get("/salidas").get_data(True)
    assert "No hay conexión con la base de datos" in html and "XAMPP" not in html


# --- Panel: «Tu trabajo de hoy» y guías «¿Cómo funciona?» -----------------------------------------

@pytest.mark.parametrize(("usuario", "tarea"), [
    ("operador", "Verificar los pagos"),
    ("admin", "Revisar la bitácora"),
    ("guia.elena", "Lista sin señal"),
    ("capitan.teodoro", "Manifiesto y zarpe"),
])
def test_cada_rol_ve_su_trabajo_de_hoy(cliente, usuario, tarea):
    iniciar_sesion(cliente, usuario)
    html = cliente.get("/panel").get_data(True)
    assert "Tu trabajo de hoy" in html and tarea in html


@pytest.mark.parametrize(("usuario", "url"), [
    ("operador", "/panel/salidas"), ("operador", "/panel/salidas/8/pasajeros"),
    ("operador", "/panel/abordaje"), ("operador", "/panel/pagos"), ("operador", "/panel/alertas"),
    ("operador", "/panel/hospedajes"), ("operador", "/panel/hospedajes/transparencia"),
    ("operador", "/panel/resenas"), ("operador", "/panel/indicadores"),
    ("operador", "/panel/catalogos"), ("admin", "/panel/usuarios"), ("admin", "/panel/bitacora"),
    ("operador", "/panel/mi-cuenta"), ("guia.elena", "/panel/mi-cuenta"),
    ("admin", "/panel/respaldos"),
])
def test_cada_pagina_del_panel_explica_como_funciona(cliente, usuario, url):
    iniciar_sesion(cliente, usuario)
    html = cliente.get(url).get_data(True)
    assert '<details class="guia no-imprimir">' in html
    assert "¿Cómo funciona esta página?" in html

"""Tareas automáticas del servidor (las enciende servidor.py; ni `flask run` ni las pruebas).

Un solo hilo que, mientras la app está encendida:
- cada 5 minutos marca «vencida» cada reserva Yape/Plin que no se pagó a tiempo (RN-05). Así el
  turista, el operador, los indicadores y los reportes ven lo mismo, sin que nadie tenga que
  acordarse de ejecutar `flask reservas vencer`;
- cada hora revisa si toca el respaldo automático de la base (D-118);
- cada 5 minutos deja listos el clima, el tipo de cambio y los feriados (APIs, v2.2).
"""

import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

VUELTA_SEGUNDOS = 300                 # cada 5 minutos
VUELTAS_POR_RESPALDO = 12             # 12 × 5 minutos = 1 hora


def hacer(app, revisar_respaldo=True):
    """Una vuelta de las tareas. Si una falla (sin base, sin disco), la otra igual corre."""
    from app.modelos import reserva, respaldo

    with app.app_context():
        try:
            vencidas = reserva.vencer_pendientes(origen="automático (servidor)")
            if vencidas:
                app.logger.info("Reservas vencidas (sin pago a tiempo): %s", ", ".join(vencidas))
        except Exception:                        # se reintenta en la próxima vuelta
            app.logger.exception("No se pudieron vencer las reservas")
    if app.config["APIS_EXTERNAS"]:
        _preparar_apis(app)
    if revisar_respaldo and app.config["RESPALDO_AUTOMATICO"]:
        with app.app_context():
            try:
                hecho = respaldo.crear_si_hace_falta()
                if hecho:
                    app.logger.info("Respaldo automático: %s (%s KB)", hecho["nombre"],
                                    hecho["kb"])
            except Exception:                    # se reintenta en la próxima hora
                app.logger.exception("Respaldo automático: no se pudo crear")


def _preparar_apis(app):
    """Deja en la caché el clima, el tipo de cambio y los feriados (v2.2): así ninguna página
    espera a una API. Si una no responde, la página sale sin ese dato (servicios/externas.py)."""
    from app.servicios import clima, feriados, tipo_cambio

    with app.app_context():
        try:
            hoy = datetime.now(ZoneInfo(app.config["ZONA_HORARIA"])).date()
            clima.pronostico()
            tipo_cambio.del_dia()
            # En diciembre, también los del año siguiente (la lista muestra 7 días)
            for anio in {hoy.year, (hoy + timedelta(days=14)).year}:
                feriados.del_anio(anio)
        except Exception:
            app.logger.exception("No se pudieron preparar los datos de las APIs externas")


def iniciar(app, espera_inicial=30, cada=VUELTA_SEGUNDOS):
    """Arranca el hilo de las tareas (daemon: se apaga junto con el servidor)."""

    def trabajar():
        time.sleep(espera_inicial)               # que el servidor termine de arrancar
        vuelta = 0
        while True:
            hacer(app, revisar_respaldo=vuelta % VUELTAS_POR_RESPALDO == 0)
            vuelta += 1
            time.sleep(cada)

    hilo = threading.Thread(target=trabajar, name="tareas-automaticas", daemon=True)
    hilo.start()
    return hilo

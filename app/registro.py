"""Registro de eventos en logs/app.log, con la hora de Lima (sección 11)."""

import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from zoneinfo import ZoneInfo

FORMATO = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


class FormatoLima(logging.Formatter):
    """Escribe la fecha con la zona America/Lima, aunque la PC tenga otra zona."""

    zona = ZoneInfo("America/Lima")

    def formatTime(self, record, datefmt=None):  # noqa: N802 (nombre que exige logging)
        momento = datetime.fromtimestamp(record.created, self.zona)
        return momento.strftime(datefmt or "%Y-%m-%d %H:%M:%S%z")


def configurar(app):
    archivo = app.config.get("LOG_ARCHIVO")
    app.logger.setLevel(logging.INFO)
    if not archivo:
        return
    archivo.parent.mkdir(parents=True, exist_ok=True)
    manejador = RotatingFileHandler(archivo, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    manejador.setFormatter(FormatoLima(FORMATO))
    manejador.setLevel(logging.INFO)
    if not any(isinstance(h, RotatingFileHandler) for h in app.logger.handlers):
        app.logger.addHandler(manejador)
    app.logger.info(
        "Arranque de Titicaca Vivo %s (entorno=%s, base=%s@%s:%s)",
        app.config["VERSION"], app.config["ENTORNO"], app.config["BD_NOMBRE"],
        app.config["BD_HOST"], app.config["BD_PUERTO"],
    )

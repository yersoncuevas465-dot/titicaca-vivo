"""Consultas técnicas: estado de la base para /salud."""

from app import bd


def hora_de_la_base():
    # Devuelve la fecha y hora actuales según MariaDB (con la zona -05:00 de la sesión).
    return bd.consultar_uno("SELECT NOW() AS ahora")["ahora"]

"""Fotos de las comunidades y fotos de fondo de cada sección.

- Fotos de las comunidades: app/estaticos/img/comunidades/<slug>.webp (≤ 40 KB, Wikimedia
  Commons). Si la foto todavía no existe, la plantilla muestra una ilustración propia en su
  lugar. El crédito visible sale de la base (comunidad.foto_credito).
- Fotos de fondo (D-109): app/estaticos/img/fondos/<slug>.webp (≤ 20 KB, las arma
  scripts/preparar_fondos.py con las mismas fotos). Cada sección tiene la suya, muy tenue,
  como marca de agua, y su crédito al pie. No se lee nada de la base: también sale en las
  páginas de error.
"""

from functools import lru_cache
from pathlib import Path

from flask import request

IMG = Path(__file__).resolve().parent.parent / "estaticos" / "img"
CARPETA = IMG / "comunidades"

# Autor y licencia de cada foto (docs/creditos-imagenes.md)
CREDITOS = {
    "uros": "Entropy1963 · dominio público",
    "taquile": "Alonso Cárdenas · CC BY-SA 3.0",
    "amantani": "Pastor3571 · CC BY 4.0",
    "llachon": "Hilda Maria FC · CC0",
    "luquina-chico": "Murray Foubister · CC BY-SA 2.0",
    "ticonata": "Titico · dominio público",
}
NOMBRES = {"uros": "Uros", "taquile": "Taquile", "amantani": "Amantaní", "llachon": "Llachón",
           "luquina-chico": "Luquina Chico", "ticonata": "Ticonata"}

# Qué foto va de fondo en cada parte de la app: gana el primer prefijo del endpoint que coincide.
# El acceso y el resumen del panel comparten foto: al entrar, el fondo no cambia.
# None = sin foto: el formulario de reserva es la página más pesada (hasta 10 pasajeros) y ahí
# el turista solo tiene que fijarse en sus datos.
FONDO_POR_PAGINA = (
    ("publico.inicio", "uros"),
    ("publico.salidas", "uros"),
    ("publico.detalle_salida", "uros"),
    ("reservas.reservar", None),
    ("publico.comunidades", "taquile"),
    ("publico.detalle_comunidad", "taquile"),   # si la comunidad todavía no tiene foto propia
    ("publico.alertas", "ticonata"),
    ("reservas.", "amantani"),
    ("autenticacion.", "llachon"),
    ("panel.inicio", "llachon"),
    ("panel.salida", "uros"),
    ("panel.pasajeros", "uros"),
    ("panel.abordaje", "uros"),
    ("panel.cobro", "uros"),
    ("panel.pago", "luquina-chico"),
    ("panel.devolucion", "luquina-chico"),
    ("panel.indicadores", "luquina-chico"),
    ("panel.alerta", "ticonata"),
    ("panel.hospedaje", "amantani"),
    ("panel.transparencia", "amantani"),
    ("panel.resena", "taquile"),
    ("catalogos.", "taquile"),
    ("panel.", "ticonata"),                  # usuarios, bitácora y mi cuenta
)


@lru_cache(maxsize=64)
def foto_comunidad(slug):
    """Ruta (dentro de estaticos/) de la foto de la comunidad, o None si no hay archivo."""
    archivo = CARPETA / f"{slug}.webp"
    return f"img/comunidades/{slug}.webp" if archivo.is_file() else None


@lru_cache(maxsize=16)
def _hay_fondo(slug):
    return (IMG / "fondos" / f"{slug}.webp").is_file()


def fondo(slug):
    """{'ruta', 'credito'} de la foto de fondo, o None si no existe."""
    if slug not in CREDITOS or not _hay_fondo(slug):
        return None
    return {"ruta": f"img/fondos/{slug}.webp",
            "credito": f"{NOMBRES[slug]} · {CREDITOS[slug]}"}


def fondo_de_pagina():
    """La foto de fondo de la página que se está mostrando (None en las páginas de error)."""
    endpoint = request.endpoint or ""
    if endpoint == "publico.detalle_comunidad":            # cada comunidad, con su propia foto
        propia = fondo((request.view_args or {}).get("slug", ""))
        if propia:
            return propia
    for prefijo, slug in FONDO_POR_PAGINA:
        if endpoint.startswith(prefijo):
            return fondo(slug)
    return None

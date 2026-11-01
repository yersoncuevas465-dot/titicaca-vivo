"""Fotos que suben el residente o el operador para sus productos (v2.9, D-121).

La foto se abre con Pillow y se guarda otra vez como WebP de 640×400. Así se comprueba que de
verdad es una imagen, pesa poco aunque la señal sea débil y pierde sus metadatos: el GPS que
guarda el celular no sale a internet. Queda con un nombre al azar en SUBIDAS_CARPETA/productos,
fuera de git y del ZIP de entrega (como los respaldos).
"""

import io
import re
import secrets
from pathlib import Path

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError

FORMATOS = {"JPEG", "PNG", "WEBP"}
ANCHO, ALTO = 640, 400
MAX_PIXELES = 50_000_000                  # 50 megapíxeles: la foto de cualquier celular
PREFIJO = "subidas/productos/"            # así empieza producto.foto si la foto fue subida
NOMBRE = re.compile(r"[0-9a-f]{20}\.webp")
NO_ES_FOTO = "La foto tiene que ser JPG, PNG o WebP (de hasta 50 megapíxeles)."


def carpeta():
    return Path(current_app.config["SUBIDAS_CARPETA"]) / "productos"


def guardar(archivo):
    """Convierte la foto subida y la guarda. Devuelve su ruta para la base o lanza ValueError."""
    try:
        with Image.open(archivo.stream) as imagen:
            if imagen.format not in FORMATOS or imagen.width * imagen.height > MAX_PIXELES:
                raise ValueError(imagen.format)
            imagen.draft("RGB", (ANCHO * 2, ALTO * 2))     # un JPG grande se lee ya reducido
            imagen = ImageOps.exif_transpose(imagen).convert("RGB")
            imagen = ImageOps.fit(imagen, (ANCHO, ALTO), Image.LANCZOS)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError,
            ValueError) as error:
        raise ValueError(NO_ES_FOTO) from error
    memoria = io.BytesIO()
    imagen.save(memoria, "WEBP", quality=75, method=4)    # sin exif: no lleva metadatos
    nombre = secrets.token_hex(10) + ".webp"
    carpeta().mkdir(parents=True, exist_ok=True)
    (carpeta() / nombre).write_bytes(memoria.getvalue())
    return PREFIJO + nombre


def borrar(foto):
    """Borra una foto subida. Las de la semilla (img/productos/) son parte del programa: no.

    Si Windows la tiene abierta un momento (el antivirus revisa cada archivo nuevo), queda
    suelta y se anota en el registro: el producto ya se guardó, no vale un error por eso."""
    if foto and foto.startswith(PREFIJO):
        try:
            (carpeta() / foto.removeprefix(PREFIJO)).unlink(missing_ok=True)
        except OSError:
            current_app.logger.warning("No se pudo borrar la foto subida %s", foto)


def es_nombre_valido(nombre):
    return NOMBRE.fullmatch(nombre) is not None

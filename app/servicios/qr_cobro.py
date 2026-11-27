"""QR de cobro con Yape y Plin (observación del docente, 27/11/2026).

El admin sube la captura del QR de la agencia y la página de pago lo muestra para escanearlo.
El QR es de la cuenta de la agencia: no va en git ni en el ZIP. Queda en SUBIDAS_CARPETA/cobro
(en Railway, dentro del volumen). Se abre con Pillow y se guarda otra vez como PNG, sin
metadatos y con fondo blanco (un QR con fondo transparente se vería negro).
El sistema no entra a la cuenta de Yape ni de Plin: el turista paga, copia el número de operación
y la agencia lo verifica en su app, como siempre.
"""

import io
from pathlib import Path

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError

MEDIOS = {"yape": "Yape", "plin": "Plin"}
FORMATOS = {"JPEG", "PNG", "WEBP"}
LADO = 720                                # px: se lee bien en el celular y pesa poco
MAX_PIXELES = 50_000_000
NO_ES_QR = "El QR tiene que ser una imagen JPG, PNG o WebP (sirve la captura de tu app)."


def carpeta():
    return Path(current_app.config["SUBIDAS_CARPETA"]) / "cobro"


def ruta(medio):
    return carpeta() / f"{medio}.png"


def hay(medio):
    return medio in MEDIOS and ruta(medio).is_file()


def guardar(medio, archivo):
    """Convierte la imagen subida y la guarda como el QR de ese medio, o lanza ValueError."""
    if medio not in MEDIOS:
        raise ValueError(NO_ES_QR)
    try:
        with Image.open(archivo.stream) as imagen:
            if imagen.format not in FORMATOS or imagen.width * imagen.height > MAX_PIXELES:
                raise ValueError(imagen.format)
            imagen = ImageOps.exif_transpose(imagen).convert("RGBA")
            fondo = Image.new("RGB", imagen.size, "white")
            fondo.paste(imagen, mask=imagen.getchannel("A"))
            fondo.thumbnail((LADO, LADO), Image.LANCZOS)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError,
            ValueError) as error:
        raise ValueError(NO_ES_QR) from error
    memoria = io.BytesIO()
    fondo.save(memoria, "PNG", optimize=True)
    carpeta().mkdir(parents=True, exist_ok=True)
    ruta(medio).write_bytes(memoria.getvalue())


def borrar(medio):
    """Quita el QR. Si Windows lo tiene abierto un momento, lo deja anotado en el registro."""
    if medio in MEDIOS:
        try:
            ruta(medio).unlink(missing_ok=True)
        except OSError:
            current_app.logger.warning("No se pudo borrar el QR de %s", medio)

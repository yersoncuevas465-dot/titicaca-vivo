"""Arma las fotos de fondo (marca de agua) a partir de las fotos de las comunidades.

Uso (desde la carpeta titicaca_vivo):
    python scripts/preparar_fondos.py

Toma cada app/estaticos/img/comunidades/<slug>.webp, la agranda a 960×600, la suaviza
(así no se notan los píxeles al agrandarla ni compite con el texto) y la guarda como
app/estaticos/img/fondos/<slug>.webp de 20 KB o menos. La página la muestra muy tenue y
solo en pantallas anchas (D-109): en el celular no se descarga.
"""

import io
import sys
from pathlib import Path

from PIL import Image, ImageFilter

RAIZ = Path(__file__).resolve().parent.parent
ORIGEN = RAIZ / "app" / "estaticos" / "img" / "comunidades"
DESTINO = RAIZ / "app" / "estaticos" / "img" / "fondos"
ANCHO, ALTO = 960, 600
MAX_BYTES = 20 * 1024


def preparar(origen):
    with Image.open(origen) as imagen:
        imagen = imagen.convert("RGB").resize((ANCHO, ALTO), Image.LANCZOS)
    imagen = imagen.filter(ImageFilter.GaussianBlur(1.6))
    for calidad in range(60, 9, -5):
        memoria = io.BytesIO()
        imagen.save(memoria, "WEBP", quality=calidad, method=6)
        if memoria.tell() <= MAX_BYTES:
            break
    else:
        raise RuntimeError(f"{origen.name}: no se pudo dejar en 20 KB o menos.")
    DESTINO.mkdir(parents=True, exist_ok=True)
    destino = DESTINO / origen.name
    destino.write_bytes(memoria.getvalue())
    return destino, memoria.tell(), calidad


def main():
    for origen in sorted(ORIGEN.glob("*.webp")):
        destino, peso, calidad = preparar(origen)
        print(f"{destino.relative_to(RAIZ)}: {peso / 1024:.1f} KB (calidad {calidad})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

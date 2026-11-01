"""Convierte una foto (JPG/PNG) en el WebP de una comunidad o un producto: 640×400 y ≤ 40 KB.

Uso (desde la carpeta titicaca_vivo):
    python scripts/preparar_foto.py ruta/a/la/foto.jpg amantani
    python scripts/preparar_foto.py foto.jpg chullo-taquile --carpeta productos --centro-y 0.85

Recorta con proporción 8:5 (al centro, o más arriba o más abajo con --centro-y, por ejemplo
para dejar fuera una cara), reduce a 640×400 y baja la calidad de a poco hasta que el archivo
pese 40 KB o menos. El resultado queda en app/estaticos/img/<carpeta>/<slug>.webp. El crédito
(autor y licencia) se escribe en comunidad.foto_credito o producto.foto_credito y en
docs/creditos-imagenes.md.
"""

import argparse
import io
import re
import sys
from pathlib import Path

from PIL import Image, ImageOps

RAIZ = Path(__file__).resolve().parent.parent
IMAGENES = RAIZ / "app" / "estaticos" / "img"
CARPETAS = ("comunidades", "productos")      # v2.9: también las fotos de los productos
ANCHO, ALTO = 640, 400
MAX_BYTES = 40 * 1024


def preparar(entrada, slug, carpeta="comunidades", centro_y=0.5):
    if not re.fullmatch(r"[a-z0-9-]+", slug):
        raise ValueError("El slug solo puede tener minúsculas, números y guiones.")
    with Image.open(entrada) as imagen:
        imagen = ImageOps.exif_transpose(imagen).convert("RGB")
        imagen = ImageOps.fit(imagen, (ANCHO, ALTO), Image.LANCZOS,       # recorte 8:5
                              centering=(0.5, centro_y))
    for calidad in range(80, 19, -5):
        memoria = io.BytesIO()
        imagen.save(memoria, "WEBP", quality=calidad, method=6)
        if memoria.tell() <= MAX_BYTES:
            break
    else:
        raise RuntimeError("No se pudo dejar la foto en 40 KB o menos.")
    (IMAGENES / carpeta).mkdir(parents=True, exist_ok=True)
    destino = IMAGENES / carpeta / f"{slug}.webp"
    destino.write_bytes(memoria.getvalue())
    return destino, memoria.tell(), calidad


def main():
    argumentos = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argumentos.add_argument("entrada", type=Path)
    argumentos.add_argument("slug")
    argumentos.add_argument("--carpeta", choices=CARPETAS, default="comunidades")
    argumentos.add_argument("--centro-y", type=float, default=0.5,
                            help="de 0 (arriba) a 1 (abajo): qué parte de la foto queda")
    opciones = argumentos.parse_args()
    destino, peso, calidad = preparar(opciones.entrada, opciones.slug, opciones.carpeta,
                                      opciones.centro_y)
    print(f"{destino.relative_to(RAIZ)}: {peso / 1024:.1f} KB (calidad {calidad})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

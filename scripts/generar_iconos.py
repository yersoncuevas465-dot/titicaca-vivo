"""Genera los íconos PNG a partir de la misma geometría del logo SVG.

- apple-touch-icon.png (180×180): para "Agregar a pantalla de inicio" en el celular.
- favicon-32.png (32×32): para navegadores que no leen favicon.svg.

Pillow no lee SVG, por eso el sello se vuelve a dibujar con figuras simples
(círculos, polígonos y curvas). Se dibuja 4 veces más grande y luego se reduce,
para que los bordes queden suaves.

Uso (desde la carpeta titicaca_vivo):  python scripts/generar_iconos.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

RAIZ = Path(__file__).resolve().parent.parent
CARPETA = RAIZ / "app" / "estaticos" / "img"
CIRUELA, TERRACOTA, CREMA, ARENA, TINTA = "#572B44", "#C27A52", "#FEF9F3", "#F5E9DC", "#2A1220"
AUMENTO = 4


def bezier_cubica(p0, p1, p2, p3, pasos=24):
    puntos = []
    for i in range(pasos + 1):
        t = i / pasos
        u = 1 - t
        x = u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0]
        y = u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]
        puntos.append((x, y))
    return puntos


def bezier_cuadratica(p0, p1, p2, pasos=12):
    puntos = []
    for i in range(pasos + 1):
        t = i / pasos
        u = 1 - t
        puntos.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                       u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))
    return puntos


def ola(x0, y, ancho_tramo, tramos, alto=4):
    """Como 'M x0 y q a/2 -alto a 0 t a 0 ...' del SVG: arcos alternados arriba y abajo."""
    puntos = []
    for i in range(tramos):
        inicio = (x0 + i * ancho_tramo, y)
        fin = (x0 + (i + 1) * ancho_tramo, y)
        control_y = y - alto if i % 2 == 0 else y + alto
        control = (inicio[0] + ancho_tramo / 2, control_y)
        puntos.extend(bezier_cuadratica(inicio, control, fin)[(1 if i else 0):])
    return puntos


def trazo(dibujo, puntos, color, ancho, escala):
    escalados = [(x * escala, y * escala) for x, y in puntos]
    dibujo.line(escalados, fill=color, width=round(ancho * escala), joint="curve")
    radio = ancho * escala / 2
    for x, y in (escalados[0], escalados[-1]):          # extremos redondeados
        dibujo.ellipse((x - radio, y - radio, x + radio, y + radio), fill=color)


def poligono(dibujo, puntos, color, escala):
    dibujo.polygon([(x * escala, y * escala) for x, y in puntos], fill=color)


def sello_completo(tamano):
    """El isotipo (viewBox 120): fondo cuadrado ciruela, para ícono de celular."""
    escala = tamano * AUMENTO / 120
    lienzo = Image.new("RGB", (tamano * AUMENTO,) * 2, CIRUELA)

    escena = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(escena)
    for x1, y1, x2, y2 in ((60, 39, 60, 33), (73.5, 42.6, 76.5, 37.4), (46.5, 42.6, 43.5, 37.4),
                           (83.4, 52.5, 88.6, 49.5), (36.6, 52.5, 31.4, 49.5)):
        trazo(d, [(x1, y1), (x2, y2)], TERRACOTA, 4, escala)
    d.pieslice((38 * escala, 44 * escala, 82 * escala, 88 * escala), 180, 360, fill=TERRACOTA)
    cordillera = [(4, 66), (12, 60), (21, 54), (28, 58), (34, 56.5), (42, 62), (50, 63.5),
                  (60, 62.5), (70, 63.5), (79, 61), (86, 57), (97, 52.5), (105, 57), (110, 56),
                  (116, 66)]
    poligono(d, cordillera, TINTA, escala)
    balsa = (bezier_cubica((17, 59), (24, 66), (30, 76), (42, 78)) + [(78, 78)]
             + bezier_cubica((78, 78), (90, 76), (96, 66), (103, 59))
             + bezier_cubica((103, 59), (101, 72), (93, 85), (80, 85)) + [(40, 85)]
             + bezier_cubica((40, 85), (27, 85), (19, 72), (17, 59)))
    poligono(d, balsa, ARENA, escala)
    trazo(d, [(36, 81.5), (84, 81.5)], CIRUELA, 1.6, escala)
    trazo(d, ola(27, 95, 11, 6), CREMA, 3, escala)
    trazo(d, ola(39, 104, 11, 4), CREMA, 3, escala)

    # Recorte circular (r = 52), igual que el clipPath del SVG
    mascara = Image.new("L", lienzo.size, 0)
    ImageDraw.Draw(mascara).ellipse((8 * escala, 8 * escala, 112 * escala, 112 * escala), fill=255)
    lienzo.paste(escena, (0, 0), Image.composite(escena.split()[3], mascara, mascara))
    ImageDraw.Draw(lienzo).ellipse((8 * escala, 8 * escala, 112 * escala, 112 * escala),
                                   outline=ARENA, width=round(1.5 * escala))
    return lienzo.resize((tamano, tamano), Image.LANCZOS)


def sello_simple(tamano):
    """El favicon (viewBox 64): círculo con fondo transparente, sol, balsa y una ola."""
    escala = tamano * AUMENTO / 64
    lienzo = Image.new("RGBA", (tamano * AUMENTO,) * 2, (0, 0, 0, 0))
    d = ImageDraw.Draw(lienzo)
    d.ellipse((0, 0, 64 * escala, 64 * escala), fill=CIRUELA)
    d.pieslice((20 * escala, 26 * escala, 44 * escala, 50 * escala), 180, 360, fill=TERRACOTA)
    balsa = (bezier_cubica((11, 34), (14.5, 38.5), (18, 43), (25, 44)) + [(39, 44)]
             + bezier_cubica((39, 44), (46, 43), (49.5, 38.5), (53, 34))
             + bezier_cubica((53, 34), (52, 42), (47, 49), (40, 49)) + [(24, 49)]
             + bezier_cubica((24, 49), (17, 49), (12, 42), (11, 34)))
    poligono(d, balsa, ARENA, escala)
    trazo(d, ola(19, 56, 7, 4, alto=3), CREMA, 2.6, escala)
    return lienzo.resize((tamano, tamano), Image.LANCZOS)


def main():
    # 64 colores alcanzan para el sello y bajan el peso a menos de la mitad
    sello_completo(180).quantize(colors=64).save(CARPETA / "apple-touch-icon.png", optimize=True)
    sello_simple(32).save(CARPETA / "favicon-32.png", optimize=True)
    for nombre in ("apple-touch-icon.png", "favicon-32.png"):
        print(f"{nombre}: {(CARPETA / nombre).stat().st_size} bytes")


if __name__ == "__main__":
    main()

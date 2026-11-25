"""Práctica 14 · prueba de humo: lo mínimo que tiene que responder Titicaca Vivo ya publicado.

Uso:  python scripts/humo.py https://titicaca-vivo.onrender.com
      python scripts/humo.py http://127.0.0.1:8080          (la laptop, en modo producción)

Solo usa la biblioteca estándar. No sigue redirecciones: así se ve que el panel manda a /entrar.
La primera llamada espera hasta 90 s porque el plan gratis de Render duerme el servicio.
"""

import sys
import time
import urllib.error
import urllib.request

CODIGO = "TV-33VR"          # reserva de la semilla: su página se abre sin entrar, pero oculta


class SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


ABRIR = urllib.request.build_opener(SinRedireccion())


def pedir(base, ruta, espera=20):
    inicio = time.perf_counter()
    pedido = urllib.request.Request(base + ruta,  # noqa: S310 (main solo acepta http y https)
                                    headers={"User-Agent": "humo-titicaca-vivo"})
    try:
        respuesta = ABRIR.open(pedido, timeout=espera)  # noqa: S310 (main solo acepta http y https)
        codigo, cabeceras, cuerpo = respuesta.status, respuesta.headers, respuesta.read()
    except urllib.error.HTTPError as error:
        codigo, cabeceras, cuerpo = error.code, error.headers, error.read()
    ms = (time.perf_counter() - inicio) * 1000
    return codigo, cabeceras, cuerpo.decode("utf-8", "replace"), ms


def main(base):
    base = base.rstrip("/")
    resultados = []

    def revisar(ok, texto):
        resultados.append(ok)
        print(f"{'✔' if ok else '✘'} {texto}")

    if not base.startswith(("http://", "https://")):
        sys.exit("La dirección tiene que empezar con http:// o https://")
    inicio = time.perf_counter()
    codigo, cabeceras, cuerpo, ms = pedir(base, "/salud", espera=90)
    sana = codigo == 200 and '"ok":true' in cuerpo.replace(" ", "")
    revisar(sana, f"/salud → {codigo}  · {ms:.0f} ms")
    for ruta in ("/", "/salidas", "/comunidades/amantani", "/mi-reserva",
                 "/manifest.webmanifest", "/sw.js"):
        codigo, _, _, ms = pedir(base, ruta)
        revisar(codigo == 200, f"{ruta} → {codigo}  · {ms:.0f} ms")
    codigo, _, _, ms = pedir(base, "/no-existe-esta-ruta")
    revisar(codigo == 404, f"/no-existe-esta-ruta → {codigo}  · {ms:.0f} ms")

    revisar(cabeceras.get("X-Content-Type-Options") == "nosniff",
            "cabeceras de seguridad (nosniff)")
    if base.startswith("https://"):
        hsts = cabeceras.get("Strict-Transport-Security") or ""
        revisar("max-age=" in hsts, "HSTS: el navegador recuerda que va solo con https")
    codigo, cabeceras, _, ms = pedir(base, "/panel")
    revisar(codigo == 302 and "/entrar" in (cabeceras.get("Location") or ""),
            f"/panel sin sesión → {codigo} a /entrar · lo del personal no se ve sin entrar")
    codigo, cabeceras, cuerpo, ms = pedir(base, f"/reservas/{CODIGO}")
    oculta = cabeceras.get("Cache-Control") == "no-store" and "••••••••" in cuerpo
    revisar(codigo == 200 and oculta,
            f"/reservas/{CODIGO} → {codigo} · no-store y el DNI oculto (••••••••)")

    bien = sum(resultados)
    print(f"{bien} de {len(resultados)} · {time.perf_counter() - inicio:.1f} s · {base}")
    return 0 if bien == len(resultados) else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))

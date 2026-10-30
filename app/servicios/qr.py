"""Códigos QR del boleto (qrcode[pil]).

El QR guarda la URL /panel/abordaje/<código>. El guía o el capitán la abre con la
cámara normal de su celular, con la sesión iniciada, y confirma el abordaje (F5).
"""

import io
import re

import qrcode
import qrcode.image.svg
from flask import current_app, request
from markupsafe import Markup


def url_de_abordaje(codigo):
    """URL que va dentro del QR. Si URL_PUBLICA está vacía, se usa la del servidor actual."""
    base = current_app.config.get("URL_PUBLICA") or request.host_url
    return base.rstrip("/") + "/panel/abordaje/" + codigo


def svg(texto, titulo="Código QR"):
    """SVG del QR listo para ponerlo dentro del HTML (sin estilos en línea: la CSP lo permite)."""
    imagen = qrcode.make(texto, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    marcado = imagen.to_string(encoding="unicode")
    # Quitamos el ancho en milímetros: el tamaño lo decide el CSS (clase .qr).
    marcado = re.sub(r'\swidth="[^"]+"\sheight="[^"]+"', "", marcado, count=1)
    marcado = marcado.replace("<svg ", f'<svg class="qr" role="img" aria-label="{titulo}" ', 1)
    # Seguro: el SVG lo arma qrcode a partir de una URL nuestra; no es texto escrito por un usuario.
    return Markup(marcado)  # noqa: S704


def png(texto):
    """Bytes PNG del QR (para el PDF del boleto)."""
    imagen = qrcode.make(texto, box_size=8, border=2)
    memoria = io.BytesIO()
    imagen.save(memoria, format="PNG")
    return memoria.getvalue()

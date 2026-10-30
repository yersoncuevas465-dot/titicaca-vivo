"""Ayudantes para validar los datos de los catálogos y de los usuarios.

Cada función revisa UN campo de `datos` y, si está mal, deja el mensaje en `errores`
(mismo nombre que el campo del formulario). Así el modelo junta todos los errores y la
página los muestra juntos, cada uno al lado de su campo.
"""

import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation

PATRON_TELEFONO = re.compile(r"^(9\d{8}|\+\d{7,15})$")
PATRON_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def texto(datos, campo, errores, minimo, maximo, obligatorio=True, nombre="el dato"):
    """Limpia espacios repetidos. Devuelve el texto (o None si es opcional y viene vacío)."""
    valor = " ".join(str(datos.get(campo) or "").split())
    if not valor:
        if obligatorio:
            errores[campo] = f"Escribe {nombre}."
        return None
    if not minimo <= len(valor) <= maximo:
        errores[campo] = f"De {minimo} a {maximo} caracteres."
    return valor


def texto_largo(datos, campo, errores, maximo):
    """Texto de varias líneas (descripción): conserva los saltos de línea."""
    valor = str(datos.get(campo) or "").strip()
    if len(valor) > maximo:
        errores[campo] = f"Máximo {maximo} caracteres."
    return valor or None


def opcion(datos, campo, errores, opciones, mensaje="Elige una opción de la lista."):
    valor = datos.get(campo)
    if valor not in opciones:
        errores[campo] = mensaje
    return valor


def entero(datos, campo, errores, minimo, maximo, obligatorio=True):
    valor = datos.get(campo)
    if valor in (None, ""):
        if obligatorio:
            errores[campo] = f"Escribe un número de {minimo} a {maximo}."
        return None
    try:
        valor = int(valor)
    except (TypeError, ValueError):
        errores[campo] = "Escribe un número entero."
        return None
    if not minimo <= valor <= maximo:
        errores[campo] = f"Va de {minimo} a {maximo}."
    return valor


def decimal(datos, campo, errores, minimo, maximo, decimales=2, obligatorio=True):
    valor = datos.get(campo)
    if valor in (None, ""):
        if obligatorio:
            errores[campo] = "Escribe un número."
        return None
    try:
        valor = Decimal(str(valor)).quantize(Decimal(1).scaleb(-decimales))
    except (InvalidOperation, ValueError):
        errores[campo] = "Escribe un número (usa punto para los decimales)."
        return None
    if not Decimal(str(minimo)) <= valor <= Decimal(str(maximo)):
        errores[campo] = f"Va de {minimo} a {maximo}."
    return valor


def fecha(datos, campo, errores, obligatorio=True):
    valor = datos.get(campo)
    if valor is None or valor == "":
        if obligatorio:
            errores[campo] = "Elige una fecha."
        return None
    if not isinstance(valor, date):
        errores[campo] = "Fecha no válida."
        return None
    return valor


def telefono(datos, campo, errores):
    valor = re.sub(r"[\s\-()]", "", str(datos.get(campo) or "")) or None
    if valor and not PATRON_TELEFONO.match(valor):
        errores[campo] = "Celular de 9 dígitos que empieza en 9, o +código del país."
    return valor


def booleano(datos, campo):
    return 1 if datos.get(campo) else 0


def slug_de(texto_original):
    """'Luquina Chico' → 'luquina-chico' (sin tildes ni símbolos)."""
    descompuesto = unicodedata.normalize("NFKD", texto_original or "")
    sin_tildes = "".join(c for c in descompuesto if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", sin_tildes).strip("-")


def indice_duplicado(error):
    """Nombre del UNIQUE que falló en un error 1062 ("... for key 'uk_ruta_codigo'")."""
    mensaje = str(error.args[1]) if len(error.args) > 1 else ""
    encontrado = re.search(r"key '([^']+)'", mensaje)
    return encontrado.group(1) if encontrado else ""

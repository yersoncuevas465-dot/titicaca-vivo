"""Textos del turista en español e inglés (sección 8.9). El panel queda solo en español.

La clave del diccionario es el texto en español: así las plantillas se leen en español
(`{{ t('Salidas de hoy') }}`) y, si a un texto le falta su traducción, se muestra en
español, nunca una clave rara. Los datos que vienen de la base (nombres de rutas,
comunidades, descripciones) quedan como están: no tienen columna en inglés (D-87).

- t(texto, **valores): traduce un texto de la interfaz. Con valores, los pone en {marcas}
  y los escapa (Markup), salvo que ya sean Markup (por ejemplo, fuerte(...)).
- mensaje(texto): traduce un mensaje que viene del modelo; si tiene partes variables
  (números, códigos), lo reconoce con un patrón.
"""

from flask import g, has_app_context
from markupsafe import Markup, escape

from app.servicios.textos_en import EN, PATRONES

IDIOMAS = ("es", "en")


def idioma():
    """'es' o 'en'. Fuera de una petición (o en el panel) siempre 'es'."""
    if not has_app_context():
        return "es"
    return g.get("idioma", "es")


def t(texto, **valores):
    traducido = EN.get(texto, texto) if idioma() == "en" else texto
    if valores:
        # Seguro: el texto se escapa primero y format() escapa cada valor que no sea Markup.
        return Markup(escape(traducido)).format(**valores)  # noqa: S704
    return traducido


def fuerte(valor):
    """<strong>valor</strong> con el valor escapado: para resaltar un dato dentro de t()."""
    return Markup("<strong>{}</strong>").format(valor)


def mensaje(texto):
    """Traduce un mensaje del modelo (texto fijo o con partes variables)."""
    if idioma() != "en" or not texto:
        return texto
    if texto in EN:
        return EN[texto]
    for patron, plantilla in PATRONES:
        encontrado = patron.fullmatch(texto)
        if encontrado:
            return plantilla.format(*encontrado.groups())
    return texto


def traducir_formulario(formulario):
    """Etiquetas, ayudas, opciones y errores de un formulario WTForms (y sus subformularios)."""
    if idioma() != "en":
        return formulario
    for campo in formulario:
        if hasattr(campo, "entries"):                  # FieldList: cada entrada es un formulario
            for entrada in campo.entries:
                traducir_formulario(entrada.form)
            continue
        campo.label.text = t(campo.label.text)
        if campo.description:
            campo.description = t(campo.description)
        if getattr(campo, "choices", None):
            campo.choices = [(valor, t(etiqueta) if isinstance(etiqueta, str) else etiqueta)
                             for valor, etiqueta in campo.choices]
        campo.errors = [mensaje(e) for e in campo.errors]
    return formulario

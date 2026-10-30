"""Formularios Flask-WTF (validación + token CSRF).

Aquí van dos ayudantes del panel (F5):
- FormularioBase: muestra en español los pocos mensajes que WTForms trae en inglés;
- poner_errores: pone cada error del modelo junto a su campo del formulario.
"""

from flask_wtf import FlaskForm
from wtforms import SelectMultipleField
from wtforms.widgets import CheckboxInput, ListWidget


class _Traduccion:
    """WTForms pide los textos a este objeto (gettext); sin Babel, basta un diccionario."""

    MENSAJES = {
        "This field is required.": "Este dato es obligatorio.",
        "Not a valid date value.": "Fecha no válida.",
        "Not a valid time value.": "Hora no válida.",
        "Not a valid datetime value.": "Fecha y hora no válidas.",
        "Not a valid integer value.": "Escribe un número entero.",
        "Not a valid decimal value.": "Escribe un número (usa punto para los decimales).",
        "Invalid Choice: could not coerce.": "Elige una opción de la lista.",
        "Not a valid choice.": "Elige una opción de la lista.",
        "Invalid choice(s): one or more data inputs could not be coerced.":
            "Elige opciones de la lista.",
    }

    def gettext(self, texto):
        return self.MENSAJES.get(texto, texto)

    def ngettext(self, singular, plural, cantidad):
        return self.gettext(singular if cantidad == 1 else plural)


class FormularioBase(FlaskForm):
    class Meta:
        def get_translations(self, form):
            return _Traduccion()


class CasillasMultiples(SelectMultipleField):
    """Varias casillas de verificación (por ejemplo, los servicios de una familia)."""

    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


def datos_de(formulario):
    """Los valores del formulario como dict, sin el token CSRF ni el botón."""
    return {nombre: campo.data for nombre, campo in formulario._fields.items()
            if nombre not in ("csrf_token", "enviar")}


def poner_errores(formulario, errores):
    """Pone cada error del modelo junto a su campo. Devuelve los que no tienen campo."""
    sueltos = []
    for nombre, mensaje in errores.items():
        if nombre in formulario:
            campo = formulario[nombre]
            campo.errors = [*campo.errors, mensaje]
        else:
            sueltos.append(mensaje)
    return sueltos

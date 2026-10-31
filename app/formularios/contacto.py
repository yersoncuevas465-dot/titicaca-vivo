"""Formulario de contacto (v2.6). Aquí lo básico (obligatorios, largo y opciones); el correo o
el celular válidos los revisa el modelo (modelos/contacto.py), igual que en la reserva."""

from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

ASUNTOS = [
    ("informacion", "Información de las salidas"),
    ("reserva", "Una reserva que ya hice"),
    ("grupos", "Viaje en grupo o con un colegio"),
    ("otro", "Otro tema"),
]


def _sin_espacios(valor):
    return valor.strip() if isinstance(valor, str) else valor


class FormularioContacto(FlaskForm):
    nombre = StringField("Tu nombre", filters=[_sin_espacios],
                         validators=[DataRequired("Escribe tu nombre."), Length(max=80)],
                         render_kw={"autocomplete": "name"})
    correo = StringField("Correo", filters=[_sin_espacios],
                         validators=[Optional(), Length(max=120)],
                         render_kw={"autocomplete": "email", "inputmode": "email"})
    telefono = StringField("Celular o WhatsApp", filters=[_sin_espacios],
                           validators=[Optional(), Length(max=20)],
                           render_kw={"autocomplete": "tel", "inputmode": "tel"})
    asunto = SelectField("Sobre qué es", choices=ASUNTOS)
    mensaje = TextAreaField(
        "Tu mensaje", filters=[_sin_espacios],
        validators=[DataRequired("Escribe tu mensaje."),
                    Length(min=10, max=1500, message="Escribe entre 10 y 1500 caracteres.")],
        render_kw={"rows": 6})
    # Trampa para robots: va escondida y una persona no la llena. Si llega con texto, el
    # mensaje no se envía (y al robot se le responde como si se hubiera enviado).
    sitio_web = StringField("Deja este campo vacío", validators=[Optional()],
                            render_kw={"autocomplete": "off", "tabindex": "-1"})
    enviar = SubmitField("Enviar mensaje")

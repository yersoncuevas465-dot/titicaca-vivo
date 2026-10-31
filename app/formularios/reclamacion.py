"""Hoja de reclamación (v2.8). Aquí lo básico; los formatos (documento, correo, monto...) los
revisa el modelo (modelos/reclamacion.py), igual que en la reserva."""

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    RadioField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, Optional

from app.formularios.reserva import TIPOS_DOCUMENTO


def _sin_espacios(valor):
    return valor.strip() if isinstance(valor, str) else valor


class FormularioReclamo(FlaskForm):
    tipo = RadioField(
        "¿Reclamo o queja?",
        choices=[("reclamo", "Reclamo: no estoy conforme con el servicio que contraté"),
                 ("queja", "Queja: no estoy conforme con la atención que recibí")],
        validators=[DataRequired("Elige si es un reclamo o una queja.")],
        validate_choice=False)                         # las opciones las revisa el modelo
    nombres = StringField("Nombres", filters=[_sin_espacios],
                          validators=[DataRequired("Escribe tus nombres."), Length(max=80)],
                          render_kw={"autocomplete": "given-name"})
    apellidos = StringField("Apellidos", filters=[_sin_espacios],
                            validators=[DataRequired("Escribe tus apellidos."), Length(max=80)],
                            render_kw={"autocomplete": "family-name"})
    tipo_documento = SelectField("Documento", choices=TIPOS_DOCUMENTO, validate_choice=False)
    numero_documento = StringField("Número de documento", filters=[_sin_espacios],
                                   validators=[DataRequired("Escribe tu número de documento."),
                                               Length(max=20)])
    domicilio = StringField("Domicilio", filters=[_sin_espacios],
                            validators=[DataRequired("Escribe tu domicilio."), Length(max=200)],
                            render_kw={"autocomplete": "street-address"})
    correo = StringField("Correo", filters=[_sin_espacios],
                         validators=[DataRequired("Escribe tu correo."), Length(max=120)],
                         render_kw={"autocomplete": "email", "inputmode": "email"})
    telefono = StringField("Celular (opcional)", filters=[_sin_espacios],
                           validators=[Optional(), Length(max=20)],
                           render_kw={"autocomplete": "tel", "inputmode": "tel"})
    apoderado = StringField("Si eres menor de edad: nombre de tu padre, madre o apoderado",
                            filters=[_sin_espacios], validators=[Optional(), Length(max=120)])
    codigo_reserva = StringField("Código de reserva (si tienes)", filters=[_sin_espacios],
                                 validators=[Optional(), Length(max=10)],
                                 render_kw={"placeholder": "TV-XXXX",
                                            "autocapitalize": "characters"})
    monto = StringField("Monto reclamado en soles (si hay)", filters=[_sin_espacios],
                        validators=[Optional(), Length(max=12)], render_kw={"inputmode": "decimal"})
    servicio = StringField("Servicio contratado", filters=[_sin_espacios],
                           validators=[DataRequired("Describe el servicio."), Length(max=300)],
                           description="Por ejemplo: la salida en lancha del 15 de noviembre.")
    detalle = TextAreaField("Detalle: qué pasó", filters=[_sin_espacios],
                            validators=[DataRequired("Cuéntanos qué pasó."), Length(max=2000)],
                            render_kw={"rows": 6})
    pedido = TextAreaField("Qué pides", filters=[_sin_espacios],
                           validators=[DataRequired("Escribe qué pides."), Length(max=1000)],
                           render_kw={"rows": 3})
    acepto = BooleanField("Declaro que los datos son verdaderos",
                          validators=[DataRequired("Marca la casilla para confirmar que los datos "
                                                   "son verdaderos.")])
    # Trampa para robots (como en Contacto): si llega con texto, la hoja no se registra
    sitio_web = StringField("Deja este campo vacío", validators=[Optional()],
                            render_kw={"autocomplete": "off", "tabindex": "-1"})
    enviar = SubmitField("Registrar la hoja de reclamación")

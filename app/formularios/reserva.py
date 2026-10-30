"""Formularios de la reserva, "Mi reserva" y el reporte de pago.

Aquí se revisa lo básico (campos obligatorios, largo y opciones). Las reglas del negocio
(formato de documentos, teléfono, cupos, duplicados...) las revisa el modelo (RN-09).
"""

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    FieldList,
    Form,
    FormField,
    HiddenField,
    RadioField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, Optional, Regexp

TIPOS_DOCUMENTO = [("DNI", "DNI"), ("CE", "Carné de extranjería"), ("PASAPORTE", "Pasaporte")]
SIN_ELEGIR = (0, "— Elige —")


def _sin_espacios(valor):
    return valor.strip() if isinstance(valor, str) else valor


class FormularioPasajero(Form):
    """Un acompañante (sin token CSRF propio: va dentro del formulario de la reserva)."""

    tipo_documento = SelectField("Documento", choices=TIPOS_DOCUMENTO)
    numero_documento = StringField("Número de documento", filters=[_sin_espacios],
                                   validators=[DataRequired("Escribe el número de documento."),
                                               Length(max=20)])
    nombres = StringField("Nombres", filters=[_sin_espacios],
                          validators=[DataRequired("Escribe los nombres."), Length(max=80)])
    apellidos = StringField("Apellidos", filters=[_sin_espacios],
                            validators=[DataRequired("Escribe los apellidos."), Length(max=80)])
    nacionalidad = StringField("País (código)", filters=[_sin_espacios],
                               validators=[DataRequired("Elige el país."), Length(max=2)],
                               render_kw={"list": "paises", "maxlength": 2,
                                          "autocapitalize": "characters", "placeholder": "PE"})
    tipo_pasajero_id = SelectField("Tipo de pasajero", coerce=int, validate_choice=False)


class FormularioReserva(FlaskForm):
    token_envio = HiddenField()
    titular_tipo_documento = SelectField("Documento", choices=TIPOS_DOCUMENTO)
    titular_numero_documento = StringField(
        "Número de documento", filters=[_sin_espacios],
        validators=[DataRequired("Escribe tu número de documento."), Length(max=20)])
    titular_nombres = StringField("Nombres", filters=[_sin_espacios],
                                  validators=[DataRequired("Escribe tus nombres."), Length(max=80)],
                                  render_kw={"autocomplete": "given-name"})
    titular_apellidos = StringField(
        "Apellidos", filters=[_sin_espacios],
        validators=[DataRequired("Escribe tus apellidos."), Length(max=80)],
        render_kw={"autocomplete": "family-name"})
    titular_nacionalidad = StringField(
        "País (código)", filters=[_sin_espacios],
        validators=[DataRequired("Elige tu país."), Length(max=2)],
        render_kw={"list": "paises", "maxlength": 2, "autocapitalize": "characters",
                   "placeholder": "PE"})
    telefono = StringField("Celular o WhatsApp", filters=[_sin_espacios],
                           validators=[Optional(), Length(max=20)],
                           render_kw={"autocomplete": "tel", "inputmode": "tel"})
    correo = StringField("Correo", filters=[_sin_espacios],
                         validators=[Optional(), Length(max=120)],
                         render_kw={"autocomplete": "email", "inputmode": "email"})
    titular_viaja = BooleanField("Yo también viajo", default=True)
    titular_tipo_pasajero_id = SelectField("Tu tipo de pasajero", coerce=int, validate_choice=False)
    acompanantes = FieldList(FormField(FormularioPasajero), min_entries=0, max_entries=9)
    metodo_pago = RadioField(
        "¿Cómo vas a pagar?",
        choices=[("yape", "Yape"), ("plin", "Plin"), ("muelle", "En el muelle, antes de subir")],
        validators=[DataRequired("Elige cómo vas a pagar.")],
    )
    enviar = SubmitField("Confirmar reserva")


class FormularioMiReserva(FlaskForm):
    codigo = StringField(
        "Código de reserva", filters=[lambda v: v.strip().upper() if isinstance(v, str) else v],
        validators=[DataRequired("Escribe el código de tu reserva."),
                    Regexp(r"^TV-[A-HJKMNP-Z2-9]{4}$",
                           message="El código tiene la forma TV-XXXX.")],
        render_kw={"autocapitalize": "characters", "placeholder": "TV-XXXX", "maxlength": 7})
    numero_documento = StringField(
        "Número de documento del titular", filters=[_sin_espacios],
        validators=[DataRequired("Escribe el número de documento."), Length(max=20)])
    enviar = SubmitField("Ver mi reserva")


class FormularioPago(FlaskForm):
    metodo = RadioField("¿Con qué pagaste?", choices=[("yape", "Yape"), ("plin", "Plin")],
                        validators=[DataRequired("Elige Yape o Plin.")])
    monto = StringField("Monto pagado (S/)", filters=[_sin_espacios],
                        validators=[DataRequired("Escribe el monto.")],
                        render_kw={"inputmode": "decimal"})
    numero_operacion = StringField("Número de operación", filters=[_sin_espacios],
                                   validators=[DataRequired("Escribe el número de operación.")])
    enviar = SubmitField("Reportar pago")


class FormularioReprogramar(FlaskForm):
    """RN-11: elegir otra salida de la misma ruta (las opciones las carga la ruta)."""

    salida_id = RadioField("Nueva salida", coerce=int, validate_choice=False,
                           validators=[DataRequired("Elige una salida.")])
    enviar = SubmitField("Pasar mi reserva a esta salida")


class FormularioResena(FlaskForm):
    puntuacion = RadioField("¿Cuántas estrellas le das?", coerce=int,
                            choices=[(5, "★★★★★ Excelente"), (4, "★★★★ Muy bueno"),
                                     (3, "★★★ Bueno"), (2, "★★ Regular"), (1, "★ Malo")],
                            validators=[DataRequired("Elige de 1 a 5 estrellas.")])
    comentario = TextAreaField("Comentario", filters=[_sin_espacios],
                               validators=[Optional(), Length(max=1000)],
                               render_kw={"rows": 4, "maxlength": 1000})
    enviar = SubmitField("Enviar mi opinión")

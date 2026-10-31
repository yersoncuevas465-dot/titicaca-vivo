"""Pedido de cotización para grupos (v2.8). Las rutas (opciones) las pone la ruta desde la base;
los formatos y los rangos los revisa el modelo (modelos/contacto.py)."""

from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

TIPOS_GRUPO = [
    ("colegio", "Colegio"),
    ("universidad", "Universidad o instituto"),
    ("empresa", "Empresa o institución"),
    ("familia", "Familia o amigos"),
    ("otro", "Otro grupo"),
]


def _sin_espacios(valor):
    return valor.strip() if isinstance(valor, str) else valor


class FormularioGrupo(FlaskForm):
    tipo = SelectField("Tipo de grupo", choices=TIPOS_GRUPO, validate_choice=False)
    institucion = StringField("Nombre del colegio, empresa o grupo (opcional)",
                              filters=[_sin_espacios],
                              validators=[Optional(), Length(max=120)],
                              render_kw={"autocomplete": "organization"})
    # Número y fecha como texto: así el error sale en español desde el modelo (WTForms lo
    # daría en inglés). El navegador igual muestra su selector de número y de fecha.
    personas = StringField("¿Cuántas personas?", filters=[_sin_espacios],
                           validators=[DataRequired("Escribe cuántas personas son.")],
                           render_kw={"type": "number", "inputmode": "numeric",
                                      "min": 2, "max": 300})
    fecha = StringField("Fecha que prefieren", validators=[DataRequired("Elige la fecha.")],
                        render_kw={"type": "date"})
    ruta = SelectField("Ruta", validate_choice=False)
    nombre = StringField("Tu nombre", filters=[_sin_espacios],
                         validators=[DataRequired("Escribe tu nombre."), Length(max=80)],
                         render_kw={"autocomplete": "name"})
    correo = StringField("Correo", filters=[_sin_espacios],
                         validators=[Optional(), Length(max=120)],
                         render_kw={"autocomplete": "email", "inputmode": "email"})
    telefono = StringField("Celular o WhatsApp", filters=[_sin_espacios],
                           validators=[Optional(), Length(max=20)],
                           render_kw={"autocomplete": "tel", "inputmode": "tel"})
    comentarios = TextAreaField("Algo más que debamos saber (opcional)", filters=[_sin_espacios],
                                validators=[Optional(), Length(max=1000)], render_kw={"rows": 4})
    sitio_web = StringField("Deja este campo vacío", validators=[Optional()],
                            render_kw={"autocomplete": "off", "tabindex": "-1"})
    enviar = SubmitField("Pedir cotización")

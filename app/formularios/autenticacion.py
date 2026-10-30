"""Formularios de la cuenta del personal (Flask-WTF trae el token CSRF):
/entrar, recuperar la contraseña (2 pasos) y Mi cuenta."""

from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

from app.formularios import FormularioBase

AYUDA_CONTRASENA = ("Al menos 10 caracteres, con letras y números, sin espacios y sin tu "
                    "nombre de usuario.")


def _sin_espacios(valor):
    return valor.strip() if isinstance(valor, str) else valor


def _clave(etiqueta, mensaje, autocompletar, ayuda=None):
    return PasswordField(etiqueta, validators=[DataRequired(mensaje), Length(max=128)],
                         render_kw={"autocomplete": autocompletar}, description=ayuda)


class FormularioEntrar(FormularioBase):
    nombre_usuario = StringField(
        "Usuario o correo",
        filters=[_sin_espacios],
        validators=[DataRequired("Escribe tu nombre de usuario o tu correo."), Length(max=120)],
        render_kw={"autocomplete": "username", "autocapitalize": "none", "spellcheck": "false"},
    )
    contrasena = _clave("Contraseña", "Escribe tu contraseña.", "current-password")
    enviar = SubmitField("Entrar")


class FormularioPedirCodigo(FormularioBase):
    identificador = StringField(
        "Usuario o correo",
        filters=[_sin_espacios],
        validators=[DataRequired("Escribe tu nombre de usuario o tu correo."), Length(max=120)],
        render_kw={"autocomplete": "username", "autocapitalize": "none", "spellcheck": "false"},
    )
    enviar = SubmitField("Enviarme el código")


class FormularioCodigo(FormularioBase):
    codigo = StringField(
        "Código de 6 dígitos",
        filters=[_sin_espacios],
        validators=[DataRequired("Escribe el código que te llegó por correo."), Length(max=6)],
        render_kw={"inputmode": "numeric", "autocomplete": "one-time-code", "maxlength": "6",
                   "pattern": "[0-9]{6}"},
    )
    contrasena = _clave("Contraseña nueva", "Escribe la contraseña nueva.", "new-password",
                        AYUDA_CONTRASENA)
    repetir = _clave("Repite la contraseña nueva", "Repite la contraseña nueva.", "new-password")
    enviar = SubmitField("Cambiar mi contraseña")


class FormularioCambiarContrasena(FormularioBase):
    actual = _clave("Contraseña actual", "Escribe tu contraseña actual.", "current-password")
    nueva = _clave("Contraseña nueva", "Escribe la contraseña nueva.", "new-password",
                   AYUDA_CONTRASENA)
    repetir = _clave("Repite la contraseña nueva", "Repite la contraseña nueva.", "new-password")
    enviar = SubmitField("Cambiar mi contraseña")


class FormularioContacto(FormularioBase):
    correo = StringField("Correo", filters=[_sin_espacios],
                         validators=[Optional(), Length(max=120)],
                         render_kw={"inputmode": "email", "autocomplete": "email"},
                         description="A este correo llega el código si olvidas tu contraseña.")
    telefono = StringField("Celular", filters=[_sin_espacios],
                           validators=[Optional(), Length(max=16)],
                           render_kw={"inputmode": "tel", "autocomplete": "tel"},
                           description="9 dígitos que empiezan en 9, o +código del país.")
    confirmar = _clave("Tu contraseña actual", "Escribe tu contraseña actual para confirmar.",
                       "current-password",
                       "Para que nadie cambie tu correo si dejas la sesión abierta.")
    enviar = SubmitField("Guardar mis datos")

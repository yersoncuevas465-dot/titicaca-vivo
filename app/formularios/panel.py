"""Formularios de la operación del panel (F5): salidas, pagos y abordaje.

Aquí se revisa lo básico (obligatorio, tipo, largo). Las reglas del negocio (RN-07, RN-06,
RN-12...) las revisa el modelo y sus errores vuelven a cada campo con poner_errores().
"""

from wtforms import (
    DateField,
    DateTimeLocalField,
    HiddenField,
    IntegerField,
    RadioField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
    TimeField,
)
from wtforms.validators import DataRequired, InputRequired, Length, Optional

from app.formularios import FormularioBase


def _sin_espacios(valor):
    return valor.strip() if isinstance(valor, str) else valor


class FormularioSalida(FormularioBase):
    ruta_id = SelectField("Ruta", coerce=int, validate_choice=False)
    embarcacion_id = SelectField("Lancha", coerce=int, validate_choice=False)
    capitan_id = SelectField("Capitán", coerce=int, validate_choice=False)
    guia_id = SelectField("Guía", coerce=int, validate_choice=False)
    fecha = DateField("Fecha de zarpe", validators=[InputRequired("Elige la fecha.")])
    hora = TimeField("Hora de zarpe", validators=[InputRequired("Elige la hora.")])
    cupo = IntegerField("Cupo (lugares a la venta)",
                        validators=[InputRequired("Escribe cuántos lugares se venden.")])
    enviar = SubmitField("Guardar salida")


class FormularioMotivo(FormularioBase):
    """Suspender o cancelar una salida: el motivo queda en la salida y en la bitácora."""

    motivo = StringField("Motivo", filters=[_sin_espacios],
                         validators=[DataRequired("Escribe el motivo."), Length(max=255)])
    enviar = SubmitField("Confirmar")


class FormularioAccion(FormularioBase):
    """Botón de una sola acción (marcar el zarpe, verificar un pago): solo lleva el CSRF."""


class FormularioRechazo(FormularioBase):
    observacion = StringField("Motivo del rechazo", filters=[_sin_espacios],
                              validators=[DataRequired("Escribe por qué se rechaza."),
                                          Length(max=255)])
    enviar = SubmitField("Rechazar")


class FormularioCobro(FormularioBase):
    metodo = RadioField("¿Cómo pagó?", choices=[("efectivo_muelle", "Efectivo"),
                                                ("pos", "Tarjeta (POS)"),
                                                ("transferencia", "Transferencia")],
                        validators=[DataRequired("Elige cómo pagó.")])
    monto = StringField("Monto cobrado (S/)", filters=[_sin_espacios],
                        validators=[DataRequired("Escribe el monto.")],
                        render_kw={"inputmode": "decimal"})
    numero_operacion = StringField("N.° de operación (POS o transferencia)",
                                   filters=[_sin_espacios], validators=[Optional(), Length(max=30)])
    enviar = SubmitField("Registrar cobro")


class FormularioAbordaje(FormularioBase):
    """Los pasajeros marcados llegan como casillas name="pasajero" (una por persona)."""

    metodo = HiddenField(default="qr")
    enviar = SubmitField("Confirmar abordaje")


class FormularioBuscarReserva(FormularioBase):
    """Buscar una reserva por código (GET, sin CSRF): para el abordaje manual en el muelle."""

    class Meta:
        csrf = False

    codigo = StringField("Código de reserva",
                         filters=[lambda v: v.strip().upper() if isinstance(v, str) else v],
                         validators=[DataRequired("Escribe el código.")],
                         render_kw={"placeholder": "TV-XXXX", "maxlength": 7,
                                    "autocapitalize": "characters"})


# --- F6: alertas, hospedajes y devoluciones ---------------------------------------------------

class FormularioAlerta(FormularioBase):
    titulo = StringField("Título", filters=[_sin_espacios],
                         validators=[DataRequired("Escribe el título."), Length(max=120)])
    tipo = SelectField("Tipo", choices=[("oleaje", "Oleaje"), ("tormenta", "Tormenta"),
                                        ("helada", "Helada"), ("neblina", "Neblina"),
                                        ("granizo", "Granizo"), ("otro", "Otro")])
    nivel = SelectField("Nivel", choices=[("verde", "Verde"), ("amarillo", "Amarillo"),
                                          ("naranja", "Naranja (afecta salidas)"),
                                          ("rojo", "Rojo (afecta salidas)")])
    fuente = SelectField("Fuente", choices=[("SENAMHI", "SENAMHI"),
                                            ("Capitania", "Capitanía de Puerto"),
                                            ("Agencia", "Agencia"), ("Comunidad", "Comunidad")])
    comunidad_id = SelectField("Lugar", coerce=int, validate_choice=False)
    vigente_desde = DateTimeLocalField("Rige desde", format="%Y-%m-%dT%H:%M",
                                       validators=[InputRequired("Elige desde cuándo rige.")])
    vigente_hasta = DateTimeLocalField("Rige hasta", format="%Y-%m-%dT%H:%M",
                                       validators=[InputRequired("Elige hasta cuándo rige.")])
    descripcion = TextAreaField("Descripción (la ve el turista)",
                                validators=[Optional(), Length(max=2000)], render_kw={"rows": 3})
    enviar = SubmitField("Guardar alerta")


class FormularioReasignar(FormularioBase):
    familia_id = SelectField("Nueva familia", coerce=int, validate_choice=False)
    motivo = StringField("Motivo (queda en la bitácora)", filters=[_sin_espacios],
                         validators=[DataRequired("Escribe el motivo."), Length(max=255)])
    enviar = SubmitField("Reasignar la noche")


class FormularioNota(FormularioBase):
    """Devolución atendida: cómo se devolvió el dinero (queda en la bitácora)."""

    nota = StringField("¿Cómo se devolvió?", filters=[_sin_espacios],
                       validators=[DataRequired("Escribe cómo se devolvió."), Length(max=255)])
    enviar = SubmitField("Marcar como devuelta")

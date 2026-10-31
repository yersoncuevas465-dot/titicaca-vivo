"""Formularios de los catálogos y de los usuarios (F5).

Los campos se llaman igual que las columnas de la tabla. Las opciones de las listas que
salen de la base (rutas, comunidades, roles...) las carga la ruta antes de mostrarlos.
"""

from wtforms import (
    BooleanField,
    DateField,
    DecimalField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import InputRequired, Length, Optional

from app.formularios import CasillasMultiples, FormularioBase


def _sin_espacios(valor):
    return valor.strip() if isinstance(valor, str) else valor


def _texto(etiqueta, maximo, obligatorio=True, **opciones):
    validadores = [InputRequired(f"Escribe {etiqueta.lower()}.")] if obligatorio else [Optional()]
    return StringField(etiqueta, filters=[_sin_espacios],
                       validators=[*validadores, Length(max=maximo)], **opciones)


class FormularioComunidad(FormularioBase):
    nombre = _texto("Nombre", 80)
    slug = _texto("Slug (dirección de la ficha)", 80, obligatorio=False,
                  description="Vacío = se arma con el nombre. Cambiarlo cambia la dirección "
                              "de la ficha y el nombre de la foto (<slug>.webp).")
    distrito = _texto("Distrito", 60)
    provincia = _texto("Provincia", 60)
    idioma_originario = SelectField("Idioma originario",
                                    choices=[("quechua", "Quechua"), ("aimara", "Aimara")])
    senal = SelectField("Señal de celular", choices=[("buena", "Buena"), ("debil", "Débil"),
                                                     ("sin_senal", "Sin señal")])
    whatsapp_contacto = _texto("WhatsApp de contacto", 16, obligatorio=False,
                               render_kw={"inputmode": "tel"})
    descripcion = TextAreaField("Descripción", validators=[Optional(), Length(max=2000)],
                                render_kw={"rows": 4})
    foto_credito = _texto("Crédito de la foto", 200, obligatorio=False)
    latitud = DecimalField("Latitud", places=6, validators=[Optional()],
                           render_kw={"step": "0.000001"})
    longitud = DecimalField("Longitud", places=6, validators=[Optional()],
                            render_kw={"step": "0.000001"})
    tiene_hospedaje = BooleanField("Recibe hospedaje vivencial")
    activa = BooleanField("Activa", default=True)
    enviar = SubmitField("Guardar comunidad")


class FormularioFamilia(FormularioBase):
    comunidad_id = SelectField("Comunidad", coerce=int, validate_choice=False)
    nombre_familia = _texto("Nombre de la familia (o de la casa)", 80)
    responsable = _texto("Responsable", 120)
    telefono = _texto("Teléfono", 16, obligatorio=False, render_kw={"inputmode": "tel"})
    capacidad_personas = IntegerField("Capacidad (personas por noche)",
                                      validators=[InputRequired("Escribe la capacidad.")])
    servicios = CasillasMultiples("Servicios", choices=[
        ("desayuno", "Desayuno"), ("almuerzo", "Almuerzo"), ("cena", "Cena"),
        ("vestimenta", "Vestimenta típica"), ("taller_textil", "Taller textil")])
    activa = BooleanField("Activa", default=True)
    enviar = SubmitField("Guardar familia")


class FormularioEmbarcacion(FormularioBase):
    nombre = _texto("Nombre", 60)
    matricula = _texto("Matrícula", 20, render_kw={"autocapitalize": "characters"})
    capacidad_maxima = IntegerField("Capacidad máxima (personas)",
                                    validators=[InputRequired("Escribe la capacidad.")])
    tipo = SelectField("Tipo", choices=[("lancha", "Lancha"), ("deslizador", "Deslizador"),
                                        ("balsa_totora", "Balsa de totora")])
    estado = SelectField("Estado", choices=[("operativa", "Operativa"),
                                            ("mantenimiento", "En mantenimiento"),
                                            ("baja", "De baja")])
    ultimo_mantenimiento = DateField("Último mantenimiento", validators=[Optional()])
    enviar = SubmitField("Guardar lancha")


class FormularioRuta(FormularioBase):
    codigo = _texto("Código", 12, render_kw={"autocapitalize": "characters"})
    nombre = _texto("Nombre", 100)
    descripcion = TextAreaField("Descripción", validators=[Optional(), Length(max=2000)],
                                render_kw={"rows": 3})
    duracion_horas = DecimalField("Duración (horas)", places=1,
                                  validators=[InputRequired("Escribe la duración.")],
                                  render_kw={"step": "0.5"})
    incluye_pernocte = BooleanField("Incluye una noche con familia anfitriona")
    muelle_salida = _texto("Muelle de salida", 100)
    activa = BooleanField("Activa", default=True)
    enviar = SubmitField("Guardar ruta")


class FormularioParada(FormularioBase):
    comunidad_id = SelectField("Comunidad", coerce=int, validate_choice=False)
    orden = IntegerField("Orden de visita", validators=[InputRequired("Escribe el orden.")])
    minutos_estadia = IntegerField("Minutos de estadía",
                                   validators=[InputRequired("Escribe los minutos.")])
    es_pernocte = BooleanField("Aquí se duerme (pernocte)")
    enviar = SubmitField("Guardar parada")


class FormularioTarifa(FormularioBase):
    ruta_id = SelectField("Ruta", coerce=int, validate_choice=False)
    tipo_pasajero_id = SelectField("Tipo de pasajero", coerce=int, validate_choice=False)
    precio_base = DecimalField("Precio base (S/)", places=2,
                               validators=[InputRequired("Escribe el precio.")],
                               render_kw={"step": "0.01"})
    vigente_desde = DateField("Vigente desde", validators=[InputRequired("Elige la fecha.")])
    vigente_hasta = DateField("Vigente hasta (vacío = sin fin)", validators=[Optional()])
    enviar = SubmitField("Guardar tarifa")


class FormularioTemporada(FormularioBase):
    nombre = _texto("Nombre", 60)
    fecha_inicio = DateField("Desde", validators=[InputRequired("Elige la fecha.")])
    fecha_fin = DateField("Hasta", validators=[InputRequired("Elige la fecha.")])
    recargo_porcentaje = DecimalField("Recargo (%)", places=2,
                                      validators=[InputRequired("Escribe el recargo.")],
                                      render_kw={"step": "0.01"})
    enviar = SubmitField("Guardar temporada")


class FormularioTipoPasajero(FormularioBase):
    nombre = _texto("Nombre", 40)
    edad_minima = IntegerField("Edad mínima", validators=[InputRequired("Escribe la edad.")])
    edad_maxima = IntegerField("Edad máxima (vacío = sin límite)", validators=[Optional()])
    enviar = SubmitField("Guardar tipo")


class FormularioUsuario(FormularioBase):
    nombre_usuario = _texto("Usuario", 30, render_kw={"autocapitalize": "none",
                                                     "autocomplete": "off"})
    nombre_completo = _texto("Nombre completo", 120)
    correo = _texto("Correo", 120, obligatorio=False, render_kw={"inputmode": "email"})
    telefono = _texto("Teléfono", 16, obligatorio=False, render_kw={"inputmode": "tel"})
    rol_id = SelectField("Rol", coerce=int, validate_choice=False)
    comunidad_id = SelectField("Comunidad (guías y residentes)", coerce=int, validate_choice=False)
    licencia_navegacion = _texto("Licencia de navegación (solo capitanes)", 30,
                                 obligatorio=False)
    contrasena = PasswordField("Contraseña", validators=[Optional(), Length(max=128)],
                               render_kw={"autocomplete": "new-password"},
                               description="Al menos 10 caracteres. Al editar, déjala vacía "
                                           "para no cambiarla.")
    activo = BooleanField("Activo", default=True)
    enviar = SubmitField("Guardar usuario")

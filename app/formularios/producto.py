"""Formulario de un producto (v2.9): lo llena el residente (los suyos) o el operador (los de la
agencia). Aquí solo lo básico; el precio, la categoría y la comunidad los revisa el modelo."""

from flask_wtf.file import FileField
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length

from app.formularios import FormularioBase
from app.modelos.producto import CATEGORIAS


def _sin_espacios(valor):
    return valor.strip() if isinstance(valor, str) else valor


class FormularioProducto(FormularioBase):
    nombre = StringField("Nombre del producto", filters=[_sin_espacios],
                         validators=[DataRequired("Escribe el nombre del producto."),
                                     Length(max=80)],
                         description="Por ejemplo: chullo tejido a mano.")
    categoria = SelectField("Categoría", choices=list(CATEGORIAS.items()), validate_choice=False)
    precio = StringField("Precio en soles", filters=[_sin_espacios],
                         validators=[DataRequired("Escribe el precio."), Length(max=10)],
                         render_kw={"inputmode": "decimal"}, description="Por ejemplo: 60 o 12.50")
    descripcion = TextAreaField("Características", filters=[_sin_espacios],
                                validators=[DataRequired("Cuenta sus características."),
                                            Length(max=600)],
                                render_kw={"rows": 4},
                                description="Material, medidas, colores y quién lo hizo.")
    # Solo para el operador (los de la agencia): el residente publica en su comunidad
    comunidad_id = SelectField("Dónde está", coerce=int, validate_choice=False)
    lugar = StringField("Dónde lo encuentran", filters=[_sin_espacios],
                        validators=[DataRequired("Escribe dónde lo encuentran."), Length(max=160)],
                        description="Por ejemplo: tienda comunal de la plaza, o mi casa junto al "
                                    "muelle.")
    # D-121: la revisa servicios/fotos.py (que de verdad sea una imagen) y la deja en 640×400
    foto = FileField("Foto del producto (opcional)",
                     description="Una foto clara del producto: JPG, PNG o WebP de hasta 8 MB.",
                     render_kw={"accept": "image/jpeg,image/png,image/webp"})
    enviar = SubmitField("Guardar producto")

"""El formulario del panel para subir el QR de Yape y el de Plin (solo el admin)."""

from flask_wtf.file import FileField
from wtforms import SubmitField

from app.formularios import FormularioBase


class FormularioCobro(FormularioBase):
    qr_yape = FileField("QR de Yape")
    qr_plin = FileField("QR de Plin")
    enviar = SubmitField("Guardar el QR")

"""Envío de correos: por ahora, el código para recuperar la contraseña (D-111).

Con CORREO_SIMULAR=1 (el valor por defecto) no sale nada a internet: el mensaje se escribe
en la ventana donde corre el servidor (la de INICIAR.bat o la terminal de VS Code). Así la
demostración funciona sin internet y sin una cuenta de correo. Para enviarlo de verdad se
pone CORREO_SIMULAR=0 y los datos SMTP en el .env (con Gmail, una "contraseña de aplicación").

El registro (logs/app.log) nunca guarda el texto del correo: llevaría el código.
"""

import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app

SIMULADO, ENVIADO, FALLO = "simulado", "enviado", "error"


def oculto(correo):
    """e***@titicaca-vivo.example: para el registro, sin el correo completo."""
    usuario, _, dominio = (correo or "").partition("@")
    return f"{usuario[:1]}***@{dominio}" if dominio else "(sin correo)"


def enviar(destino, asunto, texto):
    """Devuelve SIMULADO, ENVIADO o FALLO. Nunca lanza: un correo que falla no rompe la página."""
    config = current_app.config
    if config["CORREO_SIMULAR"]:
        sangria = "\n".join(f"      {linea}" for linea in texto.splitlines())
        print(f"\n  [CORREO SIMULADO] Para: {destino}\n  Asunto: {asunto}\n{sangria}\n", flush=True)
        current_app.logger.info("Correo simulado a %s: %s", oculto(destino), asunto)
        return SIMULADO

    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = config["SMTP_REMITENTE"] or config["SMTP_USUARIO"]
    mensaje["To"] = destino
    mensaje.set_content(texto)
    try:
        # timeout: si la red o el servidor de correo no responden, la página no se cuelga
        with smtplib.SMTP(config["SMTP_HOST"], config["SMTP_PUERTO"], timeout=15) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(config["SMTP_USUARIO"], config["SMTP_CONTRASENA"])
            smtp.send_message(mensaje)
    except (OSError, smtplib.SMTPException) as error:
        current_app.logger.error("No se pudo enviar el correo a %s: %r", oculto(destino), error)
        return FALLO
    current_app.logger.info("Correo enviado a %s: %s", oculto(destino), asunto)
    return ENVIADO

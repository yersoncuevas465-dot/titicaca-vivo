"""Configuración de Titicaca Vivo. Todo sale del archivo .env (los secretos nunca van en el código).

Para Platino (otro servidor de base de datos) solo se cambian las variables BD_* del .env.
"""

import os
import tempfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ_PROYECTO / ".env")

ENTORNO = os.getenv("ENTORNO", "desarrollo")


class Config:
    VERSION = "2.9.0"             # también sirve para que el navegador renueve CSS e imágenes
    ENTORNO = ENTORNO
    SECRET_KEY = os.getenv("SECRET_KEY")

    BD_HOST = os.getenv("BD_HOST", "127.0.0.1")
    BD_PUERTO = int(os.getenv("BD_PUERTO", "3306"))
    BD_USUARIO = os.getenv("BD_USUARIO", "titicaca_app")
    BD_CONTRASENA = os.getenv("BD_CONTRASENA", "")
    BD_NOMBRE = os.getenv("BD_NOMBRE", "titicaca_vivo")
    CARPETA_SQL = RAIZ_PROYECTO / "database"

    ZONA_HORARIA = "America/Lima"
    # RN-05: minutos que se guarda el cupo de una reserva Yape/Plin sin pago reportado
    MINUTOS_VENCIMIENTO_PAGO = int(os.getenv("MINUTOS_VENCIMIENTO_PAGO", "120"))
    # P3 (F0): soles por persona y noche para la familia anfitriona
    PAGO_FAMILIA_PERSONA_NOCHE = Decimal(os.getenv("PAGO_FAMILIA_PERSONA_NOCHE", "40.00"))
    # Máximo de pasajeros en una reserva (una familia anfitriona recibe hasta 10)
    MAX_PASAJEROS_POR_RESERVA = 10
    # Datos de cobro de la agencia que ve el turista al pagar con Yape o Plin
    YAPE_NUMERO = os.getenv("YAPE_NUMERO", "")
    PLIN_NUMERO = os.getenv("PLIN_NUMERO", "")
    TITULAR_COBRO = os.getenv("TITULAR_COBRO", "")
    # URL base que va dentro del QR del boleto (la que abre el celular del guía).
    # Vacía = la del servidor que atiende la petición.
    URL_PUBLICA = os.getenv("URL_PUBLICA", "")

    # Registro (logs/app.log), en hora de Lima. None = no escribir archivo.
    LOG_ARCHIVO = RAIZ_PROYECTO / "logs" / "app.log"

    # Cookies de sesión (sección 11): HttpOnly, SameSite=Lax y Secure en producción.
    SESSION_COOKIE_NAME = "titicaca_sesion"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = ENTORNO == "produccion"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)

    # Límite de intentos fallidos en /entrar (sección 11). Se guarda en memoria: vale por proceso.
    LIMITE_INTENTOS_ENTRAR = "5 per 15 minutes"
    # D-110: la sesión del personal se cierra sola tras estos minutos sin actividad.
    SESION_INACTIVA_MIN = int(os.getenv("SESION_INACTIVA_MIN", "30"))

    # D-111: recuperar la contraseña con un código de 6 dígitos que llega por correo.
    MINUTOS_CODIGO_RECUPERACION = 15
    LIMITE_PEDIR_CODIGO = "5 per 15 minutes"      # pedidos de código por IP
    # Códigos equivocados por IP: más que los 5 de cada código, para poder pedir uno nuevo.
    LIMITE_INTENTOS_CODIGO = "10 per 15 minutes"
    # Correo: con CORREO_SIMULAR=1 (por defecto) no sale nada a internet y el mensaje se
    # muestra en la ventana del servidor. Para enviarlo de verdad: CORREO_SIMULAR=0 y SMTP_*.
    CORREO_SIMULAR = os.getenv("CORREO_SIMULAR", "1") != "0"
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PUERTO = int(os.getenv("SMTP_PUERTO", "587"))
    SMTP_USUARIO = os.getenv("SMTP_USUARIO", "")
    # Gmail muestra la "contraseña de aplicación" con espacios: se quitan.
    SMTP_CONTRASENA = os.getenv("SMTP_CONTRASENA", "").replace(" ", "")
    SMTP_REMITENTE = os.getenv("SMTP_REMITENTE", "")

    # D-116: respaldos de la base en la carpeta respaldos/ (fuera del ZIP de entrega y de git).
    RESPALDOS_CARPETA = Path(os.getenv("RESPALDOS_CARPETA") or RAIZ_PROYECTO / "respaldos")
    RESPALDO_AUTOMATICO = os.getenv("RESPALDO_AUTOMATICO", "1") != "0"
    RESPALDO_CADA_HORAS = int(os.getenv("RESPALDO_CADA_HORAS", "24"))
    RESPALDOS_CONSERVAR = int(os.getenv("RESPALDOS_CONSERVAR", "15"))

    # v2.2: APIs externas públicas y sin clave (servicios/externas.py). Solo las llama el
    # servidor, con tiempo de espera corto y caché: si una no responde, la página sale sin ese
    # dato. APIS_EXTERNAS=0 las apaga todas (sin internet, la app funciona igual).
    APIS_EXTERNAS = os.getenv("APIS_EXTERNAS", "1") != "0"
    APIS_TIMEOUT = float(os.getenv("APIS_TIMEOUT", "4"))
    RENIEC_API_URL = os.getenv("RENIEC_API_URL", "https://graphperu.daustinn.com/api/query")
    # Consultas de DNI por IP: una reserva lleva hasta 10 pasajeros (y alguno se escribe mal).
    LIMITE_CONSULTAS_DNI = "25 per 10 minutes;120 per day"
    TIPO_CAMBIO_API_URL = os.getenv("TIPO_CAMBIO_API_URL", "https://api.apis.net.pe/v1/tipo-cambio-sunat")
    CLIMA_API_URL = os.getenv("CLIMA_API_URL", "https://api.open-meteo.com/v1/forecast")
    CLIMA_LUGAR = (-15.84, -70.02)           # bahía de Puno, donde zarpan las lanchas
    FERIADOS_API_URL = os.getenv("FERIADOS_API_URL", "https://date.nager.at/api/v3/PublicHolidays")

    # v2.6: atención de la agencia (página Contacto y pie de página). Vacío = no se muestra.
    # Los mensajes del formulario llegan a AGENCIA_CORREO o, si está vacío, a los operadores
    # activos que tienen correo (los mismos de la recuperación de contraseña).
    AGENCIA_CORREO = os.getenv("AGENCIA_CORREO", "")
    AGENCIA_WHATSAPP = os.getenv("AGENCIA_WHATSAPP", "")       # 9XXXXXXXX o +código del país
    AGENCIA_HORARIO = os.getenv("AGENCIA_HORARIO", "")
    LIMITE_MENSAJES_CONTACTO = "5 per hour"                    # por IP
    # v2.8: el libro de reclamaciones muestra la razón social y el RUC del proveedor
    AGENCIA_RAZON_SOCIAL = os.getenv("AGENCIA_RAZON_SOCIAL", "Titicaca Vivo")
    AGENCIA_RUC = os.getenv("AGENCIA_RUC", "")
    LIMITE_HOJAS_RECLAMACION = "5 per hour"                    # por IP
    LIMITE_COTIZACIONES_GRUPO = "5 per hour"                   # por IP

    WTF_CSRF_TIME_LIMIT = 4 * 3600           # el formulario vale 4 horas (señal lenta)
    MAX_CONTENT_LENGTH = 1 * 1024 * 1024     # los formularios no suben archivos grandes
    # CSS e imágenes: en producción, 1 día en la caché del navegador (se renuevan al cambiar
    # VERSION); en desarrollo, sin caché para ver cada cambio al instante.
    SEND_FILE_MAX_AGE_DEFAULT = 86400 if ENTORNO == "produccion" else 0


class ConfigPruebas(Config):
    """Las pruebas usan una base aparte, que se borra y se vuelve a crear."""

    TESTING = True
    SECRET_KEY = "clave-solo-para-pruebas"  # noqa: S105 (solo firma cookies de prueba)
    BD_NOMBRE = os.getenv("BD_NOMBRE_PRUEBAS", "titicaca_vivo_pruebas")
    LOG_ARCHIVO = None
    SESSION_COOKIE_SECURE = False
    CORREO_SIMULAR = True                    # las pruebas nunca mandan correos de verdad
    APIS_EXTERNAS = False                    # ni salen a internet (test_apis.py las simula)
    # Los datos de la agencia no salen del .env de quien corre las pruebas: así dan lo mismo
    # en cualquier PC (cada prueba que los necesita los pone ella misma).
    AGENCIA_CORREO = AGENCIA_WHATSAPP = AGENCIA_HORARIO = AGENCIA_RUC = ""
    AGENCIA_RAZON_SOCIAL = "Titicaca Vivo"
    SESION_INACTIVA_MIN = 30
    # Los respaldos de las pruebas van a la carpeta temporal del sistema, no a respaldos/
    RESPALDOS_CARPETA = Path(tempfile.gettempdir()) / "titicaca_vivo_respaldos_pruebas"
    RESPALDO_AUTOMATICO = False

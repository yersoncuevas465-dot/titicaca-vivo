"""Filtros de Jinja para mostrar fechas, dinero y estados, sin depender del locale de Windows.

En las páginas del turista salen en español o en inglés (textos.idioma()); en el panel, en español.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.servicios import paises, privacidad, textos
from app.servicios.textos import t

DIAS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
DIAS_LARGOS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "set", "oct", "nov", "dic")
MESES_LARGOS = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                "setiembre", "octubre", "noviembre", "diciembre")
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
LONG_DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
LONG_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December")

ESTADOS_PUBLICOS = {
    "disponible": "Disponible",
    "pocos_cupos": "Pocos cupos",
    "llena": "Llena",
    "suspendida": "Suspendida",
    "zarpo": "Zarpó",
    "cancelada": "Cancelada",
}

ESTADOS_RESERVA = {
    "pendiente_pago": "Pendiente de pago",
    "confirmada": "Confirmada (pagas en el muelle)",
    "pagada": "Pagada",
    "abordada": "Abordada",
    "cancelada": "Cancelada",
    "vencida": "Vencida (no se pagó a tiempo)",
    "no_show": "No se presentó",
}
METODOS_PAGO = {"yape": "Yape", "plin": "Plin", "muelle": "En el muelle",
                "efectivo_muelle": "Efectivo en el muelle", "transferencia": "Transferencia",
                "pos": "Tarjeta (POS)"}
ESTADOS_PAGO = {"reportado": "Por verificar", "verificado": "Verificado", "rechazado": "Rechazado"}

NIVELES_ALERTA = {"verde": "Verde", "amarillo": "Amarilla", "naranja": "Naranja", "rojo": "Roja"}
TIPOS_ALERTA = {"oleaje": "Oleaje", "tormenta": "Tormenta", "helada": "Helada",
                "neblina": "Neblina", "granizo": "Granizo", "otro": "Aviso"}
IDIOMAS = {"quechua": "Quechua", "aimara": "Aimara"}
# Acciones de la bitácora (RN-14) en palabras, para el panel del admin. La base guarda el código.
ACCIONES_BITACORA = {
    "inicio_sesion": "Inicio de sesión",
    "cierre_sesion": "Cierre de sesión",
    "intento_fallido": "Intento fallido de entrar",
    "recuperacion_solicitada": "Pidió recuperar la contraseña",
    "contrasena_restablecida": "Contraseña restablecida",
    "contrasena_cambiada": "Cambió su contraseña",
    "contacto_actualizado": "Cambió su correo o celular",
    "usuario_activado": "Activó un usuario",
    "usuario_desactivado": "Desactivó un usuario",
    "bitacora_exportada": "Exportó la bitácora",
    "respaldo_creado": "Respaldo creado",
    "respaldo_descargado": "Respaldo descargado",
    "respaldo_restaurado": "Base restaurada desde un respaldo",
    "reporte_general_descargado": "Descargó el reporte general",
    "creacion": "Creación",
    "edicion": "Edición",
    "borrado": "Borrado",
    "cambio_estado": "Cambio de estado",
    "pago_reportado": "Pago reportado",
    "cobro_muelle": "Cobro en el muelle",
    "abordaje": "Abordaje",
    "asignacion": "Familia asignada",
    "reasignacion": "Familia reasignada",
    "sin_familia": "Reserva sin familia",
    "suspension_por_alerta": "Suspensión por alerta",
    "reprogramacion": "Reprogramación",
    "devolucion_solicitada": "Devolución pedida",
    "devolucion_atendida": "Devolución atendida",
    "mensaje_contacto": "Mensaje de contacto recibido",
}
SENALES = {"buena": "Buena señal", "debil": "Señal débil", "sin_senal": "Sin señal"}
SERVICIOS = {"desayuno": "Desayuno", "almuerzo": "Almuerzo", "cena": "Cena",
             "vestimenta": "Vestimenta típica", "taller_textil": "Taller textil"}


def _ingles():
    return textos.idioma() == "en"


def fecha_corta(valor):
    """lun 19 oct (en inglés: Mon Oct 19)"""
    if valor is None:
        return ""
    if _ingles():
        return f"{DAYS[valor.weekday()]} {MONTHS[valor.month - 1]} {valor.day}"
    return f"{DIAS[valor.weekday()]} {valor.day} {MESES[valor.month - 1]}"


def hora(valor):
    """14:00"""
    return valor.strftime("%H:%M") if valor is not None else ""


def fecha_larga(valor):
    """martes 20 de octubre (en inglés: Tuesday, October 20)"""
    if valor is None:
        return ""
    if _ingles():
        return f"{LONG_DAYS[valor.weekday()]}, {LONG_MONTHS[valor.month - 1]} {valor.day}"
    return f"{DIAS_LARGOS[valor.weekday()]} {valor.day} de {MESES_LARGOS[valor.month - 1]}"


def mes_y_anio(valor):
    """oct 2026 (en inglés: Oct 2026)"""
    if valor is None:
        return ""
    return f"{(MONTHS if _ingles() else MESES)[valor.month - 1]} {valor.year}"


def inicial_mayuscula(texto):
    """Como capitalize, pero sin pasar el resto a minúscula ("Tuesday, October 20")."""
    texto = str(texto or "")
    return texto[:1].upper() + texto[1:]


def duracion(horas):
    """3 h · 9 h 30 min · 2 días (las rutas con noche duran más de 24 h)"""
    if horas is None:
        return ""
    minutos = round(float(horas) * 60)
    if minutos >= 24 * 60:
        dias = -(-minutos // (24 * 60))
        return f"{dias} days" if _ingles() else f"{dias} días"
    h, m = divmod(minutos, 60)
    return f"{h} h" + (f" {m} min" if m else "")


def servicios(valor):
    """'desayuno,cena' → ['Desayuno', 'Cena'] (el SET de MariaDB llega como texto con comas)"""
    if not valor:
        return []
    return [t(SERVICIOS.get(s, s)) for s in str(valor).split(",") if s]


def fecha_hora(valor):
    """lun 19 oct, 14:00"""
    return f"{fecha_corta(valor)}, {hora(valor)}" if valor is not None else ""


def estado_reserva(valor):
    return t(ESTADOS_RESERVA.get(valor, valor))


def estado_visible(reserva):
    """El estado que se muestra de una reserva: si esperaba un pago y su plazo ya pasó, es
    «vencida» aunque la tarea automática (cada 5 minutos) todavía no la haya marcado (RN-05)."""
    if reserva.get("estado") == "pendiente_pago" and reserva.get("vigente") == 0:
        return "vencida"
    return reserva.get("estado")


def soles(valor):
    """S/ 1,250.00"""
    if valor is None:
        return ""
    return f"S/ {Decimal(valor):,.2f}"


def dolares(valor, cambio):
    """S/ 80.00 con el tipo de cambio de SUNAT (venta 3.461) → 'US$ 23' (aproximado)."""
    if valor is None or not cambio:
        return ""
    return f"US$ {(Decimal(valor) / cambio['venta']).quantize(Decimal('1'), ROUND_HALF_UP):,}"


def registrar(app):
    app.jinja_env.filters.update(
        fecha_corta=fecha_corta, fecha_larga=fecha_larga, hora=hora, fecha_hora=fecha_hora,
        mes_y_anio=mes_y_anio, inicial_mayuscula=inicial_mayuscula,
        soles=soles, dolares=dolares, duracion=duracion, servicios=servicios,
        # Las etiquetas pasan por t(): en el panel quedan en español; al turista, en su idioma.
        estado_publico=lambda v: t(ESTADOS_PUBLICOS.get(v, v)),
        nivel_alerta=lambda v: t(NIVELES_ALERTA.get(v, v)),
        tipo_alerta=lambda v: t(TIPOS_ALERTA.get(v, v)),
        idioma=lambda v: t(IDIOMAS.get(v, v)),
        accion_bitacora=lambda v: ACCIONES_BITACORA.get(v, v),
        senal=lambda v: t(SENALES.get(v, v)),
        estado_reserva=estado_reserva,
        metodo_pago=lambda v: t(METODOS_PAGO.get(v, v)),
        estado_pago=lambda v: t(ESTADOS_PAGO.get(v, v)),
        pais=paises.nombre,
        oculta_nombre=privacidad.nombre, oculta_documento=privacidad.documento,
        oculta_telefono=privacidad.telefono, oculta_correo=privacidad.correo,
    )

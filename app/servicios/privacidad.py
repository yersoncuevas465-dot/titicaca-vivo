"""Enmascarado de datos personales.

/reservas/<código> se puede abrir con solo el código. Hasta que la persona se
identifica (código + documento del titular, en /mi-reserva), nombres, documentos
y contactos se muestran a medias.
"""


def nombre(texto):
    """'Carmen Rosa' → 'C***** R***' (deja la primera letra de cada palabra)."""
    if not texto:
        return ""
    return " ".join(p[0] + "*" * (len(p) - 1) for p in str(texto).split())


def documento(texto):
    """'41020304' → '•••••304' (solo se ven los 3 últimos caracteres)."""
    if not texto:
        return ""
    texto = str(texto)
    return "•" * max(len(texto) - 3, 0) + texto[-3:]


def telefono(texto):
    """'900000201' → '9•••••201'."""
    if not texto:
        return ""
    texto = str(texto)
    if len(texto) <= 4:
        return "•" * len(texto)
    return texto[0] + "•" * (len(texto) - 4) + texto[-3:]


def correo(texto):
    """'camille.durand@correo.example' → 'c•••@correo.example'."""
    if not texto or "@" not in texto:
        return ""
    usuario, dominio = str(texto).split("@", 1)
    return f"{usuario[:1]}•••@{dominio}"

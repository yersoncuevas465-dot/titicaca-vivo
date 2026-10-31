"""Capa de modelos: aquí viven las reglas de negocio y TODO el SQL (escrito a mano).

Las rutas (blueprints) llaman a estas funciones; nunca escriben SQL.
Cada función que actúa en nombre de alguien recibe al `actor` y revisa su rol
otra vez (exigir_rol), además del decorador @requiere_rol de la ruta.
"""

ROLES_PERSONAL = ("admin", "operador", "guia", "capitan")
# v2.9 (D-119): el residente de una comunidad también entra al panel, pero solo para publicar
# sus productos. No es personal de la agencia: nunca ve salidas, pasajeros ni pagos.
ROLES_CON_CUENTA = (*ROLES_PERSONAL, "residente")
ROLES_CATALOGO = ("admin", "operador")        # S-26: catálogos los manejan el admin y el operador
ERROR_DUPLICADO = 1062                        # UNIQUE repetido
ERROR_TRIGGER = 1644                          # SIGNAL SQLSTATE '45000' de un trigger


class PermisoDenegado(Exception):
    """El actor no tiene el rol necesario. La app la convierte en un error 403."""


class ErrorNegocio(Exception):
    """Una regla de negocio no se cumple. El mensaje es para la persona usuaria.

    `campo` (opcional) dice junto a qué campo del formulario mostrarlo.
    """

    def __init__(self, mensaje, campo=None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.campo = campo


class ErrorValidacion(ErrorNegocio):
    """Datos inválidos. `errores` es {nombre_del_campo: mensaje}."""

    def __init__(self, errores):
        super().__init__("Revisa los datos marcados.")
        self.errores = errores


class EstadoNoPermite(ErrorNegocio):
    """El registro no está en un estado que permita esa acción."""


def mensaje_de_la_base(error):
    """Texto del error de MariaDB (por ejemplo, el MESSAGE_TEXT de un SIGNAL de trigger)."""
    return str(error.args[1]) if len(error.args) > 1 else str(error)


def exigir_rol(actor, *roles):
    if actor is None or not getattr(actor, "is_authenticated", False):
        raise PermisoDenegado("Hace falta iniciar sesión.")
    if actor.rol not in roles:
        raise PermisoDenegado(f"El rol {actor.rol} no puede hacer esto.")

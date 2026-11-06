"""Reglas del negocio que no necesitan la base de datos (observación de la Práctica 9).

Corren en cualquier PC, sin XAMPP ni MariaDB:

    python -m pytest tests/unitarias

Ninguna pide la fixture `app` ni `cliente`: así no se prepara la base de pruebas.
"""

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.modelos import ErrorValidacion, contacto, producto, reclamacion
from app.modelos import validacion as v

HOY = date(2026, 11, 6)
RUTAS = [{"codigo": "URO-MD", "nombre": "Islas flotantes de los Uros", "desde": 30}]
HOJA = {"tipo": "reclamo", "nombres": "Rosa", "apellidos": "Quispe", "tipo_documento": "DNI",
        "numero_documento": "79940001", "domicilio": "Jr. Lima 123, Puno",
        "correo": "Rosa@Ejemplo.test", "telefono": "", "apoderado": "", "codigo_reserva": "",
        "monto": "80,5", "servicio": "La salida en lancha del sábado",
        "detalle": "La lancha salió una hora tarde y nadie nos avisó.",
        "pedido": "Que me devuelvan la mitad del pasaje.", "acepto": True}


def grupo(**cambios):
    return {"tipo": "colegio", "institucion": "Colegio de prueba", "personas": "30",
            "fecha": "2026-12-01", "ruta": "URO-MD", "nombre": "Rosa Quispe",
            "correo": "rosa@ejemplo.test", "telefono": "", "comentarios": "", **cambios}


# --- Libro de reclamaciones ----------------------------------------------------------------------

@pytest.mark.parametrize("registrada, vence", [
    (datetime(2026, 11, 2, 10, 0), date(2026, 11, 23)),     # de lunes a lunes
    (datetime(2026, 11, 6, 18, 0), date(2026, 11, 27)),     # de viernes a viernes
    (datetime(2026, 10, 31, 17, 59), date(2026, 11, 20)),   # un sábado empieza a contar el lunes
])
def test_el_plazo_para_responder_son_15_dias_habiles(registrada, vence):
    assert reclamacion.vence_el(registrada) == vence


def test_una_hoja_bien_llenada_queda_limpia():
    limpia = reclamacion.validar(dict(HOJA))
    assert limpia["correo"] == "rosa@ejemplo.test" and limpia["monto"] == "80.50"


def test_una_hoja_mal_llenada_dice_cada_error():
    with pytest.raises(ErrorValidacion) as error:
        reclamacion.validar({**HOJA, "nombres": "R2-D2", "monto": "mucho", "acepto": False})
    assert set(error.value.errores) == {"nombres", "monto", "acepto"}


# --- Viajes en grupo -----------------------------------------------------------------------------

def test_el_pedido_de_un_grupo_y_su_precio_referencial():
    ruta = contacto.validar_grupo(grupo(), RUTAS, HOY)
    assert ruta["codigo"] == "URO-MD" and contacto.estimar(ruta, 30) == 900


@pytest.mark.parametrize("cambios, campo", [
    ({"personas": "1"}, "personas"),
    ({"personas": "muchos"}, "personas"),
    ({"fecha": "2020-01-01"}, "fecha"),
    ({"ruta": "NO-EXISTE"}, "ruta"),
    ({"tipo": "piratas"}, "tipo"),
])
def test_un_pedido_mal_llenado_marca_su_campo(cambios, campo):
    with pytest.raises(ErrorValidacion) as error:
        contacto.validar_grupo(grupo(**cambios), RUTAS, HOY)
    assert campo in error.value.errores


# --- Productos: quién edita, quién retira y quién oculta -----------------------------------------

JUANA = SimpleNamespace(id=7, rol="residente")
OPERADOR = SimpleNamespace(id=2, rol="operador")
ADMIN = SimpleNamespace(id=1, rol="admin")
DE_JUANA = {"residente_id": 7, "estado": "publicado"}
DE_LA_AGENCIA = {"residente_id": None, "estado": "publicado"}


def test_cada_uno_edita_solo_lo_suyo():
    assert producto.puede_editar(JUANA, DE_JUANA)
    assert not producto.puede_editar(JUANA, DE_LA_AGENCIA)
    assert producto.puede_editar(OPERADOR, DE_LA_AGENCIA)
    assert not producto.puede_editar(OPERADOR, DE_JUANA)
    assert not producto.puede_editar(ADMIN, DE_LA_AGENCIA)              # el admin solo mira


def test_retirar_ocultar_y_volver_a_mostrar():
    oculto = {**DE_JUANA, "estado": "oculto"}
    assert producto.cambios_permitidos(JUANA, DE_JUANA) == ("retirado",)
    assert producto.cambios_permitidos(OPERADOR, DE_JUANA) == ("oculto",)
    assert producto.cambios_permitidos(JUANA, oculto) == ()           # solo la agencia lo muestra
    assert producto.cambios_permitidos(OPERADOR, oculto) == ("publicado",)
    assert producto.cambios_permitidos(ADMIN, DE_JUANA) == ()


# --- Ayudantes de validación ---------------------------------------------------------------------

def test_los_ayudantes_de_validacion():
    errores = {}
    assert v.decimal({"precio": "12.5"}, "precio", errores, "0.50", 10000) == Decimal("12.50")
    assert v.decimal({"precio": "gratis"}, "precio", errores, "0.50", 10000) is None
    assert errores == {"precio": "Escribe un número (usa punto para los decimales)."}
    assert v.texto({"nombre": "  Rosa   Quispe "}, "nombre", {}, 2, 80) == "Rosa Quispe"
    assert v.slug_de("Luquina Chico") == "luquina-chico" and v.slug_de("Amantaní") == "amantani"

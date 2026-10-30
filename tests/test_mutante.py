"""Prueba mutante (sección 14): si se quita el FOR UPDATE, la prueba de concurrencia FALLA.

Un "mutante" es una copia del código con un cambio a propósito. Si las pruebas no detectan
el cambio, no estaban probando nada. Aquí el mutante es app/modelos/reserva.py SIN
`FOR UPDATE` ni `LOCK IN SHARE MODE`, y se corre la misma carrera de la prueba de concurrencia:
8 hilos, cada uno con su conexión, piden el ÚLTIMO lugar.

La reserva tiene DOS defensas (D-19, D-50): el FOR UPDATE del modelo y el trigger
trg_reserva_pasajero_bi. Para ver qué hace cada una, el trigger se quita solo durante la prueba
y se vuelve a crear al final. Las tres corridas usan la misma pausa entre "contar los ocupados"
y "guardar" (como una red lenta), para que la carrera no dependa de la suerte:

| Modelo                    | Trigger | Resultado esperado                         |
|---------------------------|---------|--------------------------------------------|
| original (con FOR UPDATE) | sin     | 1 reserva: el FOR UPDATE solo ya protege   |
| mutante (sin FOR UPDATE)  | sin     | VARIAS reservas: sobreventa (falla RN-02)  |
| mutante (sin FOR UPDATE)  | con     | 1 reserva: el trigger es la red de respaldo |
"""

import time
import types
from pathlib import Path

import pytest

from app import bd
from tests.conftest import consultar_valor
from tests.test_concurrencia import _en_paralelo

FUENTE = Path(__file__).resolve().parent.parent / "app" / "modelos" / "reserva.py"
LINEA_CONTEO = '    libres = max(salida["cupo"] - cur.fetchone()["ocupados"], 0)\n'
PAUSA = 0.3          # segundos entre contar y guardar: la "ventana" de la carrera
HILOS = 8


def construir_modelo(quitar_bloqueos):
    """El modelo de reservas con una pausa después de contar; con quitar_bloqueos=True, el mutante."""
    codigo = FUENTE.read_text(encoding="utf-8")
    assert codigo.count(LINEA_CONTEO) == 1, "Cambió el modelo: hay que actualizar la prueba mutante"
    codigo = "import time\n" + codigo.replace(LINEA_CONTEO, LINEA_CONTEO + f"    time.sleep({PAUSA})\n")
    if quitar_bloqueos:
        assert codigo.count("FOR UPDATE") >= 2 and "LOCK IN SHARE MODE" in codigo
        codigo = codigo.replace("FOR UPDATE", "").replace("LOCK IN SHARE MODE", "")
    modulo = types.ModuleType("reserva_mutante" if quitar_bloqueos else "reserva_con_pausa")
    exec(compile(codigo, modulo.__name__ + ".py", "exec"), modulo.__dict__)  # noqa: S102 (código propio)
    return modulo


@pytest.fixture
def sin_trigger(app):
    """Quita el trigger de sobreventa y lo vuelve a crear desde 02_vistas_triggers.sql."""
    script = (app.config["CARPETA_SQL"] / "02_vistas_triggers.sql").read_text(encoding="utf-8")
    crear = next(s for s in bd.dividir_sentencias(script)
                 if s.startswith("CREATE TRIGGER trg_reserva_pasajero_bi"))
    conexion = bd.conectar(app.config)
    try:
        with conexion.cursor() as cursor:
            cursor.execute("DROP TRIGGER IF EXISTS trg_reserva_pasajero_bi")
        conexion.commit()
        yield
    finally:
        with conexion.cursor() as cursor:
            cursor.execute("DROP TRIGGER IF EXISTS trg_reserva_pasajero_bi")
            cursor.execute(crear)
        conexion.commit()
        conexion.close()


def carrera(app, salida_id, modelo):
    """Los 8 hilos piden el último lugar con `modelo`. Devuelve (reservas creadas, ocupados)."""
    def tarea(indice):
        titular = modelo.Persona("Hilo", "Mutante", "DNI", f"7996{indice:04d}", "PE", 1)
        solicitud = modelo.Solicitud(salida_id=salida_id, titular=titular, telefono="987654321",
                                     correo=None, titular_viaja=True, metodo_pago="muelle")
        return modelo.crear(solicitud, modelo.generar_token())

    inicio = time.monotonic()
    resultados = _en_paralelo(app, HILOS, tarea)
    creadas = sum(1 for r in resultados if r[0] == "ok")
    ocupados = consultar_valor(app, "SELECT ocupados FROM v_disponibilidad_salida WHERE salida_id = %s",
                               (salida_id,))
    print(f"\n  {modelo.__name__}: {creadas} reserva(s) creadas, {ocupados} ocupado(s) de 1 lugar, "
          f"{time.monotonic() - inicio:.1f} s · {[r[0] for r in resultados]}")
    return creadas, ocupados


def test_con_for_update_y_sin_trigger_no_hay_sobreventa(app, salida_prueba, sin_trigger):
    salida_id = salida_prueba(cupo=1)
    assert carrera(app, salida_id, construir_modelo(quitar_bloqueos=False)) == (1, 1)


def test_el_mutante_sin_for_update_vende_de_mas(app, salida_prueba, sin_trigger):
    """Esta es la demostración: sin FOR UPDATE, la prueba de los 8 hilos fallaría."""
    salida_id = salida_prueba(cupo=1)
    creadas, ocupados = carrera(app, salida_id, construir_modelo(quitar_bloqueos=True))
    assert creadas > 1 and ocupados > 1          # SOBREVENTA: más pasajeros que el cupo (1)


def test_el_trigger_frena_al_mutante(app, salida_prueba):
    """Segunda defensa: con el trigger puesto, el mutante igual no vende de más."""
    salida_id = salida_prueba(cupo=1)
    assert carrera(app, salida_id, construir_modelo(quitar_bloqueos=True)) == (1, 1)


def test_el_trigger_quedo_restaurado(app):
    assert consultar_valor(app, "SELECT COUNT(*) FROM information_schema.TRIGGERS "
                                "WHERE TRIGGER_SCHEMA = DATABASE() "
                                "AND TRIGGER_NAME = 'trg_reserva_pasajero_bi'") == 1

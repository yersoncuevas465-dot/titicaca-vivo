"""Comandos de consola: `flask bd reiniciar`, `flask bd contar`, `flask bd respaldar`,
`flask bd restaurar <archivo>`, `flask reservas vencer`, `flask usuarios listar`,
`flask usuarios clave <usuario>` y `flask correo probar <correo>`."""

import time
from contextlib import contextmanager
from pathlib import Path

import click
import pymysql
from flask import current_app
from flask.cli import AppGroup

from app import bd, diagnostico

grupo_bd = AppGroup("bd", help="Base de datos de Titicaca Vivo.")
grupo_reservas = AppGroup("reservas", help="Tareas de las reservas.")
grupo_usuarios = AppGroup("usuarios", help="Cuentas del personal.")
grupo_correo = AppGroup("correo", help="Envío de correos.")


@contextmanager
def _base_disponible():
    """Si MySQL falla, el comando termina con la causa y el arreglo, no con una traza."""
    try:
        yield
    except pymysql.err.MySQLError as error:
        raise click.ClickException(diagnostico.explicar(error, current_app.config)) from error


@grupo_bd.command("reiniciar")
@click.option("--si", is_flag=True, help="No pedir confirmación (para scripts).")
@click.option("--sin-respaldo", is_flag=True, help="No guardar antes un respaldo de la base.")
def reiniciar(si, sin_respaldo):
    """Borra la base, la crea de nuevo y ejecuta 01_esquema, 02_vistas_triggers y 03_datos.

    Antes guarda un respaldo de lo que había (D-117): un reinicio por error se puede deshacer
    con `flask bd restaurar`."""
    config = current_app.config
    if config["ENTORNO"] == "produccion":
        raise click.ClickException("En producción no se reinicia la base.")
    nombre = config["BD_NOMBRE"]
    destino = f"'{nombre}' en {config['BD_HOST']}:{config['BD_PUERTO']}"
    if not si:
        click.confirm(f"Se BORRARÁ la base {destino}. ¿Continuar?", abort=True)

    inicio = time.perf_counter()
    with _base_disponible():
        if not sin_respaldo:
            _respaldo_previo("antes-de-reiniciar")
        resultado = bd.reiniciar_base(config)
    for archivo, sentencias in resultado.items():
        click.echo(f"  {archivo:<24} {sentencias:>3} sentencias")
    click.echo(f"Base {destino} lista en {time.perf_counter() - inicio:.1f} s.")
    _mostrar_conteo()


def _respaldo_previo(tipo):
    """Guarda un respaldo antes de borrar. Si la base todavía no existe o está rota, avisa y sigue
    (reiniciar es justamente el arreglo); si MySQL no responde, deja que se explique el error."""
    from app.modelos import ErrorNegocio, respaldo

    try:
        hecho = respaldo.crear(tipo, ip="consola")
    except pymysql.err.MySQLError as error:
        if diagnostico.sin_servidor(error):
            raise
        causa = diagnostico.explicar(error, current_app.config).splitlines()[0]
        click.echo(f"  (no se guardó un respaldo previo: {causa})")
    except ErrorNegocio as error:
        click.echo(f"  (no se guardó un respaldo previo: {error.mensaje})")
    else:
        click.echo(f"  Respaldo previo: respaldos\\{hecho['nombre']} ({hecho['kb']} KB)")


@grupo_bd.command("respaldar")
def respaldar():
    """D-116: guarda ahora un respaldo completo de la base en la carpeta respaldos/."""
    from app.modelos import ErrorNegocio, respaldo

    with _base_disponible():
        try:
            hecho = respaldo.crear("consola", ip="consola")
        except ErrorNegocio as error:
            raise click.ClickException(error.mensaje) from error
    click.echo(f"Listo: {respaldo.carpeta() / hecho['nombre']}")
    click.echo(f"  {hecho['tablas']} tablas, {hecho['filas']} filas, {hecho['kb']} KB.")


@grupo_bd.command("restaurar")
@click.argument("archivo", type=click.Path(dir_okay=False, path_type=Path))
@click.option("--si", is_flag=True, help="No pedir confirmación (para scripts).")
@click.option("--sin-respaldo", is_flag=True,
              help="No guardar antes un respaldo (si la base está tan dañada que no se puede).")
def restaurar(archivo, si, sin_respaldo):
    """D-116: deja la base como en el respaldo ARCHIVO. Antes guarda un respaldo de lo que hay."""
    from app.modelos import ErrorNegocio, respaldo

    config = current_app.config
    if not archivo.is_file() and (respaldo.carpeta() / archivo.name).is_file():
        archivo = respaldo.carpeta() / archivo.name          # basta con el nombre del archivo
    destino = f"'{config['BD_NOMBRE']}' en {config['BD_HOST']}:{config['BD_PUERTO']}"
    if not si:
        click.confirm(f"Se BORRARÁ lo que hay en la base {destino} y quedará lo de "
                      f"{archivo.name}. ¿Continuar?", abort=True)
    inicio = time.perf_counter()
    with _base_disponible():
        try:
            sentencias, previo = respaldo.restaurar(archivo, ip="consola",
                                                    respaldo_previo=not sin_respaldo)
        except ErrorNegocio as error:
            raise click.ClickException(error.mensaje) from error
    if previo:
        click.echo(f"  Antes se guardó: respaldos\\{previo['nombre']}")
    click.echo(f"Base {destino} restaurada desde {archivo.name}: {sentencias} sentencias en "
               f"{time.perf_counter() - inicio:.1f} s.")
    _mostrar_conteo()


@grupo_bd.command("contar")
def contar():
    """Muestra cuántas filas tiene cada una de las 20 tablas."""
    _mostrar_conteo()


def _mostrar_conteo():
    with _base_disponible():
        conexion = bd.conectar(current_app.config)
        try:
            filas = bd.contar_filas(conexion)
        finally:
            conexion.close()
    for tabla, cantidad in filas:
        click.echo(f"  {tabla:<20} {cantidad:>4}")
    click.echo(f"  {len(filas)} tablas, {sum(c for _, c in filas)} filas en total.")


@grupo_reservas.command("vencer")
def vencer():
    """RN-05: marca 'vencida' cada reserva pendiente de pago cuyo plazo ya pasó."""
    from app.modelos import reserva

    with _base_disponible():
        codigos = reserva.vencer_pendientes()
    if codigos:
        click.echo(f"{len(codigos)} reservas vencidas: {', '.join(codigos)}")
    else:
        click.echo("No había reservas por vencer.")


@grupo_usuarios.command("listar")
def usuarios_listar():
    """Muestra el personal: usuario, rol, si está activo y si tiene correo para recuperar."""
    from app.modelos import usuario

    with _base_disponible():
        filas = usuario.para_consola()
    for f in filas:
        estado = "activo" if f["activo"] else "INACTIVO"
        correo = f["correo"] or "(sin correo: no puede recuperar su contraseña)"
        click.echo(f"  {f['nombre_usuario']:<18} {f['rol']:<9} {estado:<9} {correo}")


@grupo_usuarios.command("clave")
@click.argument("nombre_usuario")
@click.password_option("--contrasena", prompt="Contraseña nueva",
                       confirmation_prompt="Repite la contraseña nueva",
                       help="Si no se escribe aquí, se pide sin mostrarla.")
def usuarios_clave(nombre_usuario, contrasena):
    """D-111: pone una contraseña nueva desde la terminal del servidor (el admin la olvidó).

    Queda en la bitácora con la IP «consola». Las sesiones abiertas de esa cuenta se cierran.
    """
    from app.modelos import ErrorNegocio, usuario

    with _base_disponible():
        try:
            activo = usuario.cambiar_clave_desde_consola(nombre_usuario, contrasena)
        except ErrorNegocio as error:
            raise click.ClickException(error.mensaje) from error
    click.echo(f"Listo: la contraseña de «{nombre_usuario}» cambió.")
    if not activo:
        click.echo("Aviso: esa cuenta está DESACTIVADA. Actívala en Usuarios para que "
                   "pueda entrar.")


@grupo_correo.command("probar")
@click.argument("destino")
def correo_probar(destino):
    """Manda un correo de prueba para revisar la configuración SMTP del .env."""
    from app.servicios import correo

    resultado = correo.enviar(destino, "Titicaca Vivo · correo de prueba",
                              "Si lees esto, el envío de correos de Titicaca Vivo funciona.")
    mensajes = {
        correo.SIMULADO: "Modo simulación (CORREO_SIMULAR=1): el correo se mostró arriba y no "
                         "salió a internet. Para enviarlo de verdad, pon CORREO_SIMULAR=0 y los "
                         "datos SMTP en el .env.",
        correo.ENVIADO: f"Correo enviado a {destino}. Revisa la bandeja (y la carpeta de spam).",
    }
    if resultado == correo.FALLO:
        raise click.ClickException("No se pudo enviar. Revisa SMTP_HOST, SMTP_PUERTO, "
                                   "SMTP_USUARIO y SMTP_CONTRASENA en el .env (el detalle está "
                                   "en logs/app.log).")
    click.echo(mensajes[resultado])


def registrar(app):
    app.cli.add_command(grupo_bd)
    app.cli.add_command(grupo_reservas)
    app.cli.add_command(grupo_usuarios)
    app.cli.add_command(grupo_correo)

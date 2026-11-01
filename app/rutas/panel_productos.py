"""Productos en el panel (v2.9): el residente publica y edita los suyos; el operador, los de la
agencia, y oculta el de un residente que no corresponda; el admin solo mira.

Las rutas se registran en el blueprint `panel` (url /panel/productos). Ningún SQL aquí.
"""

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from werkzeug.datastructures import FileStorage

from app.formularios import datos_de
from app.formularios.producto import FormularioProducto
from app.modelos import ErrorNegocio, ErrorValidacion, comunidad
from app.modelos import producto as modelo_producto
from app.rutas.panel import bp, procesar
from app.seguridad import ip_cliente, requiere_rol
from app.servicios import fotos

AVISOS = {"retirado": "Listo: «{nombre}» ya no se muestra en la página de productos.",
          "publicado": "Listo: «{nombre}» se muestra otra vez en la página de productos.",
          "oculto": "Listo: «{nombre}» quedó oculto. Solo la agencia lo vuelve a mostrar."}


def _pagina(sueltos=(), codigo=200):
    return render_template("panel/productos.html",
                           productos=modelo_producto.listar_panel(current_user),
                           categorias=modelo_producto.CATEGORIAS, estados=modelo_producto.ESTADOS,
                           sueltos=sueltos), codigo


def _guardar(producto_id, formulario, actual):
    """Primero la foto nueva (si vino), después el producto. Si el producto no se guarda, la foto
    nueva se borra; si se guarda, se borra la foto subida que tenía antes."""
    archivo, nueva = formulario.foto.data, None
    if isinstance(archivo, FileStorage) and archivo.filename:
        try:
            nueva = fotos.guardar(archivo)
        except ValueError as error:
            raise ErrorValidacion({"foto": str(error)}) from error
    try:
        guardado = modelo_producto.guardar(current_user, producto_id, datos_de(formulario),
                                           ip_cliente(), foto=nueva)
    except Exception:
        fotos.borrar(nueva)
        raise
    if nueva and actual:
        fotos.borrar(actual["foto"])
    return guardado


@bp.route("/productos")
@requiere_rol("admin", "operador", "residente")
def productos():
    return _pagina()


@bp.route("/productos/nuevo", methods=["GET", "POST"])
@bp.route("/productos/<int:producto_id>/editar", methods=["GET", "POST"])
@requiere_rol("operador", "residente")
def producto_formulario(producto_id=None):
    actual = None
    if producto_id is not None:
        actual = modelo_producto.buscar_para_editar(current_user, producto_id)
        if actual is None:
            abort(404)                          # no existe o no es suyo: no se dice cuál
    # La foto actual no va al campo del archivo: ese campo solo trae una foto nueva
    formulario = FormularioProducto(data={**actual, "comunidad_id": actual["comunidad_id"] or 0,
                                          "foto": None} if actual else None)
    comunidades = comunidad.opciones()
    if current_user.rol == "residente":
        del formulario.comunidad_id             # publica en su comunidad, la de su cuenta
        donde = next((c["nombre"] for c in comunidades if c["id"] == current_user.comunidad_id),
                     None)
    else:
        formulario.comunidad_id.choices = [(0, "En Puno, con la agencia")] + [
            (c["id"], c["nombre"]) for c in comunidades]
        donde = None
    respuesta, sueltos, codigo = procesar(
        formulario,
        lambda: _guardar(producto_id, formulario, actual),
        "Listo: los cambios quedaron guardados." if actual else
        "Listo: el producto quedó publicado y ya se ve en la página de productos.",
        url_for("panel.productos"))
    return respuesta or (render_template("panel/producto_formulario.html", f=formulario, p=actual,
                                         sueltos=sueltos, donde=donde), codigo)


@bp.route("/productos/<int:producto_id>/estado", methods=["POST"])
@requiere_rol("operador", "residente")
def producto_estado(producto_id):
    nuevo = request.form.get("estado")
    try:
        nombre = modelo_producto.cambiar_estado(current_user, producto_id, nuevo, ip_cliente())
    except ErrorNegocio as error:
        return _pagina([error.mensaje], 422)
    flash(AVISOS[nuevo].format(nombre=nombre), "exito")
    return redirect(url_for("panel.productos"), code=303)

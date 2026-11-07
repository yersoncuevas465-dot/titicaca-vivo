"""Catálogos del panel (F5): rutas y paradas, lanchas, tarifas, temporadas, tipos de pasajero,
comunidades y familias. Los manejan el admin y el operador (S-26, matriz de permisos).

Las 7 listas y los 7 formularios se parecen, así que comparten dos plantillas; lo que cambia
(qué formulario, qué columnas, qué funciones del modelo) se describe en CATALOGOS. Cada
catálogo tiene su propio SQL en su modelo: aquí no hay SQL.
"""

from dataclasses import dataclass, field

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from flask_login import current_user

from app.formularios import datos_de
from app.formularios.catalogos import (
    FormularioComunidad,
    FormularioEmbarcacion,
    FormularioFamilia,
    FormularioParada,
    FormularioRuta,
    FormularioTarifa,
    FormularioTemporada,
    FormularioTipoPasajero,
)
from app.formularios.panel import FormularioAccion
from app.modelos import (
    ROLES_CATALOGO,
    ErrorNegocio,
    comunidad,
    embarcacion,
    familia,
    ruta,
    tarifa,
    temporada,
    tipo_pasajero,
)
from app.rutas.panel import SIN_ELEGIR, procesar
from app.seguridad import ip_cliente, requiere_rol
from app.servicios import formato

bp = Blueprint("catalogos", __name__, url_prefix="/panel/catalogos")


@bp.before_request
def sin_cache():
    # Las familias y el personal tienen datos personales: nada va a la caché del navegador.
    g.sin_cache = True


def _si_no(valor):
    return "Sí" if valor else "No"


def _activo(valor):
    return "Activa" if valor else "Inactiva"


def _opciones_tarifa(formulario):
    op = tarifa.opciones()
    formulario.ruta_id.choices = [SIN_ELEGIR] + [(r["id"], r["nombre"]) for r in op["rutas"]]
    formulario.tipo_pasajero_id.choices = [SIN_ELEGIR] + [(t["id"], t["nombre"])
                                                          for t in op["tipos"]]


def _opciones_familia(formulario):
    formulario.comunidad_id.choices = [SIN_ELEGIR] + [
        (c["id"], c["nombre"]) for c in comunidad.opciones() if c["tiene_hospedaje"]]


@dataclass
class Catalogo:
    titulo: str                   # "Lanchas"
    con_articulo: str             # "la lancha" (para los mensajes)
    descripcion: str
    formulario: type
    listar: object                # (actor) -> filas
    buscar: object                # (actor, id) -> fila o None
    guardar: object               # (actor, id, datos, ip) -> id
    columnas: list = field(default_factory=list)   # [(encabezado, fila -> texto)]
    opciones: object = None       # (formulario) -> carga las listas desplegables
    permite_nuevo: bool = True
    enlace_extra: tuple = None    # (texto, endpoint) por fila, por ejemplo las paradas


CATALOGOS = {
    "rutas": Catalogo(
        "Rutas", "la ruta", "Recorridos que vende la agencia, su duración y si incluyen noche.",
        FormularioRuta, ruta.listar_panel, ruta.buscar_panel, ruta.guardar,
        columnas=[("Código", lambda f: f["codigo"]), ("Nombre", lambda f: f["nombre"]),
                  ("Duración", lambda f: formato.duracion(f["duracion_horas"])),
                  ("Paradas", lambda f: f["paradas"]),
                  ("Noche en", lambda f: f["pernocte_en"] or (
                      "¡Falta marcarla!" if f["incluye_pernocte"] else "—")),
                  ("Salidas por venir", lambda f: f["salidas_por_venir"]),
                  ("Estado", lambda f: _activo(f["activa"]))],
        enlace_extra=("Paradas", "catalogos.paradas")),
    "embarcaciones": Catalogo(
        "Lanchas", "la lancha", "Solo una lancha operativa puede salir, y el cupo de una "
        "salida no pasa su capacidad.",
        FormularioEmbarcacion, embarcacion.listar_panel, embarcacion.buscar_panel,
        embarcacion.guardar,
        columnas=[("Nombre", lambda f: f["nombre"]), ("Matrícula", lambda f: f["matricula"]),
                  ("Capacidad", lambda f: f["capacidad_maxima"]),
                  ("Tipo", lambda f: f["tipo"].replace("_", " ")),
                  ("Estado", lambda f: f["estado"]),
                  ("Último mantenimiento", lambda f: formato.fecha_corta(f["ultimo_mantenimiento"])
                   or "—"),
                  ("Salidas por venir", lambda f: f["salidas_por_venir"])]),
    "tarifas": Catalogo(
        "Tarifas", "la tarifa", "Gana la tarifa vigente más reciente para la fecha de la "
        "salida. Cambiar una tarifa no cambia las reservas ya hechas (el precio es una foto).",
        FormularioTarifa, tarifa.listar_panel, tarifa.buscar_panel, tarifa.guardar,
        columnas=[("Ruta", lambda f: f["ruta"]), ("Tipo", lambda f: f["tipo"]),
                  ("Precio base", lambda f: formato.soles(f["precio_base"])),
                  ("Desde", lambda f: formato.fecha_corta(f["vigente_desde"])),
                  ("Hasta", lambda f: formato.fecha_corta(f["vigente_hasta"]) or "Sin fin"),
                  ("Vigente hoy", lambda f: _si_no(f["vigente_hoy"]))],
        opciones=_opciones_tarifa),
    "temporadas": Catalogo(
        "Temporadas", "la temporada", "Recargo por fechas. No se pueden solapar.",
        FormularioTemporada, temporada.listar, temporada.buscar, temporada.guardar,
        columnas=[("Nombre", lambda f: f["nombre"]),
                  ("Desde", lambda f: formato.fecha_corta(f["fecha_inicio"])),
                  ("Hasta", lambda f: formato.fecha_corta(f["fecha_fin"])),
                  ("Recargo", lambda f: formato.porcentaje(f["recargo_porcentaje"])),
                  ("En curso", lambda f: _si_no(f["en_curso"]))]),
    "tipos-pasajero": Catalogo(
        "Tipos de pasajero", "el tipo de pasajero", "Los 5 tipos los fija el enunciado: solo se "
        "editan su nombre y sus edades (informativas: se revisan con el documento).",
        FormularioTipoPasajero, tipo_pasajero.listar, tipo_pasajero.buscar,
        tipo_pasajero.guardar, permite_nuevo=False,
        columnas=[("Código", lambda f: f["codigo"]), ("Nombre", lambda f: f["nombre"]),
                  ("Edades", lambda f: f"{f['edad_minima']} a {f['edad_maxima']}"
                   if f["edad_maxima"] is not None else f"{f['edad_minima']} o más"),
                  ("Tarifas", lambda f: f["tarifas"])]),
    "comunidades": Catalogo(
        "Comunidades", "la comunidad", "Lugares que visitan las rutas. La ficha pública sale "
        "de aquí (la foto es img/comunidades/<slug>.webp).",
        FormularioComunidad, comunidad.listar_panel, comunidad.buscar_panel, comunidad.guardar,
        columnas=[("Nombre", lambda f: f["nombre"]), ("Distrito", lambda f: f["distrito"]),
                  ("Idioma", lambda f: formato.IDIOMAS.get(f["idioma_originario"])),
                  ("Señal", lambda f: formato.SENALES.get(f["senal"])),
                  ("Hospedaje", lambda f: _si_no(f["tiene_hospedaje"])),
                  ("Familias activas", lambda f: f["familias"]), ("Rutas", lambda f: f["rutas"]),
                  ("Estado", lambda f: _activo(f["activa"]))]),
    "familias": Catalogo(
        "Familias anfitrionas", "la familia", "Reciben turistas por rotación justa. "
        "El responsable y el teléfono solo se ven en el panel.",
        FormularioFamilia, familia.listar_panel, familia.buscar_panel, familia.guardar,
        columnas=[("Familia", lambda f: f["nombre_familia"]),
                  ("Comunidad", lambda f: f["comunidad"]),
                  ("Responsable", lambda f: f["responsable"]),
                  ("Teléfono", lambda f: f["telefono"] or "—"),
                  ("Capacidad", lambda f: f["capacidad_personas"]),
                  ("Servicios", lambda f: ", ".join(formato.servicios(f["servicios"])) or "—"),
                  ("Noches por venir", lambda f: f["noches_por_venir"]),
                  ("Estado", lambda f: _activo(f["activa"]))],
        opciones=_opciones_familia),
}


def _catalogo_o_404(nombre):
    catalogo = CATALOGOS.get(nombre)
    if catalogo is None:
        abort(404)
    return catalogo


@bp.route("")
@requiere_rol(*ROLES_CATALOGO)
def inicio():
    return render_template("panel/catalogos/inicio.html", catalogos=CATALOGOS)


@bp.route("/<nombre>")
@requiere_rol(*ROLES_CATALOGO)
def lista(nombre):
    catalogo = _catalogo_o_404(nombre)
    return render_template("panel/catalogos/lista.html", cat=catalogo, nombre=nombre,
                           filas=catalogo.listar(current_user))


@bp.route("/<nombre>/nuevo", methods=["GET", "POST"])
@bp.route("/<nombre>/<int:registro_id>", methods=["GET", "POST"])
@requiere_rol(*ROLES_CATALOGO)
def formulario(nombre, registro_id=None):
    catalogo = _catalogo_o_404(nombre)
    actual = None
    if registro_id is None and not catalogo.permite_nuevo:
        abort(404)
    if registro_id is not None:
        actual = catalogo.buscar(current_user, registro_id)
        if actual is None:
            abort(404)
    forma = catalogo.formulario(data=actual)
    if catalogo.opciones:
        catalogo.opciones(forma)
    respuesta, sueltos, codigo = procesar(
        forma,
        lambda: catalogo.guardar(current_user, registro_id, datos_de(forma), ip_cliente()),
        f"Listo: se guardó {catalogo.con_articulo}.",
        url_for("catalogos.lista", nombre=nombre))
    if actual:
        titulo = f"Editar {catalogo.con_articulo}"
        if "codigo" in actual and nombre == "tipos-pasajero":
            titulo += f" «{actual['codigo']}»"
    else:
        titulo = "Nueva " + catalogo.con_articulo.removeprefix("la ")   # todas son "la ..."
    return respuesta or (render_template(
        "panel/catalogos/formulario.html", f=forma, titulo=titulo, sueltos=sueltos,
        ayuda=catalogo.descripcion, volver=url_for("catalogos.lista", nombre=nombre),
        volver_texto=catalogo.titulo), codigo)


# --- Paradas de una ruta -------------------------------------------------------------------------

@bp.route("/rutas/<int:ruta_id>/paradas", methods=["GET", "POST"])
@bp.route("/rutas/<int:ruta_id>/paradas/<int:parada_id>", methods=["GET", "POST"])
@requiere_rol(*ROLES_CATALOGO)
def paradas(ruta_id, parada_id=None):
    la_ruta = ruta.buscar_panel(current_user, ruta_id)
    if la_ruta is None:
        abort(404)
    actual = None
    if parada_id is not None:
        actual = ruta.buscar_parada(current_user, ruta_id, parada_id)
        if actual is None:
            abort(404)
    lista_paradas = ruta.paradas_panel(current_user, ruta_id)
    forma = FormularioParada(data=actual)
    forma.comunidad_id.choices = [SIN_ELEGIR] + [(c["id"], c["nombre"])
                                                 for c in comunidad.opciones()]
    if request.method == "GET" and actual is None:
        forma.orden.data = max((p["orden"] for p in lista_paradas), default=0) + 1
        forma.minutos_estadia.data = 60
    respuesta, sueltos, codigo = procesar(
        forma,
        lambda: ruta.guardar_parada(current_user, ruta_id, parada_id, datos_de(forma),
                                    ip_cliente()),
        "Listo: se guardó la parada.", url_for("catalogos.paradas", ruta_id=ruta_id))
    return respuesta or (render_template(
        "panel/catalogos/paradas.html", r=la_ruta, paradas=lista_paradas, f=forma,
        actual=actual, sueltos=sueltos, borrar=FormularioAccion()), codigo)


@bp.route("/rutas/<int:ruta_id>/paradas/<int:parada_id>/borrar", methods=["POST"])
@requiere_rol(*ROLES_CATALOGO)
def parada_borrar(ruta_id, parada_id):
    try:
        ruta.borrar_parada(current_user, ruta_id, parada_id, ip_cliente())
    except ErrorNegocio as error:
        flash(error.mensaje, "error")
    else:
        flash("Listo: se quitó la parada.", "exito")
    return redirect(url_for("catalogos.paradas", ruta_id=ruta_id), code=303)

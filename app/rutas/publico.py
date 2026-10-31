"""Páginas públicas (sin cuenta): portada, salidas, comunidades, alertas y /salud.

Nivel Plata: cada página lee sus datos de la base a través de los modelos.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pymysql
from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app.modelos import alerta, comunidad, resena, ruta, salida, sistema, tarifa
from app.seguridad import destino_seguro
from app.servicios import clima, feriados, imagenes, mapa, tipo_cambio

bp = Blueprint("publico", __name__)


def hoy_en_lima():
    return datetime.now(ZoneInfo(current_app.config["ZONA_HORARIA"])).date()


def _datos_del_mapa(comunidades=None, **resalte):
    """Datos del mapa; `resalte`: ruta_id, resaltadas o todo_el_lago (servicios/mapa.py)."""
    comunidades = comunidades if comunidades is not None else comunidad.listar_publicas()
    return mapa.construir(comunidades, ruta.paradas_para_mapa(), **resalte)


def _rutas_con_paradas(rutas, paradas, comunidades):
    """v2.4: cada ruta con sus comunidades en el orden de visita y la de su foto (la última
    parada que tenga foto). Sin consultas extra: usa las paradas que ya trae el mapa."""
    por_slug = {c["slug"]: c for c in comunidades}
    tarjetas = []
    for r in rutas:
        suyas = [por_slug[p["slug"]] for p in paradas
                 if p["ruta_id"] == r["id"] and p["slug"] in por_slug]
        con_foto = [c for c in suyas if imagenes.foto_comunidad(c["slug"])]
        tarjetas.append({**r, "paradas": suyas, "foto": con_foto[-1] if con_foto else None})
    return tarjetas


@bp.route("/")
def inicio():
    hoy = hoy_en_lima()
    comunidades = comunidad.listar_publicas()
    paradas = ruta.paradas_para_mapa()               # una sola vez: el mapa y las tarjetas
    return render_template(
        "publico/inicio.html",
        hoy=hoy,
        manana=hoy + timedelta(days=1),
        salidas=salida.listar_publicas(hoy),
        alertas=alerta.vigentes(),
        rutas=_rutas_con_paradas(ruta.listar_activas(), paradas, comunidades),
        comunidades=comunidades,
        mapa=mapa.construir(comunidades, paradas),
        # v2.3: la comunidad de la foto grande de la portada (con su nombre y crédito)
        portada=next((c for c in comunidades if c["slug"] == imagenes.FOTO_PORTADA
                      and imagenes.foto_comunidad(c["slug"])), None),
    )


@bp.route("/salidas")
def salidas():
    hoy = hoy_en_lima()
    rutas = ruta.listar_activas()
    errores = {}

    texto_fecha = request.args.get("fecha", "").strip()
    fecha = hoy
    if texto_fecha:
        try:
            fecha = date.fromisoformat(texto_fecha)
        except ValueError:
            errores["fecha"] = "Escribe la fecha como año-mes-día, por ejemplo 2026-10-21."
        else:
            if abs((fecha - hoy).days) > 366:
                errores["fecha"] = "Elige una fecha dentro del próximo año."

    codigo_ruta = request.args.get("ruta", "").strip() or None
    if codigo_ruta is not None and codigo_ruta not in {r["codigo"] for r in rutas}:
        errores["ruta"] = "Esa ruta no existe. Elige una de la lista."

    if errores:
        # Con un dato mal escrito se muestra el error y, debajo, las salidas de hoy.
        fecha, codigo_ruta = hoy, None
    lista = salida.listar_publicas(fecha, codigo_ruta)

    # Los próximos 7 días, con cuántas salidas tiene cada uno (0 si ninguna)
    por_dia = {f["dia"]: f["salidas"] for f in salida.dias_con_salidas(7)}
    dias = [(hoy + timedelta(days=i), por_dia.get(hoy + timedelta(days=i), 0)) for i in range(7)]

    pagina = render_template("publico/salidas.html", salidas=lista, fecha=fecha, hoy=hoy,
                             dias=dias, rutas=rutas, codigo_ruta=codigo_ruta, errores=errores,
                             texto_fecha=texto_fecha,
                             feriados=feriados.de_las_fechas([d for d, _ in dias] + [fecha]))
    return pagina, (422 if errores else 200)


@bp.route("/salidas/<int:salida_id>")
def detalle_salida(salida_id):
    datos = salida.buscar_publica(salida_id)
    if datos is None:
        abort(404)
    return render_template(
        "publico/salida.html",
        s=datos,
        paradas=ruta.paradas(datos["ruta_id"]),
        precios=tarifa.precios_para_salida(salida_id),
        alertas=salida.alertas_que_la_afectan(salida_id),
        puede_reservar="reservas.reservar" in current_app.view_functions,
        opiniones=resena.publicadas_de_ruta(datos["ruta_id"]),
        mapa=_datos_del_mapa(ruta_id=datos["ruta_id"]),         # el recorrido, numerado
        # APIs (v2.2): clima a la hora del zarpe, feriado y precios en dólares (None sin datos)
        clima=clima.para_la_hora(datos["fecha_hora_zarpe"]),
        feriado=feriados.de_la_fecha(datos["fecha_hora_zarpe"].date()),
        cambio=tipo_cambio.del_dia(),
    )


@bp.route("/comunidades")
def comunidades():
    lista = comunidad.listar_publicas()
    return render_template("publico/comunidades.html", comunidades=lista,
                           mapa=_datos_del_mapa(lista))


@bp.route("/comunidades/<slug>")
def detalle_comunidad(slug):
    datos = comunidad.buscar_por_slug(slug)
    if datos is None:
        abort(404)
    familias = comunidad.familias_publicas(datos["id"])
    return render_template(
        "publico/comunidad.html",
        c=datos,
        familias=familias,
        # "Artesanía": familias que ofrecen taller textil (el SET llega como "desayuno,cena,...")
        talleres=sum("taller_textil" in (f["servicios"] or "").split(",") for f in familias),
        rutas=comunidad.rutas_que_la_visitan(datos["id"]),
        salidas=comunidad.proximas_salidas(datos["id"]),
        mapa=_datos_del_mapa(resaltadas={datos["slug"]}),         # dónde queda y quién llega
    )


@bp.route("/alertas")
def alertas():
    lista = alerta.para_pagina_publica()
    grupos = {g: [a for a in lista if a["grupo"] == g] for g in ("vigente", "proxima", "pasada")}
    return render_template("publico/alertas.html", grupos=grupos)


@bp.route("/idioma/<any(es, en):codigo>")
def idioma(codigo):
    """Español o inglés para el turista (8.9). Se guarda en la sesión y vuelve a la misma página."""
    session["idioma"] = codigo
    return redirect(destino_seguro(request.args.get("volver")) or url_for("publico.inicio"))


@bp.route("/salud")
def salud():
    """JSON {ok, hora}: 200 si la base responde, 503 si no (sin detalles del error)."""
    try:
        ahora = sistema.hora_de_la_base()
    except pymysql.MySQLError as error:
        codigo = error.args[0] if error.args else "?"
        current_app.logger.warning("/salud: la base no responde (error %s)", codigo)
        ahora_python = datetime.now(ZoneInfo(current_app.config["ZONA_HORARIA"]))
        respuesta = jsonify(ok=False, hora=ahora_python.isoformat(timespec="seconds"))
        respuesta.status_code = 503
    else:
        hora = ahora.replace(tzinfo=ZoneInfo(current_app.config["ZONA_HORARIA"]))
        respuesta = jsonify(ok=True, hora=hora.isoformat(timespec="seconds"))
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta

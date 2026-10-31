"""Páginas públicas (sin cuenta): portada, salidas, comunidades, galería, contacto, alertas
y /salud.

Nivel Plata: cada página lee sus datos de la base a través de los modelos.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pymysql
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app.formularios.contacto import ASUNTOS, FormularioContacto
from app.modelos import (
    ErrorValidacion,
    abordaje,
    alerta,
    comunidad,
    producto,
    resena,
    ruta,
    salida,
    sistema,
    tarifa,
)
from app.modelos import contacto as modelo_contacto
from app.seguridad import destino_seguro, ip_cliente, limitador
from app.servicios import (
    clima,
    correo,
    feriados,
    formato,
    imagenes,
    mapa,
    textos,
    tipo_cambio,
    whatsapp,
)
from app.servicios.textos import t, traducir_formulario

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
        productos=producto.destacados(3),          # v2.9: lo último de las islas
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


@bp.route("/galeria")
def galeria():
    """v2.5: las fotos de las comunidades en mosaico; cada una se abre en grande con su nombre,
    su descripción y su crédito (js/galeria.js). Se puede filtrar por idioma originario."""
    idioma = request.args.get("idioma")
    if idioma not in formato.IDIOMAS:                 # lista blanca: quechua o aimara
        idioma = None
    con_foto = [c for c in comunidad.listar_publicas() if imagenes.foto_comunidad(c["slug"])]
    return render_template(
        "publico/galeria.html", idioma=idioma, idiomas=formato.IDIOMAS, total=len(con_foto),
        fotos=[c for c in con_foto if idioma in (None, c["idioma_originario"])],
        cuantas={i: sum(c["idioma_originario"] == i for c in con_foto) for i in formato.IDIOMAS})


def _texto_del_correo(datos, asunto, idioma):
    """El correo que recibe la agencia (en español: lo lee el personal)."""
    return "\n".join([
        "Llegó un mensaje desde la página Contacto de Titicaca Vivo.",
        "",
        f"Nombre: {datos['nombre']}",
        f"Correo: {datos['correo'] or '—'}",
        f"Celular o WhatsApp: {datos['telefono'] or '—'}",
        f"Asunto: {asunto}",
        f"Idioma de la página: {'inglés' if idioma == 'en' else 'español'}",
        "",
        "Mensaje:",
        datos["mensaje"],
        "",
        "Responde directamente a la persona, a su correo o a su celular.",
    ])


@bp.route("/contacto", methods=["GET", "POST"])
@limitador.limit(lambda: current_app.config["LIMITE_MENSAJES_CONTACTO"], methods=["POST"])
def contacto():
    """v2.6: atención, dónde zarpamos y el formulario. El mensaje llega por correo a la agencia
    (simulado por defecto, como la recuperación de contraseña) y la bitácora anota que llegó."""
    formulario = FormularioContacto()
    error_general, codigo_http = None, 200
    if request.method == "POST":
        if formulario.sitio_web.data:                 # la trampa para robots vino llena
            flash(t("¡Gracias! Recibimos tu mensaje y te responderemos pronto."), "exito")
            return redirect(url_for("publico.contacto"), code=303)
        datos = {campo: formulario[campo].data
                 for campo in ("nombre", "correo", "telefono", "asunto", "mensaje")}
        try:
            if not formulario.validate():
                raise ErrorValidacion({})
            modelo_contacto.validar(datos)
        except ErrorValidacion as error:
            for nombre, texto in error.errores.items():
                formulario[nombre].errors = [*formulario[nombre].errors, texto]
            codigo_http = 422
        else:
            asunto = dict(ASUNTOS)[datos["asunto"]]
            resultados = [correo.enviar(destino, f"[Titicaca Vivo] Contacto: {asunto}",
                                        _texto_del_correo(datos, asunto, textos.idioma()))
                          for destino in modelo_contacto.destinatarios(
                              current_app.config["AGENCIA_CORREO"])]
            enviados = sum(r != correo.FALLO for r in resultados)
            if enviados:
                modelo_contacto.anotar_recibido(datos["asunto"], textos.idioma(), enviados,
                                                ip_cliente())
                flash(t("¡Gracias! Recibimos tu mensaje y te responderemos pronto."), "exito")
                return redirect(url_for("publico.contacto"), code=303)
            error_general = t("No pudimos enviar tu mensaje ahora. Escríbenos por WhatsApp o "
                              "inténtalo en unos minutos.")
            codigo_http = 503
    traducir_formulario(formulario)
    numero = current_app.config["AGENCIA_WHATSAPP"]
    latitud, longitud = mapa.PUNO
    return render_template(
        "publico/contacto.html", f=formulario, error_general=error_general,
        muelles=ruta.muelles(), horario=current_app.config["AGENCIA_HORARIO"],
        correo_agencia=current_app.config["AGENCIA_CORREO"],
        whatsapp=whatsapp.enlace(t("Hola, quiero información sobre las salidas al lago."), numero)
        if numero else None,
        mapa_url=f"https://www.openstreetmap.org/?mlat={latitud}&mlon={longitud}"
                 f"#map=15/{latitud}/{longitud}",
    ), codigo_http


@bp.route("/privacidad")
def privacidad():
    """v2.7: política de privacidad (Ley 29733), en español."""
    return render_template("publico/privacidad.html")


@bp.route("/condiciones")
def condiciones():
    """v2.7: condiciones del servicio. Los números salen de la configuración y de los modelos:
    si cambia una regla (RN-05 pago, RN-12 embarque), el texto cambia con ella."""
    return render_template(
        "publico/condiciones.html", minutos_pago=current_app.config["MINUTOS_VENCIMIENTO_PAGO"],
        maximo=current_app.config["MAX_PASAJEROS_POR_RESERVA"],
        abre=abordaje.MINUTOS_ANTES, cierra=abordaje.MINUTOS_DESPUES)


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

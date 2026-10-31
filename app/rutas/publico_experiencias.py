"""Experiencias en las comunidades y viajes en grupo (v2.8).

- /experiencias: qué se puede vivir en cada comunidad, con los datos de la base (paradas de las
  rutas, noche con una familia, servicios de las familias, señal). Se filtra por actividad.
- /grupos: pedido de cotización (colegios, empresas...). Muestra el precio referencial y llega
  por correo a la agencia, como Contacto; la bitácora anota el pedido sin datos personales.

Las rutas se registran en el blueprint `publico`. Ningún SQL aquí.
"""

from flask import current_app, flash, redirect, render_template, request, url_for

from app.formularios.grupo import TIPOS_GRUPO, FormularioGrupo
from app.modelos import ErrorValidacion, comunidad, ruta
from app.modelos import contacto as modelo_contacto
from app.rutas.publico import bp, hoy_en_lima
from app.seguridad import ip_cliente, limitador
from app.servicios import correo, formato, textos
from app.servicios.textos import t, traducir_formulario

# Filtros de /experiencias: clave → (etiqueta, ¿la comunidad la ofrece?)
COMIDAS = ("desayuno", "almuerzo", "cena")
ACTIVIDADES = {
    "noche": ("Noche con una familia", lambda c: bool(c["noche"])),
    "comida": ("Comida casera", lambda c: any(s in c["servicios"] for s in COMIDAS)),
    "taller_textil": ("Taller textil", lambda c: "taller_textil" in c["servicios"]),
    "vestimenta": ("Vestimenta típica", lambda c: "vestimenta" in c["servicios"]),
}


@bp.route("/experiencias")
def experiencias():
    actividad = request.args.get("actividad")
    if actividad not in ACTIVIDADES:                  # lista blanca
        actividad = None
    todas = comunidad.experiencias()
    return render_template(
        "publico/experiencias.html", actividad=actividad, total=len(todas),
        actividades={clave: etiqueta for clave, (etiqueta, _) in ACTIVIDADES.items()},
        cuantas={clave: sum(map(ofrece, todas)) for clave, (_, ofrece) in ACTIVIDADES.items()},
        comunidades=[c for c in todas if actividad is None or ACTIVIDADES[actividad][1](c)],
        comidas=COMIDAS)


def _texto_cotizacion(datos, ruta_elegida, estimado):
    """El correo que recibe la agencia (en español: lo lee el personal)."""
    return "\n".join([
        "Llegó un pedido de cotización para un grupo desde la página de Titicaca Vivo.", "",
        f"Grupo: {dict(TIPOS_GRUPO)[datos['tipo']]}"
        + (f" · {datos['institucion']}" if datos["institucion"] else ""),
        f"Personas: {datos['personas']}",
        f"Fecha que prefieren: {formato.fecha_larga(datos['fecha'])} de {datos['fecha'].year}",
        f"Ruta: {ruta_elegida['nombre']}",
        f"Precio referencial: desde {formato.soles(estimado)}" if estimado else
        "Precio referencial: la ruta no tiene tarifa vigente",
        "", f"Contacto: {datos['nombre']}",
        f"Correo: {datos['correo'] or '—'} · Celular o WhatsApp: {datos['telefono'] or '—'}",
        "", "Comentarios:", datos["comentarios"] or "—", "",
        "Responde a la persona con la cotización final y, si acepta, programa la salida.",
    ])


@bp.route("/grupos", methods=["GET", "POST"])
@limitador.limit(lambda: current_app.config["LIMITE_COTIZACIONES_GRUPO"], methods=["POST"])
def grupos():
    rutas = ruta.listar_activas()
    formulario = FormularioGrupo()
    formulario.ruta.choices = [(r["codigo"], r["nombre"]) for r in rutas]
    error_general, codigo_http = None, 200
    if request.method == "POST":
        if formulario.sitio_web.data:                 # la trampa para robots vino llena
            return redirect(url_for("publico.grupos"), code=303)
        datos = {campo: formulario[campo].data for campo in
                 ("tipo", "institucion", "personas", "fecha", "ruta", "nombre", "correo",
                  "telefono", "comentarios")}
        datos["idioma"] = textos.idioma()
        try:
            if not formulario.validate():
                raise ErrorValidacion({})
            elegida = modelo_contacto.validar_grupo(datos, rutas, hoy_en_lima())
        except ErrorValidacion as error:
            for nombre, texto in error.errores.items():
                formulario[nombre].errors = [*formulario[nombre].errors, texto]
            codigo_http = 422
        else:
            estimado = modelo_contacto.estimar(elegida, datos["personas"])
            resultados = [correo.enviar(destino, f"[Titicaca Vivo] Cotización para un grupo de "
                                                 f"{datos['personas']} personas",
                                        _texto_cotizacion(datos, elegida, estimado))
                          for destino in modelo_contacto.destinatarios(
                              current_app.config["AGENCIA_CORREO"])]
            enviados = sum(r != correo.FALLO for r in resultados)
            if enviados:
                modelo_contacto.anotar_cotizacion(datos, enviados, ip_cliente())
                if estimado:
                    flash(t("¡Gracias! Te enviaremos la cotización para {personas} personas. "
                            "Precio referencial: desde {total}.", personas=datos["personas"],
                            total=formato.soles(estimado)), "exito")
                else:
                    flash(t("¡Gracias! Te enviaremos la cotización para {personas} personas.",
                            personas=datos["personas"]), "exito")
                return redirect(url_for("publico.grupos"), code=303)
            error_general = t("No pudimos enviar tu pedido ahora. Escríbenos por WhatsApp o "
                              "inténtalo en unos minutos.")
            codigo_http = 503
    traducir_formulario(formulario)
    return render_template("publico/grupos.html", f=formulario, rutas=rutas,
                           error_general=error_general, hoy=hoy_en_lima()), codigo_http

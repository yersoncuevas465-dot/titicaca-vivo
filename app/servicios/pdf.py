"""PDF con reportlab (sin WeasyPrint: en Windows necesita GTK).

- boleto(): el pase de abordar de una reserva, tamaño A6, con el QR.
- manifiesto(): la lista oficial de pasajeros de una salida, tamaño A4 (F5).
- dibujar_isotipo(): el sello del logo redibujado con figuras de reportlab, porque
  reportlab no lee SVG y svglib sería una dependencia nueva (D-13).
"""

import io
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, A6
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.servicios import formato
from app.servicios.textos import t

CIRUELA, TERRACOTA, CREMA = HexColor("#572B44"), HexColor("#C27A52"), HexColor("#FEF9F3")
ARENA, TINTA, GRIS = HexColor("#F5E9DC"), HexColor("#2A1220"), HexColor("#5E4654")


def _olas(trazo, x0, y, ancho_tramo, tramos, alto=4):
    """Olas como en el SVG ('q' y 't'): curvas cuadráticas convertidas a cúbicas."""
    trazo.moveTo(x0, y)
    for i in range(tramos):
        inicio_x = x0 + i * ancho_tramo
        fin_x = inicio_x + ancho_tramo
        control = (inicio_x + ancho_tramo / 2, y - alto if i % 2 == 0 else y + alto)
        c1 = (inicio_x + 2 / 3 * (control[0] - inicio_x), y + 2 / 3 * (control[1] - y))
        c2 = (fin_x + 2 / 3 * (control[0] - fin_x), y + 2 / 3 * (control[1] - y))
        trazo.curveTo(*c1, *c2, fin_x, y)


def dibujar_isotipo(c, x, y, tamano):
    """Dibuja el sello (120×120 unidades del SVG) con su esquina inferior izquierda en (x, y)."""
    c.saveState()
    # Mismo sistema que el SVG: origen arriba a la izquierda y la y crece hacia abajo.
    c.translate(x, y + tamano)
    c.scale(tamano / 120, -tamano / 120)
    c.setFillColor(CIRUELA)
    c.circle(60, 60, 58, stroke=0, fill=1)

    c.saveState()
    recorte = c.beginPath()
    recorte.circle(60, 60, 52)
    c.clipPath(recorte, stroke=0, fill=0)
    c.setStrokeColor(TERRACOTA)
    c.setLineWidth(4)
    c.setLineCap(1)
    for x1, y1, x2, y2 in ((60, 39, 60, 33), (73.5, 42.6, 76.5, 37.4), (46.5, 42.6, 43.5, 37.4),
                           (83.4, 52.5, 88.6, 49.5), (36.6, 52.5, 31.4, 49.5)):
        c.line(x1, y1, x2, y2)
    sol = c.beginPath()
    sol.arc(38, 44, 82, 88, startAng=180, extent=180)
    sol.close()
    c.setFillColor(TERRACOTA)
    c.drawPath(sol, stroke=0, fill=1)

    cordillera = c.beginPath()
    puntos = [(4, 66), (12, 60), (21, 54), (28, 58), (34, 56.5), (42, 62), (50, 63.5), (60, 62.5),
              (70, 63.5), (79, 61), (86, 57), (97, 52.5), (105, 57), (110, 56), (116, 66)]
    cordillera.moveTo(*puntos[0])
    for punto in puntos[1:]:
        cordillera.lineTo(*punto)
    cordillera.close()
    c.setFillColor(TINTA)
    c.drawPath(cordillera, stroke=0, fill=1)

    balsa = c.beginPath()
    balsa.moveTo(17, 59)
    balsa.curveTo(24, 66, 30, 76, 42, 78)
    balsa.lineTo(78, 78)
    balsa.curveTo(90, 76, 96, 66, 103, 59)
    balsa.curveTo(101, 72, 93, 85, 80, 85)
    balsa.lineTo(40, 85)
    balsa.curveTo(27, 85, 19, 72, 17, 59)
    balsa.close()
    c.setFillColor(ARENA)
    c.drawPath(balsa, stroke=0, fill=1)
    c.setStrokeColor(CIRUELA)
    c.setLineWidth(1.6)
    c.line(36, 81.5, 84, 81.5)

    olas = c.beginPath()
    _olas(olas, 27, 95, 11, 6)
    _olas(olas, 39, 104, 11, 4)
    c.setStrokeColor(CREMA)
    c.setLineWidth(3)
    c.drawPath(olas, stroke=1, fill=0)
    c.restoreState()

    c.setStrokeColor(ARENA)
    c.setLineWidth(1.5)
    c.circle(60, 60, 52, stroke=1, fill=0)
    c.restoreState()


def _texto(c, x, y, texto, fuente="Helvetica", tamano=9, color=TINTA, ancho=None):
    """Escribe texto (partiéndolo en líneas si hay ancho). Devuelve la y de la línea siguiente."""
    c.setFont(fuente, tamano)
    c.setFillColor(color)
    lineas = simpleSplit(str(texto), fuente, tamano, ancho) if ancho else [str(texto)]
    for linea in lineas:
        c.drawString(x, y, linea)
        y -= tamano * 1.3
    return y


def boleto(reserva, pasajeros, qr_png):
    """Bytes del PDF del pase de abordar (A6 vertical)."""
    memoria = io.BytesIO()
    ancho, alto = A6
    c = canvas.Canvas(memoria, pagesize=A6)
    c.setTitle(f"{t('Boleto')} {reserva['codigo']} - Titicaca Vivo")
    c.setAuthor("Titicaca Vivo")

    # Franja superior con el sello
    c.setFillColor(CIRUELA)
    c.rect(0, alto - 64, ancho, 64, stroke=0, fill=1)
    dibujar_isotipo(c, 12, alto - 56, 48)
    _texto(c, 70, alto - 30, "Titicaca Vivo", "Helvetica-Bold", 16, CREMA)
    _texto(c, 70, alto - 46, t("Pase de abordar"), "Helvetica", 10, ARENA)

    # Código y salida (columna izquierda) + QR (derecha)
    y = alto - 92
    _texto(c, 14, y, t("Código de reserva"), "Helvetica", 8, GRIS)
    _texto(c, 14, y - 22, reserva["codigo"], "Helvetica-Bold", 22, CIRUELA)
    y = _texto(c, 14, y - 44, reserva["ruta_nombre"], "Helvetica-Bold", 11, TINTA, ancho=150)
    zarpe = reserva["fecha_hora_zarpe"]
    y = _texto(c, 14, y - 2, formato.inicial_mayuscula(formato.fecha_larga(zarpe)), ancho=150)
    y = _texto(c, 14, y, t("Zarpe: {hora}  ·  {muelle}").format(
        hora=formato.hora(zarpe), muelle=reserva["muelle_salida"]), ancho=150)
    y = _texto(c, 14, y, t("Lancha: {nombre}").format(nombre=reserva["embarcacion_nombre"]),
               ancho=150)
    c.drawImage(ImageReader(io.BytesIO(qr_png)), ancho - 130, alto - 196, 116, 116)
    _texto(c, ancho - 126, alto - 206, t("Lo lee el guía o el capitán"), "Helvetica", 7, GRIS)

    # Pasajeros
    y = min(y, alto - 214) - 8
    c.setStrokeColor(TERRACOTA)
    c.setLineWidth(1)
    c.line(14, y + 6, ancho - 14, y + 6)
    y = _texto(c, 14, y - 6, t("Pasajeros ({n})").format(n=len(pasajeros)), "Helvetica-Bold",
               10, CIRUELA)
    for p in pasajeros:
        documento = f"{p['tipo_documento']} ···{p['numero_documento'][-3:]}"
        linea = f"{p['nombres']} {p['apellidos']}  ·  {documento}"
        y = _texto(c, 18, y, linea, "Helvetica", 8.5, TINTA, ancho=ancho - 36)

    # Pago y avisos
    y -= 4
    resumen = t("Total: {total}  ·  Estado: {estado}").format(
        total=formato.soles(reserva["total"]), estado=reserva["estado_texto"])
    y = _texto(c, 14, y, resumen, "Helvetica-Bold", 9.5, TINTA, ancho=ancho - 28)
    _texto(c, 14, 30, t("Preséntate en el muelle 30 minutos antes del zarpe con tu documento."),
           "Helvetica", 7.5, GRIS, ancho=ancho - 28)
    c.showPage()
    c.save()
    return memoria.getvalue()


# --- Manifiesto de zarpe (F5) ----------------------------------------------------------------

def manifiesto(salida, pasajeros, generado_en):
    """Bytes del PDF del manifiesto (A4): lancha, matrícula, capitán y cada pasajero con su
    documento y nacionalidad (sección 8.4). La tabla sigue en otra hoja si no entra."""
    memoria = io.BytesIO()
    ancho, alto = A4
    margen = 15 * mm
    zarpe = salida["fecha_hora_zarpe"]
    titulo = f"Manifiesto de zarpe - {salida['ruta_nombre']} - {zarpe:%d/%m/%Y %H:%M}"

    def cabecera_y_pie(c, documento):
        c.saveState()
        c.setFillColor(CIRUELA)
        c.rect(0, alto - 26 * mm, ancho, 26 * mm, stroke=0, fill=1)
        dibujar_isotipo(c, margen, alto - 22 * mm, 18 * mm)
        _texto(c, margen + 22 * mm, alto - 12 * mm, "Manifiesto de zarpe", "Helvetica-Bold", 16,
               CREMA)
        _texto(c, margen + 22 * mm, alto - 19 * mm, "Titicaca Vivo · Puno, lago Titicaca",
               "Helvetica", 9, ARENA)
        _texto(c, margen, 10 * mm, f"Generado el {generado_en:%d/%m/%Y %H:%M} (hora de Lima)  ·  "
               f"Hoja {documento.page}", "Helvetica", 7.5, GRIS)
        c.restoreState()

    estilos = getSampleStyleSheet()
    normal = ParagraphStyle("normal", parent=estilos["Normal"], fontName="Helvetica",
                            fontSize=9, leading=11.5, textColor=TINTA)
    negrita = ParagraphStyle("negrita", parent=normal, fontName="Helvetica-Bold")
    subtitulo = ParagraphStyle("subtitulo", parent=negrita, fontSize=12, leading=15,
                               textColor=CIRUELA, spaceAfter=4)

    def p(texto, estilo=normal):
        return Paragraph(escape(str(texto)), estilo)

    datos_viaje = [
        [p("Ruta", negrita), p(salida["ruta_nombre"]),
         p("Zarpe", negrita), p(f"{formato.fecha_larga(zarpe)}, {formato.hora(zarpe)}")],
        [p("Muelle", negrita), p(salida["muelle_salida"]),
         p("Retorno", negrita), p(formato.fecha_hora(salida["fecha_hora_retorno"]))],
        [p("Lancha", negrita), p(f"{salida['embarcacion_nombre']} · {salida['matricula']}"),
         p("Cupo", negrita), p(f"{salida['cupo']} (lancha de {salida['capacidad_maxima']})")],
        [p("Capitán", negrita), p(f"{salida['capitan']} · {salida['licencia_navegacion'] or '—'}"),
         p("Guía", negrita), p(salida["guia"] or "Sin guía")],
    ]
    tabla_viaje = Table(datos_viaje, colWidths=[22 * mm, 70 * mm, 20 * mm, 68 * mm])
    tabla_viaje.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ARENA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, CREMA),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))

    filas = [[p(t, negrita) for t in ("N.°", "Apellidos y nombres", "Documento", "País",
                                      "Tipo", "Reserva", "Abordó")]]
    for numero, pasajero in enumerate(pasajeros, start=1):
        filas.append([
            p(numero), p(f"{pasajero['apellidos']}, {pasajero['nombres']}"),
            p(f"{pasajero['tipo_documento']} {pasajero['numero_documento']}"),
            p(pasajero["nacionalidad"]), p(pasajero["tipo"]), p(pasajero["codigo"]),
            p(formato.hora(pasajero["abordo_en"]) if pasajero["abordo_en"] else "—"),
        ])
    if len(filas) == 1:
        filas.append([p("—"), p("Sin pasajeros con reserva activa."), "", "", "", "", ""])
    tabla = Table(filas, repeatRows=1,
                  colWidths=[9 * mm, 49 * mm, 38 * mm, 11 * mm, 30 * mm, 25 * mm, 18 * mm])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ARENA),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, HexColor("#D9C7B5")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))

    abordaron = sum(1 for x in pasajeros if x["abordo_en"])
    historia = [
        p(f"{salida['ruta_nombre']} · {formato.fecha_larga(zarpe).capitalize()}", subtitulo),
        tabla_viaje, Spacer(1, 6 * mm),
        p(f"Pasajeros: {len(pasajeros)}  ·  Abordaron: {abordaron}  ·  "
          f"Estado de la salida: {salida['estado'].capitalize()}", negrita),
        Spacer(1, 2 * mm), tabla, Spacer(1, 14 * mm),
        p("Firma del capitán: ____________________________      "
          "Firma del guía: ____________________________"),
    ]
    documento = SimpleDocTemplate(memoria, pagesize=A4, leftMargin=margen, rightMargin=margen,
                                  topMargin=32 * mm, bottomMargin=18 * mm, title=titulo,
                                  author="Titicaca Vivo")
    documento.build(historia, onFirstPage=cabecera_y_pie, onLaterPages=cabecera_y_pie)
    return memoria.getvalue()

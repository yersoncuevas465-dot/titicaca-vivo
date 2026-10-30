"""Mapa esquemático del lago en SVG propio (sin mapas externos ni JavaScript).

Lo que viene de la BASE: las comunidades (con su latitud y longitud) y las rutas
con sus paradas en orden. Lo que es DIBUJO fijo (como una ilustración): la orilla
simplificada, las islas, Puno y la boca de la bahía por donde pasan las lanchas.

Proyección: un rectángulo de 0.44° × 0.40° alrededor de la bahía de Puno.
A esta latitud 1° de longitud ≈ 107 km y 1° de latitud ≈ 110.6 km, así que
1 unidad del SVG ≈ 100 m y el mapa no se deforma.
"""

LON_OESTE, LON_ESTE = -70.06, -69.62
LAT_NORTE, LAT_SUR = -15.56, -15.96
ANCHO, ALTO = 470, 440

# Puno (muelle) y la boca de la bahía, entre las puntas de Capachica y Chucuito (aproximados)
PUNO = (-15.835, -70.015)
BOCA_BAHIA = (-15.7645, -69.7885)
LIMITE_BAHIA_X = 270     # a la izquierda: bahía de Puno; a la derecha (pasando 300): lago abierto

# Orilla simplificada (unidades del SVG). Es un dibujo: no son datos del negocio.
TIERRA = (
    # tierra firme al oeste y al sur, con la península de Chucuito
    "M0,0 L70,0 L92,40 L105,95 L102,150 L90,200 L75,245 L58,280 L50,300 L44,318 L62,338 "
    "L105,352 L150,360 L176,352 L190,322 L205,296 L220,276 L236,270 L246,284 L240,314 "
    "L232,345 L246,372 L290,395 L340,418 L380,440 L0,440 Z",
    # península de Capachica (sigue hacia el norte, fuera del mapa)
    "M120,0 L200,0 L235,40 L250,80 L270,110 L300,135 L330,160 L345,178 L338,192 L310,190 "
    "L280,175 L250,165 L220,160 L190,150 L160,130 L140,100 L125,60 Z",
)
ISLAS = (  # (cx, cy, rx, ry, giro) — Amantaní, Taquile y Ticonata
    (374, 115, 21, 19, 0),
    (401, 239, 26, 8, -25),
    (291, 97, 6, 4, 0),
)
COLORES_RUTA = ("#572B44", "#1F5E3B", "#8F3F12", "#2F5D8A", "#8A6100", "#5E4654")


def proyectar(latitud, longitud):
    """Convierte (latitud, longitud) en (x, y) del SVG, con 1 decimal."""
    lat, lon = float(latitud), float(longitud)
    x = (lon - LON_OESTE) / (LON_ESTE - LON_OESTE) * ANCHO
    y = (LAT_NORTE - lat) / (LAT_NORTE - LAT_SUR) * ALTO
    return round(x, 1), round(y, 1)


def _cruza_la_bahia(a, b):
    """True si un tramo va de la bahía al lago abierto: entonces pasa por la boca."""
    izquierda, derecha = sorted((a[0], b[0]))
    return izquierda < LIMITE_BAHIA_X and derecha > LIMITE_BAHIA_X + 30


def trazo_de_ruta(puntos):
    """Agrega la boca de la bahía en los tramos que la cruzan."""
    boca = proyectar(*BOCA_BAHIA)
    trazo = [puntos[0]]
    for siguiente in puntos[1:]:
        if _cruza_la_bahia(trazo[-1], siguiente):
            trazo.append(boca)
        trazo.append(siguiente)
    return trazo


def construir(comunidades, paradas, ruta_id=None, resaltadas=(), todo_el_lago=False):
    """Arma los datos del mapa para la plantilla publico/_mapa.html.

    comunidades: filas con slug, nombre, idioma_originario, latitud, longitud.
    paradas: filas (ya ordenadas por ruta y orden) con ruta_id, codigo, nombre, slug,
             latitud, longitud.
    ruta_id: la ruta de una salida. Va resaltada, con sus paradas numeradas, y `recorrido`
             trae los nombres en orden (el mismo recorrido en texto, para leerlo sin el dibujo).
    resaltadas: slugs de comunidades con un halo (la de una alerta o la de su página). Las rutas
             que paran en ellas también van resaltadas.
    todo_el_lago: una alerta para todo el lago: el agua se tiñe y todas las rutas se resaltan.
    """
    puno = proyectar(*PUNO)
    resaltadas = set(resaltadas)
    nombres = {c["slug"]: c["nombre"] for c in comunidades}

    rutas, por_ruta = [], {}
    for p in paradas:
        if p["latitud"] is None:
            continue
        if p["ruta_id"] not in por_ruta:
            por_ruta[p["ruta_id"]] = {"id": p["ruta_id"], "codigo": p["codigo"],
                                      "nombre": p["nombre"], "puntos": [puno], "slugs": []}
            rutas.append(por_ruta[p["ruta_id"]])
        por_ruta[p["ruta_id"]]["puntos"].append(proyectar(p["latitud"], p["longitud"]))
        por_ruta[p["ruta_id"]]["slugs"].append(p["slug"])

    for indice, ruta in enumerate(rutas):
        # Cada ruta se corre un poco para que no se tapen en el tramo común Puno–Uros.
        corrimiento = (indice - (len(rutas) - 1) / 2) * 3
        trazo = trazo_de_ruta(ruta["puntos"])
        ruta["color"] = COLORES_RUTA[indice % len(COLORES_RUTA)]
        ruta["polilinea"] = " ".join(
            f"{x + corrimiento:.1f},{y + corrimiento:.1f}" for x, y in trazo)
        ruta["resaltada"] = (ruta["id"] == ruta_id or todo_el_lago
                             or bool(resaltadas & set(ruta["slugs"])))
    hay_resalte = ruta_id is not None or bool(resaltadas) or todo_el_lago
    for ruta in rutas:
        ruta["tenue"] = hay_resalte and not ruta["resaltada"]
    # La ruta resaltada se dibuja al final: queda encima de las demás
    rutas.sort(key=lambda r: r["resaltada"])

    elegida = por_ruta.get(ruta_id)
    en_la_ruta = set(elegida["slugs"]) if elegida else set()
    puntos = []
    for c in comunidades:
        if c["latitud"] is None:
            continue
        x, y = proyectar(c["latitud"], c["longitud"])
        a_la_izquierda = x > ANCHO - 90          # cerca del borde: el nombre va a la izquierda
        puntos.append({
            "slug": c["slug"], "nombre": c["nombre"], "idioma": c["idioma_originario"],
            "x": x, "y": y,
            "texto_x": x - 9 if a_la_izquierda else x + 9,
            "ancla": "end" if a_la_izquierda else "start",
            "resaltada": c["slug"] in resaltadas,
            "tenue": elegida is not None and c["slug"] not in en_la_ruta,
        })

    paradas_numeradas, recorrido = [], []
    if elegida:
        for numero, (slug, (x, y)) in enumerate(zip(elegida["slugs"], elegida["puntos"][1:],
                                                     strict=True), start=1):
            paradas_numeradas.append({"n": numero, "x": round(x - 13, 1), "y": round(y - 13, 1)})
            recorrido.append(nombres.get(slug, slug))

    return {
        "ancho": ANCHO, "alto": ALTO, "tierra": TIERRA, "islas": ISLAS,
        "puno": {"x": puno[0], "y": puno[1], "nombre": "Puno"},
        "comunidades": puntos, "rutas": rutas,
        "paradas_numeradas": paradas_numeradas, "recorrido": recorrido,
        "todo_el_lago": todo_el_lago,
        "escala_10km": 100,   # 1 unidad ≈ 100 m
    }

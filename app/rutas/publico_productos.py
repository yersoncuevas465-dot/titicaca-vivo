"""Productos y artesanías de las islas (v2.9): lo que ofrecen la agencia y los residentes de
cada comunidad, con su precio, sus características y dónde encontrarlo.

Se filtra por lugar y por categoría (listas blancas). Las rutas se registran en el blueprint
`publico` (url /productos). Ningún SQL aquí.
"""

from flask import render_template, request

from app.modelos import producto as modelo_producto
from app.rutas.publico import bp

EN_PUNO = "puno"         # el filtro de los productos que tiene la agencia en Puno


def lugar_de(p):
    return p["comunidad_slug"] or EN_PUNO


@bp.route("/productos")
def productos():
    todos = modelo_producto.publicados()
    # Los lugares con productos: primero Puno (la agencia) y luego las comunidades, por nombre
    lugares = {}
    for p in sorted(todos, key=lambda p: (p["comunidad_slug"] is not None, p["comunidad"] or "")):
        nombre, cuantos = lugares.get(lugar_de(p), (p["comunidad"] or "Puno", 0))
        lugares[lugar_de(p)] = (nombre, cuantos + 1)
    lugar = request.args.get("lugar")
    if lugar not in lugares:                        # lista blanca
        lugar = None
    categoria = request.args.get("categoria")
    if categoria not in modelo_producto.CATEGORIAS:
        categoria = None
    del_lugar = [p for p in todos if lugar is None or lugar_de(p) == lugar]
    return render_template(
        "publico/productos.html", lugar=lugar, categoria=categoria, lugares=lugares,
        total=len(todos), en_el_lugar=len(del_lugar), categorias=modelo_producto.CATEGORIAS,
        por_categoria={c: sum(p["categoria"] == c for p in del_lugar)
                       for c in modelo_producto.CATEGORIAS},
        productos=[p for p in del_lugar if categoria is None or p["categoria"] == categoria])

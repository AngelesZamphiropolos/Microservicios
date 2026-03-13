from flask import Flask, request, jsonify, abort
import logging
import sqlite3
# libreria para hacer peticiones a otros servicios
import requests

app = Flask(__name__)

# Guarda los logs en catalogos.log
logging.basicConfig(filename='pedido.log', level=logging.INFO, filemode= 'w', format="%(asctime)s | %(levelname)s : %(message)s") 

DATABASE = "pedidos.db"

# URL base del microservicio de catálogo
CATALOGO_BASE_URL = "http://127.0.0.1:5001"

# Token que catálogo espera
TOKEN_PEDIDOS_CATALOGO = "PEDIDOS_CATALOGO"

# Token que este servicio espera desde Pagos para cambiar estado
TOKEN_PAGOS_PEDIDOS = "PAGOS_PEDIDOS"

# Crea una conexión nueva a la base de datos de catálogo
def conectar_db():
    conn = sqlite3.connect(DATABASE)
    # Para poder acceder a las columnas por nombre (ej: row["descripcion"])
    conn.row_factory = sqlite3.Row
    return conn

# Obtener una paleta desde la db de catalogo
def obtener_paleta(paleta_id: int):
    # Llama a GET /paletas/<id> en catálogo para obtener precio y validar que exista
    try:
        resp = requests.get(f"{CATALOGO_BASE_URL}/paletas/{paleta_id}", timeout=3)
    except requests.exceptions.RequestException:
        logging.warning("Catálogo no disponible")
        abort(503, description="Catálogo no disponible")

    # si ocurre un error
    if resp.status_code != 200:
        logging.warning(f"Error desde catálogo al obtener paleta {paleta_id}")
        abort(resp.status_code, description=f"Error desde catálogo al obtener paleta {paleta_id}")

    logging.info(f"Paleta con id = {paleta_id} encontrada")
    return resp.json()

# Llama a POST /paletas/<id>/reservar en catálogo para descontar stock
def reservar_stock_en_catalogo(paleta_id: int, cantidad: int):

    headers = {
        "Authorization": f"Bearer {TOKEN_PEDIDOS_CATALOGO}",
        "Content-Type": "application/json"
    }
    body = {"cantidad": cantidad}

    # hacemos una petición al microservicio de catálogo
    try:
        resp = requests.post(
            f"{CATALOGO_BASE_URL}/paletas/{paleta_id}/reservar",
            json=body,
            headers=headers,
            timeout=3
        )
    except requests.exceptions.RequestException:
        logging.warning("Catálogo no disponible")
        abort(503, description="Catálogo no disponible")

    # si ocurre algun error
    if resp.status_code != 200:
        # propagamos el error de catálogo
        logging.warning(f"Error al reservar stock de paleta {paleta_id}")
        abort(resp.status_code, description=f"Error al reservar stock de paleta {paleta_id}: {resp.text}")

    logging.info(f"Paleta con id = {paleta_id} reservada, cantidad = {cantidad}")
    return resp.json()

# Verifica que el llamado provenga del microservicio de Pagos
def verificar_token_pagos():
    esperado = f"Bearer {TOKEN_PAGOS_PEDIDOS}"
    
    # si la autorizacion enviada es distinta, no tiene permiso
    if request.headers.get("Authorization", "") != esperado:
        logging.warning("No autorizado para cambiar estado de pedido")
        abort(401, description="No autorizado para cambiar estado de pedido")

# Crea un nuevo pedido
@app.post("/pedidos")
def crear_pedido():
    # datos de la petición
    data = request.get_json() or {}

    cliente_id = data.get("cliente_id")
    items = data.get("items")

    # verificar que todo esté completo
    if cliente_id is None or not isinstance(items, list) or len(items) == 0:
        logging.warning("Datos inválidos: cliente_id e items son obligatorios")
        abort(400, description="Datos invalidos: cliente_id e items son obligatorios")

    # Validar y obtener precios desde catálogo, y reservar stock
    total = 0
    items_procesados = []

    for item in items:
        try:
            paleta_id = int(item["paleta_id"])
            cantidad = int(item["cantidad"])
        except (KeyError, TypeError, ValueError):
            logging.warning("Cada item debe tener paleta_id y cantidad válidos")
            abort(400, description="Cada item debe tener paleta_id y cantidad válidos")

        if cantidad <= 0:
            logging.warning("La cantidad debe ser mayor a 0")
            abort(400, description="La cantidad debe ser mayor a 0")

        # obtener info de la paleta (precio)
        paleta = obtener_paleta(paleta_id)
        precio = int(paleta["precio"])

        # reservar stock
        reservar_stock_en_catalogo(paleta_id, cantidad)

        subtotal = precio * cantidad
        total += subtotal

        items_procesados.append({
            "paleta_id": paleta_id,
            "cantidad": cantidad,
            "precio_unitario": precio,
            "subtotal": subtotal
        })

    # Guardar pedido y items en la base de datos
    conn = conectar_db()
    cur = conn.cursor()

    # estado inicial: CREADO o PENDIENTE_PAGO
    estado_inicial = "CREADO"

    cur.execute(
        "INSERT INTO pedido (cliente_id, estado, total) VALUES (?, ?, ?)",
        (cliente_id, estado_inicial, total)
    )
    pedido_id = cur.lastrowid

    for it in items_procesados:
        cur.execute(
            "INSERT INTO pedido_items (pedido_id, paleta_id, cantidad) VALUES (?, ?, ?)",
            (pedido_id, it["paleta_id"], it["cantidad"])
        )

    conn.commit()
    conn.close()

    logging.info(f"Pedido creado, id = {pedido_id}")

    return jsonify({
        "id": pedido_id,
        "cliente_id": cliente_id,
        "estado": estado_inicial,
        "total": total,
        "items": items_procesados
    }), 201


# Devuelve un pedido con sus items
@app.get("/pedidos/<int:pedido_id>")
def obtener_pedido(pedido_id):
    
    conn = conectar_db()
    cur = conn.cursor()

    cur.execute("SELECT id, cliente_id, estado, total FROM pedido WHERE id = ?", (pedido_id,))
    fila_pedido = cur.fetchone()

    if fila_pedido is None:
        conn.close()
        logging.warning("Pedido no encontrado")
        abort(404, description="Pedido no encontrado")

    cur.execute(
        "SELECT id, paleta_id, cantidad FROM pedido_items WHERE pedido_id = ?",
        (pedido_id,)
    )
    filas_items = cur.fetchall()
    conn.close()

    items = []
    for f in filas_items:
        items.append({
            "id": f["id"],
            "paleta_id": f["paleta_id"],
            "cantidad": f["cantidad"]
        })

    pedido = {
        "id": fila_pedido["id"],
        "cliente_id": fila_pedido["cliente_id"],
        "estado": fila_pedido["estado"],
        "total": fila_pedido["total"],
        "items": items
    }

    logging.info(f"Ítems de pedido con id = {pedido_id} devuelto")
    return jsonify(pedido), 200

# Cambia el estado de un pedido
# Esta ruta está pensada para que la llame el microservicio de Pagos
# Header: Authorization: Bearer PAGOS_PEDIDOS
@app.put("/pedidos/<int:pedido_id>/estado")
def actualizar_estado_pedido(pedido_id):
    
    verificar_token_pagos()

    data = request.get_json() or {}
    nuevo_estado = data.get("estado")

    if not nuevo_estado:
        logging.warning("Falta el campo 'estado'")
        abort(400, description="Falta el campo 'estado'")

    conn = conectar_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM pedido WHERE id = ?", (pedido_id,))
    fila = cur.fetchone()
    if fila is None:
        conn.close()
        logging.warning("Pedido no encontrado")
        abort(404, description="Pedido no encontrado")

    cur.execute(
        "UPDATE pedido SET estado = ? WHERE id = ?",
        (nuevo_estado, pedido_id)
    )
    conn.commit()
    conn.close()

    logging.info(f"Estado del pedido con id = {pedido_id} actualizado")

    return jsonify({
        "id": pedido_id,
        "nuevo_estado": nuevo_estado
    }), 200


if __name__ == "__main__":
    puerto = 5002
    app.run(port=5002, debug=True)

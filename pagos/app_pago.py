from flask import Flask, request, jsonify, abort
import logging
import sqlite3
import requests

app = Flask(__name__)

# Guarda los logs en catalogos.log
logging.basicConfig(filename='pago.log', level=logging.INFO, filemode= 'w', format="%(asctime)s | %(levelname)s : %(message)s") 

DATABASE = "pagos.db"

# Token que Pedidos usa para llamar a Pagos
TOKEN_PEDIDOS_PAGOS = "PEDIDOS_PAGOS"

# Token que Pagos usa para llamar a Pedidos
TOKEN_PAGOS_PEDIDOS = "PAGOS_PEDIDOS"

# URL del microservicio de Pedidos (para cambiar estado)
PEDIDOS_BASE_URL = "http://127.0.0.1:5002"


def conectar_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# Verifica que el llamado provenga del microservicio de Pedidos
def verificar_token_pedidos():
    esperado = f"Bearer {TOKEN_PEDIDOS_PAGOS}"
    if request.headers.get("Authorization", "") != esperado:
        logging.warning("No autorizado")
        abort(401, description="No autorizado")


# Llama a PUT /pedidos/<id>/estado para actualizar el estado
def notificar_pedidos(pedido_id, nuevo_estado):
    url = f"{PEDIDOS_BASE_URL}/pedidos/{pedido_id}/estado"

    headers = {
        "Authorization": f"Bearer {TOKEN_PAGOS_PEDIDOS}",
        "Content-Type": "application/json"
    }

    body = {"estado": nuevo_estado}

    try:
        resp = requests.put(url, json=body, headers=headers, timeout=3)
    except requests.exceptions.RequestException:
        logging.warning("No se pudo contactar al servicio de pedidos")
        abort(503, description="No se pudo contactar al servicio de pedidos")

    if resp.status_code != 200:
        logging.warning("Pedidos rechazó el cambio de estado")
        abort(resp.status_code, description="Pedidos rechazó el cambio de estado")

    logging.info(f"Pedido {pedido_id} notificado")

    return resp.json()


# Crea un pago nuevo
@app.post("/pagos")
def registrar_pago():
    verificar_token_pedidos()

    # Estraer la info del post
    data = request.get_json() or {}

    # Separarlos para validar
    pedido_id = data.get("pedido_id")
    metodo = data.get("metodo")

    if not pedido_id or not metodo:
        logging.warning("Faltan datos")
        abort(400, description="Faltan datos!!")

    conn = conectar_db()
    cursor = conn.cursor()

    # Insertamos el pago como APROBADO 
    estado = "APROBADO"
    cursor.execute(
        "INSERT INTO pagos (pedido_id, metodo, estado) VALUES (?, ?, ?)",
        (pedido_id, metodo, estado)
    )

    pago_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Notificamos a Pedidos del éxito del pago
    notificacion = notificar_pedidos(pedido_id, "PAGADO")

    logging.info(f"Pago del pedido {pedido_id} registrado")

    return jsonify({
        "pago_id": pago_id,
        "pedido_id": pedido_id,
        "estado": estado,
        "notificacion": notificacion
    }), 201


# Obtener un pago en específico
@app.get("/pagos/<int:pago_id>")
def obtener_pago(pago_id):
    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM pagos WHERE id = ?", (pago_id,))
    fila = cursor.fetchone()
    conn.close()

    if fila is None:
        logging.warning("Pago no encontrado")
        abort(404, description="Pago no encontrado")

    logging.info(f"Pago {pago_id} encontrado")

    return jsonify({
        "id": fila["id"],
        "pedido_id": fila["pedido_id"],
        "metodo": fila["metodo"],
        "estado": fila["estado"]
    }), 200


if __name__ == "__main__":
    puerto = 5003
    app.run(port=5003, debug=True)

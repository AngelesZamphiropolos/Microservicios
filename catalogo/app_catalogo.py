from flask import Flask, request, jsonify, abort
import logging
import sqlite3

app = Flask(__name__)

# Guarda los logs en catalogos.log
logging.basicConfig(filename='catalogos.log', level=logging.INFO, filemode= 'w', format="%(asctime)s | %(levelname)s : %(message)s") 

# Token que usará el microservicio de pedidos para hablar con catálogo
TOKEN_PEDIDOS_CATALOGO = "PEDIDOS_CATALOGO"

DATABASE = "catalogo.db"

# Crea una conexión nueva a la base de datos de catálogo
def conectar_db():
    conn = sqlite3.connect(DATABASE)
    # Para poder acceder a las columnas por nombre (ej: row["descripcion"])
    conn.row_factory = sqlite3.Row
    return conn


# Verifica que el header Authorization tenga el token correcto para llamadas entre microservicios
def verificar_token_servicio():
    # Obtener la Autorización del header de la petición
    auth_header = request.headers.get("Authorization", "")
    esperado = f"Bearer {TOKEN_PEDIDOS_CATALOGO}"
    if auth_header != esperado:
        logging.warning("Token Inválido")
        # para cortar la ejecución en flask y retornar un mensaje al detectar un error
        abort(401, description="No autorizado para esta operación")


# Crea una nueva paleta en el catálogo
@app.route("/paletas", methods=["POST"])
def crear_paleta():
    # verificar token
    verificar_token_servicio()

    # datos de la pretición
    data = request.get_json() or {}

    descripcion = data.get("descripcion")
    precio = data.get("precio")
    stock = data.get("stock")

    # verificar que no falten campos
    if not descripcion or precio is None or stock is None:
        logging.warning("Faltan campos")
        abort(400, description="Faltan campos: descripcion, precio, stock")

    # conectar a la db
    conn = conectar_db()
    cursor = conn.cursor()

    # hacer una consulta
    cursor.execute(
        "INSERT INTO catalogo (descripcion, precio, stock) VALUES (?, ?, ?)",
        (descripcion, precio, stock)
    )
    conn.commit()

    # Obtener el último id insertado
    nuevo_id = cursor.lastrowid
    conn.close()

    # guardar log
    logging.info(f"Paleta creada: id={nuevo_id}")

    return jsonify({
        "id": nuevo_id,
        "descripcion": descripcion,
        "precio": precio,
        "stock": stock
    }), 201


# Devuelve la lista de todas las paletas
@app.route("/paletas", methods=["GET"])
def listar_paletas():
    # Conectar a la db
    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, descripcion, precio, stock FROM catalogo")
    filas = cursor.fetchall()

    # recorrer cada paleta de la db y agregar a una lista para luego retornarla
    paletas = []
    for fila in filas:
        paletas.append({
            "id": fila["id"],
            "descripcion": fila["descripcion"],
            "precio": fila["precio"],
            "stock": fila["stock"]
        })

    conn.close()
    logging.info(f"Listar paletas")
    return jsonify(paletas), 200


# Devuelve los datos de una paleta en específica
@app.route("/paletas/<int:paleta_id>", methods=["GET"])
def obtener_paleta(paleta_id):
    # Conectar a la db
    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, descripcion, precio, stock FROM catalogo WHERE id = ?",
        (paleta_id,)
    )

    # guardar la paleta si se encuentra
    fila = cursor.fetchone()
    conn.close()

    # si fila es none, entonces no se encontró
    if fila is None:
        logging.warning("Paleta no encontrada")
        abort(404, description="Paleta no encontrada")

    # guardar datos de la paleta en una lista para retornar
    paleta = {
        "id": fila["id"],
        "descripcion": fila["descripcion"],
        "precio": fila["precio"],
        "stock": fila["stock"]
    }
    logging.info(f"Listar paleta especifica: id={paleta_id}")
    return jsonify(paleta), 200


# Actualiza completamente una paleta
@app.route("/paletas/<int:paleta_id>", methods=["PUT"])
def actualizar_paleta(paleta_id):
    
    verificar_token_servicio()

    # datos de la peticion
    data = request.get_json() or {}

    descripcion = data.get("descripcion")
    precio = data.get("precio")
    stock = data.get("stock")

    # verificar que se encuentren todos los datos
    if not descripcion or precio is None or stock is None:
        logging.warning("Faltan campos")
        abort(400, description="Faltan campos: descripcion, precio, stock")

    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM catalogo WHERE id = ?",
        (paleta_id,)
    )
    fila = cursor.fetchone()

    # si fila es none, no existe la paleta a actualizar
    if fila is None:
        conn.close()
        logging.warning("Paleta no encontrada")
        abort(404, description="Paleta no encontrada")

    # si existe, actualiza en la db
    cursor.execute(
        "UPDATE catalogo SET descripcion = ?, precio = ?, stock = ? WHERE id = ?",
        (descripcion, precio, stock, paleta_id)
    )
    conn.commit()
    conn.close()

    logging.info(f"Paleta actualizada: id={paleta_id}")

    return jsonify({
        "id": paleta_id,
        "descripcion": descripcion,
        "precio": precio,
        "stock": stock
    }), 200


# Verifica el stock y descuenta la cantidad pedida
@app.route("/paletas/<int:paleta_id>/reservar", methods=["POST"])
def reservar_paleta(paleta_id):
   
    verificar_token_servicio()

    # datos de la petición
    data = request.get_json()
    cantidad = data.get("cantidad")

    # verificar que la cantidad sea correcta
    if cantidad is None or cantidad <= 0:
        logging.warning("Cantidad inválida")
        abort(400, description="Cantidad inválida")

    conn = conectar_db()
    cursor = conn.cursor()

    # Obtenemos la paleta actual
    cursor.execute(
        "SELECT id, descripcion, precio, stock FROM catalogo WHERE id = ?",
        (paleta_id,)
    )
    fila = cursor.fetchone()

    # si es none, no existe
    if fila is None:
        conn.close()
        logging.warning("Paleta no encontrada")
        abort(404, description="Paleta no encontrada")

    # obtener el stock actual
    stock_actual = fila["stock"]

    # verificar si la cantidad pedida no sobrepasa el stock actual
    if stock_actual < cantidad:
        conn.close()
        logging.warning("Stock insuficiente")
        abort(400, description="Stock insuficiente")

    # Actualizamos el stock
    nuevo_stock = stock_actual - cantidad

    cursor.execute(
        "UPDATE catalogo SET stock = ? WHERE id = ?",
        (nuevo_stock, paleta_id)
    )
    conn.commit()
    conn.close()

    logging.info(f"Stock reservado para paleta id={paleta_id}")

    return jsonify({
        "paleta_id": paleta_id,
        "cantidad_reservada": cantidad,
        "stock_restante": nuevo_stock
    }), 200


if __name__ == "__main__":
    puerto = 5001
    app.run(port=5001, debug=True)
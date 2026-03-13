# Conectarse a una base de datos
import sqlite3

# Abrir conexion con la base de datos, si no existe la crea
with sqlite3.connect("pedidos.db") as conexion:
    # Crear cursor (puente entre python y la base de datos)
    cursor = conexion.cursor()

    # Borra la tabla si existe
    cursor.execute("DROP TABLE IF EXISTS pedido")

    # Crea la tabla logs
    cursor.execute("""
    CREATE TABLE pedido (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id INT NOT NULL,
        estado TEXT NOT NULL,
        total INT NOT NULL
    )
    """)

    # Borra la tabla si existe
    cursor.execute("DROP TABLE IF EXISTS pedido_items")

    # Crea la tabla logs
    cursor.execute("""
    CREATE TABLE pedido_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pedido_id INT NOT NULL,
        paleta_id INT NOT NULL,
        cantidad INT NOT NULL,
        FOREIGN KEY (pedido_id) REFERENCES pedido (id)
    )
    """)

cursor.close()
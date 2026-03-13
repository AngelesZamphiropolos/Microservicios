# Conectarse a una base de datos
import sqlite3

# Abrir conexion con la base de datos, si no existe la crea
with sqlite3.connect("pagos.db") as conexion:
    # Crear cursor (puente entre python y la base de datos)
    cursor = conexion.cursor()

    # Borra la tabla si existe
    cursor.execute("DROP TABLE IF EXISTS pagos")

    # Crea la tabla logs
    cursor.execute("""
    CREATE TABLE pagos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pedido_id INT NOT NULL,
        metodo TEXT NOT NULL,
        estado TEXT NOT NULL
    )
    """)

cursor.close()
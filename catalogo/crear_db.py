# Conectarse a una base de datos
import sqlite3

# Abrir conexion con la base de datos, si no existe la crea
with sqlite3.connect("catalogo.db") as conexion:
    # Crear cursor (puente entre python y la base de datos)
    cursor = conexion.cursor()

    # Borra la tabla si existe
    cursor.execute("DROP TABLE IF EXISTS catalogo")

    # Crea la tabla logs
    cursor.execute("""
    CREATE TABLE catalogo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        descripcion TEXT NOT NULL,
        precio INT NOT NULL,
        stock INT NOT NULL
    )
    """)

cursor.close()
import mysql.connector
from mysql.connector import Error
import os
import base64
import requests
from dotenv import load_dotenv

# Carga las variables de entorno desde el archivo .env
load_dotenv()

# Configuración de conexión usando variables de entorno
config = {
    'user': os.getenv('MYSQL_USER'),          # Usuario de MySQL desde .env
    'password': os.getenv('MYSQL_PASSWORD'),  # Contraseña de MySQL desde .env
    'host': os.getenv('MYSQL_HOST'),          # Host de MySQL desde .env
    'port': os.getenv('MYSQL_PORT'),          # Puerto de MySQL desde .env
    'database': os.getenv('MYSQL_DATABASE')   # Base de datos de MySQL desde .env
}



def obtener_texto_imagen(image_path):
    # Cargar la clave API desde las variables de entorno
    api_key = os.getenv("OPENAI_API_KEY")
    
    print(api_key)

    headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
    }

    payload = {
    "model": "gpt-4o-mini",
    "messages": [
        {
        "role": "user",
        "content": [
            {
            "type": "text",
            "text": "dame los platos del menu ejecutivo de la imagen cada uno con su texto y precio, solo responde con el menu"
            },
            {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{image_path}"
            }
            }
        ]
        }
    ],
    "max_tokens": 300
    }

    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

    respuesta = response.json()
    print(respuesta)
    menu = respuesta['choices'][0]['message']['content']

    return menu

# Función para guardar el menú en la base de datos
def guardar_menu_en_db(menu_juanchito_plaza, config):
    connection = None  # Definir la variable fuera del bloque try
    try:
        # Configuración de conexión a MySQL
        connection = mysql.connector.connect(**config)

        if connection.is_connected():
            cursor = connection.cursor()

            # Inserción del menú en la tabla 'menus' (solo contenido_menu)
            cursor.execute("""
                INSERT INTO menus (contenido_menu) 
                VALUES (%s)
            """, (menu_juanchito_plaza,))  # Se pasa el parámetro como una tupla

            # Confirmar cambios
            connection.commit()
            print("Menú guardado exitosamente en la base de datos.")

    except Error as e:
        print(f"Error al guardar el menú en la base de datos: {e}")
    finally:
        if connection is not None and connection.is_connected():
            cursor.close()
            connection.close()
            print("Conexión cerrada.")

# Función para actualizar el menú
def actualizar_menu(imagen, menu_carta, config):
    # Obtener el texto de la imagen
    menu_ejecutivo = obtener_texto_imagen(imagen)

    # Combinar los menús
    menu_juanchito_plaza = menu_ejecutivo + " " + menu_carta

    # Guardar el menú combinado en la base de datos
    guardar_menu_en_db(menu_juanchito_plaza, config)
    return "Menú actualizado"


def obtener_ultimo_menu(config):

    connection = mysql.connector.connect(**config)
    
    cursor = connection.cursor()
    # Consulta SQL para obtener el contenido del menú más reciente
    query = """
        SELECT contenido_menu 
        FROM menus 
        ORDER BY fecha_actualizacion DESC 
        LIMIT 1
    """
    
    cursor.execute(query)
    resultado = cursor.fetchone()  # Obtiene la primera fila del resultado
    
    if resultado:
        return resultado[0]  # Retorna el contenido del menú
    else:
        return None  # Si no hay resultados, retorna None


if __name__ == "__main__":

    menu = """
    Aquí tienes el texto de la carta del restaurante Juancho Plaza:

    **Menú a la carta:**
    1. **Churrasco + Chorizo** - $38.000
    - 300 GRS. Sopas, Arroz, Jugo 

    2. **Salmón** - $38.000
    - 180 GRS. Sopa o crema, ensalada, Arroz, Jugo 

    3. **Mojarra Frita** - $28.000
    - 380 GRS. Sopa, Arroz, Jugo

    4. **Punta de anca de cerdo** - $27.000
    - Sopas, Arroz, Jugo, ensalada

    5. **Filete de Trucha** - $20.000
    - Sopas, Arroz, Jugo, ensalada
"""

    # Ejemplo de uso
    #image_path = "C:/Users/sebas/chat-bot/juancho_plaza/chatbot/carta_juancho_plaza.jpg"  # Reemplazar con la ruta real
    #numero = 321  # Número a verificar

    # Actualizar el menú
    #respuesta =actualizar_menu(image_path, numero, menu,config)
    #respuesta

    menu = obtener_ultimo_menu(config)
    print(menu)
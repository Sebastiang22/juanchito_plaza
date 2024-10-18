from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import mysql.connector
from chatbot_juanchito import crear_grafo
from funciones import actualizar_menu, obtener_ultimo_menu
import base64
import os
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

app = FastAPI()

# Modelo para recibir la solicitud
class ChatRequest(BaseModel):
    pregunta: str
    celular: str
    imagen: str = None  # Este campo será opcional para recibir la imagen en Base64


menu_carta = """
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

numeros_permitidos = ["573217295290"]

@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        pregunta = request.pregunta
        celular = request.celular
            
        inputs = {"pregunta": pregunta, "celular": celular}
        
        print(f"Número de celular: {celular}")

        print(f"Número de celular: {numeros_permitidos}")
        
        # Comprobar si el número está en la lista de números permitidos y si hay imagen
        if celular in numeros_permitidos and request.imagen is not None:
            try:
                print("Número permitido y imagen proporcionada.")
                
                # Decodificar la imagen de Base64
                image_data = request.imagen

                print(f"Imagen decodificada con éxito, tamaño de la imagen: {len(image_data)} bytes.")
                
                # Llamar a la función actualizar_menu si el número coincide
                menu_actualizado = actualizar_menu(image_data, menu_carta,config,)
                
                if menu_actualizado:
                    print("Menú actualizado con éxito.")
                else:
                    print("Error al actualizar el menú.")

                return menu_actualizado
            
            except Exception as image_error:
                raise HTTPException(status_code=500, detail=f"Error al procesar la imagen: {str(image_error)}")
        
        else:
            # Si el número no está permitido o no hay imagen
            print("Número no permitido o imagen no proporcionada.")
            response = crear_grafo(inputs)
            respuesta = response['respuesta']
            print(f"Respuesta del grafo: {respuesta}")
            return respuesta
    
    except Exception as e:
        print(f"Excepción: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



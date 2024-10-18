import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from typing import List, TypedDict
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.output_parsers import StrOutputParser
from datetime import datetime
import mysql.connector
from mysql.connector import Error
from langgraph.graph import END, StateGraph
from pprint import pprint
import json  # Para manejar el pedido que es un JSON
from funciones import obtener_ultimo_menu
# Carga las variables de entorno desde el archivo .env
load_dotenv()

# Usar las variables de entorno
os.getenv("LANGCHAIN_TRACING_V2")  # "true"
os.getenv("LANGCHAIN_API_KEY")   # "your-langchain-api-key"
os.getenv("OPENAI_API_KEY")      # "your-openai-api-key"
# Configuración de conexión usando variables de entorno
config = {
    'user': os.getenv('MYSQL_USER'),          # Usuario de MySQL desde .env
    'password': os.getenv('MYSQL_PASSWORD'),  # Contraseña de MySQL desde .env
    'host': os.getenv('MYSQL_HOST'),          # Host de MySQL desde .env
    'port': os.getenv('MYSQL_PORT'),          # Puerto de MySQL desde .env
    'database': os.getenv('MYSQL_DATABASE')   # Base de datos de MySQL desde .env
}
llm = ChatOpenAI(temperature=0, model_name='gpt-4o-mini')

class objeto_juancho_plaza(TypedDict):
    # Primer nodo: decisión sobre la función a realizar
    celular: str  # Número de teléfono del usuario
    pregunta: str  # Pregunta original del usuario
    decision: str  # Decisión sobre qué función ejecutar ('crear_usuario', 'consulta_sql', 'crear_pago')

    # Nodos intermedios: detalles específicos para cada función
    pedido: dict  # Contendrá detalles de un nuevo usuario (nombre, email, etc.)
    direccion: str  # Dirección de envío del pedido
    
    # Nodo final: respuesta generada
    respuesta: str  # Respuesta final del chatbot después de procesar la solicitud

prompt_decision = PromptTemplate(
    template="""<|begin_of_text|><|start_header_id|>system<|end_header_id|> 
    Eres un experto en gestionar operaciones de un sistema de pedidos de comida. Tienes tres funciones principales:
    1. 'pedido': Usar esta función si la pregunta está relacionada con tomar el pidido, el nombre del cliente o la direccion.
    2. 'confirmacion': Usar esta función si la pregunta está relacionada con confirmar un pedido o si la pregunta solo es si.
    3. 'nodo_final': Usar esta función si la pregunta no tiene que ver con las funciones anteriores.
    
    No necesitas ser estricto con las palabras clave, identifica el propósito general de la pregunta para seleccionar la opción adecuada. 
    Da una opción binaria ('pedido', 'confirmacion', 'nodo_final') basada en la pregunta. 
    Retorna un JSON con solo una clave 'funcion' sin preámbulo o explicación.

    Pregunta a enrutar: {pregunta}
    <|eot_id|><|start_header_id|>assistant<|end_header_id|>""",
    input_variables=["pregunta"],
)

prompt_pedidos = PromptTemplate(
    template=""" 
    <|begin_of_text|><|start_header_id|>system<|end_header_id|> 
    Eres un experto en gestionar pedidos para el restaurante 'Juancho Plaza'. Tu tarea principal es recibir el pedido de los clientes y estructurarlo correctamente basándote en el menú del restaurante, el cual está dividido en dos secciones: "A la carta" y "Menú ejecutivo". El menú es el siguiente:

    Menu:
    {menu}

    Tu deber es:
    1. Recibir el pedido del cliente en lenguaje natural, incluyendo su nombre y dirección.
    2. Identificar los elementos del pedido basándote en las opciones disponibles en el menú.
    3. Estructurar el pedido en un formato JSON con las claves:
    - 'nombre' (el nombre del cliente).
    - 'direccion' (la dirección del cliente).
    - 'a_la_carta' (una lista de los productos pedidos de la sección "A la carta" con su cantidad).
    - 'menu_ejecutivo' (una lista de los productos pedidos de la sección "Menú ejecutivo" con su cantidad).
    - 'extras' (una lista de extras o especificaciones adicionales si las hay).
    - 'estado_pedido' (si todos los productos están en el menú, el estado será 'pendiente para confirmacion'. Si algún producto no está en el menú, el estado será 'pedido_erroneo').
    - 'platos_no_encontrados' (una lista de los productos que no están en el menú, solo si hay productos que no se encuentran).

    El formato de cada producto en el JSON debe ser:
    {{
        "producto": "nombre del plato",
        "cantidad": cantidad pedida
    }}

    Si todos los platos mencionados están en el menú, responde con un JSON estructurado con el estado `pendiente para confirmacion` y el pedido. Si hay algún plato que no está en el menú, responde con el estado `pedido_erroneo` e incluye el o los platos que no están en el menú bajo la clave `platos_no_encontrados`.

    Solo responde con el JSON del pedido, sin agregar ninguna explicación adicional.
    
    Pedido del cliente: {pregunta}
    <|eot_id|><|start_header_id|>assistant<|end_header_id|>""",
    input_variables=["menu", "pregunta"],
)

prompt_final_nodo = PromptTemplate(
    template=""" 
    <|begin_of_text|><|start_header_id|>system<|end_header_id|> 
    Eres un asistente especializado en gestionar pedidos en un restaurante llamado Juancho Plaza. Has llegado al nodo final, y debes proporcionar una respuesta clara y precisa basada en la pregunta del cliente, los datos proporcionados y la conversación previa. Aquí tienes las variables de entrada:

    - `memoria`: {memoria} (el historial de conversación con el cliente)
    - `pregunta`: {pregunta} (la pregunta original del cliente)
    - `pedido`: {pedido} (respuesta relacionada con la toma de un nuevo pedido)
    - `direccion`: {direccion} (direccion relacionada con el pedido)
    - `estado_pedido`: {estado_pedido} (estado del pedido, indicando si es correcto o erróneo)
    - `platos_no_encontrados`: {platos_no_encontrados} (platos que no se encontraron en el menú)
    - `menu` : {menu}(menu actulizado)
    Basándote en la memoria de la conversación y en las variables proporcionadas, responde de acuerdo a la función que se haya ejecutado:

    1. Si la variable `estado_pedido` es "pedido_erroneo":
        - Responde amablemente que los siguientes platos no están en el menú:
          - **Platos no encontrados:**
            - {platos_no_encontrados}
        - Pide al cliente que elija otros platos del menú.

    2. Si la variable `estado_pedido` es "pendiente para confirmacion":
        - Tu pedido es el siguiente:
          - **Pedido:**
            - {pedido}
          - **Dirección:**
            - {direccion}
        - Pide que confirme el pedido con un "sí".

    2. Si la variable `estado_pedido` es "confirmado":
        - Formula una respuesta confirmando que ha sido correctamente registrado o esta en proceso de preparacion.

    4. Si la pregunta no está relacionada con el pedido, la confirmación o los platos:
        - Responde textualmente: "Hola 😊, soy el *chatbot de Juanchito Plaza*, puedo ayudar con la toma de tu pedido. Tenemos domicilios disponibles solo en la *zona industrial Maltería*, desde el *Bosque Popular* hasta *Oncólogos*. Recibimos pedidos hasta las *11 a.m*. Proporciona tu nombre, dirección y los platos del menú que desees."

    5.Si la pregunta esta relacionada con el menu, devulve el menu
    Ajusta la respuesta para que sea clara, directa y sin información innecesaria.

    <|eot_id|><|start_header_id|>assistant<|end_header_id|>
    """,
    input_variables=["memoria", "pregunta", "pedido", "direccion", "estado_pedido", "platos_no_encontrados","menu"]
)


def enrutador_decision(state):
    print('---- Pasaje por el enrutador_decision ----')
    
    
    pregunta = state["pregunta"]
    celular = state["celular"]
    print(celular)
    
    cadena_decision = prompt_decision | llm | JsonOutputParser()

    # Lógica de decisión utilizando cadena_decision 
    decision = cadena_decision.invoke({"pregunta": pregunta})
    print("decision: ", decision)
    funcion = decision['funcion']
    
    try:
        # Conectar a la base de datos
        connection = mysql.connector.connect(**config)
        cursor = connection.cursor()

        # Verificar si el número de celular ya existe en la base de datos
        query_check_celular = "SELECT * FROM clientes WHERE telefono = %s"
        cursor.execute(query_check_celular, (celular,))
        resultado = cursor.fetchone()

        if not resultado:
            # Si no existe, insertar un nuevo cliente
            query_insert_cliente = "INSERT INTO clientes (telefono) VALUES (%s)"
            cursor.execute(query_insert_cliente, (celular,))
            connection.commit()
            print(f"Nuevo cliente creado con el número {celular}.")
        else:
            print(f"El cliente con el número {celular} ya existe.")

        # Ruta de decisión
        if funcion == 'pedido':
            return "pedido"
        elif funcion == 'confirmacion':
            return "confirmacion"
        elif funcion == 'nodo_final':
            return "nodo_final"
        
    except Error as e:
        print(f"Error al conectarse a la base de datos: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            print("Conexión a la base de datos cerrada.")

def nodo_pedido(state):
    print('---- nodo_pedido ----')

    # Obtener la pregunta y el celular del estado
    pregunta = state["pregunta"] 
    celular = state["celular"]

    menu = obtener_ultimo_menu(config)

    inputs = {
        "pregunta": pregunta,
        "menu": menu
    }
    cadena_pedidos = prompt_pedidos | llm | JsonOutputParser()

    pedido = cadena_pedidos.invoke(inputs)
    print('Pedido generado:', pedido)


    # Extraer el nombre y la dirección del JSON del pedido
    nombre_cliente = pedido['nombre']
    print('Nombre del cliente:', nombre_cliente)
    direccion_cliente = pedido['direccion']
    print('Dirección del cliente:', direccion_cliente)

    pedido_final = {
        "a_la_carta": pedido['a_la_carta'] if pedido['a_la_carta'] else [],  # Lista de platos de la carta o lista vacía
        "menu_ejecutivo": pedido['menu_ejecutivo'] if pedido['menu_ejecutivo'] else [],  # Lista de platos del menú ejecutivo o lista vacía
        "extras": pedido['extras'] if pedido['extras'] else []  # Lista de extras o lista vacía
    }

    # Convierte el pedido_final a una cadena JSON
    pedido_final_json = json.dumps(pedido_final)

    try:
        # Conectar a la base de datos
        connection = mysql.connector.connect(**config)
        cursor = connection.cursor()

        # Verificar si el cliente ya existe
        query_check_celular = "SELECT id, nombre FROM clientes WHERE telefono = %s"
        cursor.execute(query_check_celular, (celular,))
        cliente = cursor.fetchone()

        if cliente:
            cliente_id, nombre_existente = cliente
            print(cliente)
        else:
            print("Cliente no encontrado.")
        cliente_id = cliente[0]
        print(cliente)

        cliente_id, nombre_existente = cliente

        if nombre_existente != nombre_cliente:
            print(f"Actualizando el nombre del cliente con número {celular}.")
            cursor.execute("UPDATE clientes SET nombre = %s WHERE id = %s", (nombre_cliente, cliente_id))
            connection.commit()


        # Guardar el pedido en la tabla pedidos
        query_insert_pedido = """
            INSERT INTO pedidos (cliente_id, pedido_json, direccion, pedido_cofirmado) 
            VALUES (%s, %s, %s, %s)
        """
        # Aquí asumimos que la confirmación inicial es False
        confirmacion_pedido = False  # Por defecto, el pedido no está confirmado
        cursor.execute(query_insert_pedido, (cliente_id, pedido_final_json, direccion_cliente, confirmacion_pedido))
        connection.commit()

        print(f"Pedido guardado para el cliente con ID {cliente_id}")

    except Error as e:
        print(f"Error al interactuar con la base de datos: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            print("Conexión a MySQL cerrada.")

    return {"pedido": pedido, "pregunta": pregunta, "confirmacion": "no","direccion":direccion_cliente}

def nodo_confirmacion(state):
    print('---- nodo_confirmacion ----')

    # Obtener el celular del cliente desde el estado
    celular = state["celular"]
    confirmacion = True
    # Inicializar el diccionario de pedido con el estado del pedido
    pedido = {"estado_pedido": "confirmado"}  # Aquí defines el estado del pedido

    try:
        # Conectar a la base de datos
        connection = mysql.connector.connect(**config)
        cursor = connection.cursor()

        # Verificar si el cliente existe
        query_check_celular = "SELECT id FROM clientes WHERE telefono = %s"
        cursor.execute(query_check_celular, (celular,))
        cliente = cursor.fetchone()

        if cliente:
            cliente_id = cliente[0]

            # Obtener el último pedido registrado por el cliente
            query_get_last_order = """
                SELECT id FROM pedidos
                WHERE cliente_id = %s
                ORDER BY id DESC
                LIMIT 1
            """
            cursor.execute(query_get_last_order, (cliente_id,))
            last_order = cursor.fetchone()

            if last_order:
                last_order_id = last_order[0]

                # Actualizar la columna de confirmación en el último pedido
                query_update_confirmacion = """
                    UPDATE pedidos
                    SET pedido_cofirmado = %s
                    WHERE id = %s
                """
                cursor.execute(query_update_confirmacion, (confirmacion, last_order_id))
                connection.commit()

                print(f"Confirmación actualizada para el último pedido con ID {last_order_id}.")
            else:
                print("No se encontraron pedidos para el cliente.")

        else:
            print("Cliente no encontrado.")

    except Error as e:
        print(f"Error al interactuar con la base de datos: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            print("Conexión a MySQL cerrada.")

    # Retornar todas las variables necesarias para el flujo
    return {
        "pedido": pedido,      # Asegúrate de que 'pedido' esté en el estado
    }

def nodo_final(state):
    print('---- Pasaje por el nodo final ----')

    # Obtener las variables del estado, o asignar None si no están presentes
    pregunta = state.get('pregunta', None)
    respuesta_pedidos = state.get('pedido', None)
    celular = state.get('celular', None)  # Número de celular para identificar al cliente

    # Verifica si respuesta_pedidos es None antes de acceder a sus claves
    if respuesta_pedidos is not None:
        nombre_cliente = respuesta_pedidos.get("nombre", None)
        direccion = respuesta_pedidos.get("direccion", None)
        a_la_carta = respuesta_pedidos.get("a_la_carta", None)
        menu_ejecutivo = respuesta_pedidos.get("menu_ejecutivo", None)
        extras = respuesta_pedidos.get("extras", None)
        estado_pedido = respuesta_pedidos.get("estado_pedido", None)
        platos_no_encontrados = respuesta_pedidos.get("platos_no_encontrados", None)
    else:
        # Manejar el caso en que respuesta_pedidos es None
        nombre_cliente = None
        direccion = None
        a_la_carta = None
        menu_ejecutivo = None
        extras = None
        estado_pedido = None
        platos_no_encontrados = None


        # Crear el diccionario con las variables
    pedido = {
        "nombre": nombre_cliente,
        "direccion": direccion,
        "a_la_carta": a_la_carta,
        "menu_ejecutivo": menu_ejecutivo,
        "extras": extras
    }
    try:
        connection = mysql.connector.connect(**config)
        cursor = connection.cursor()

        # Verificar si el cliente ya está en la base de datos, si no, agregarlo
        query_check_celular = "SELECT id FROM clientes WHERE telefono = %s"
        cursor.execute(query_check_celular, (celular,))
        cliente = cursor.fetchone()
        
        if cliente:
            cliente_id = cliente[0]

            # Recuperar la última conversación del cliente
            query_get_last_conversacion = """
                SELECT mensaje_cliente_chatbot 
                FROM conversaciones_chatbot 
                WHERE cliente_id = %s 
                ORDER BY fecha_conversacion DESC 
                LIMIT 1
            """
            cursor.execute(query_get_last_conversacion, (cliente_id,))
            ultima_conversacion = cursor.fetchone()

            if ultima_conversacion:
                memoria = ultima_conversacion[0]
                print(f"Última conversación del cliente {cliente_id}: {memoria}")
            else:
                memoria = "No previous conversation found."
                print(f"No se encontró conversación previa para el cliente {cliente_id}.")
        else:
            memoria = "New customer, no conversation history."
            print(f"Cliente con el número {celular} no encontrado, es un nuevo cliente.")
            # Insertar al nuevo cliente en la tabla
            query_insert_cliente = "INSERT INTO clientes (telefono) VALUES (%s)"
            cursor.execute(query_insert_cliente, (celular,))
            connection.commit()
            cliente_id = cursor.lastrowid  # Obtener el nuevo ID del cliente

        menu = obtener_ultimo_menu(config)

        # Crear el input para el modelo con la memoria de conversación y la pregunta actual
        inputs = {
            "pregunta": pregunta,
            "pedido": pedido,
            "memoria": memoria,  # Añadimos la memoria de la conversación previa
            "direccion": direccion,
            "estado_pedido": estado_pedido,
            "platos_no_encontrados": platos_no_encontrados,
            "direccion": direccion,
            "menu": menu

        }
        
        cadena_final_nodo = prompt_final_nodo | llm | StrOutputParser()

        # Generar respuesta utilizando la memoria y la pregunta actual
        response = cadena_final_nodo.invoke(inputs)
        print(f'---- Respuesta generada: {response} ----')

        # Insertar la conversación actual en la base de datos
        query_insert_conversacion = """
            INSERT INTO conversaciones_chatbot (cliente_id, mensaje_cliente_chatbot) 
            VALUES (%s, %s)
        """
        cursor.execute(query_insert_conversacion, (cliente_id, f"Cliente: {pregunta} | Chatbot: {response}"))
        connection.commit()

        print(f"Conversación guardada para el cliente con ID {cliente_id}.")

    except Error as e:
        print(f"Error al interactuar con la base de datos: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            print("Conexión a la base de datos cerrada.")

    return {'respuesta': response}

def crear_grafo(inputs):
    # Crear un nuevo objeto StateGraph
    workflow = StateGraph(objeto_juancho_plaza)

    workflow.add_node("nodo_pedido", nodo_pedido) 
    workflow.add_node("nodo_confirmacion", nodo_confirmacion) 
    workflow.add_node("nodo_final", nodo_final) 


    workflow.set_conditional_entry_point(
        enrutador_decision,
        {
            "pedido": "nodo_pedido",
            "confirmacion": "nodo_confirmacion",
            "nodo_final": "nodo_final",
        },
    )

    # Agregar bordes directos a 'nodo_final' desde los nodos específicos
    workflow.add_edge("nodo_pedido", "nodo_final")
    workflow.add_edge("nodo_confirmacion", "nodo_final")

    # Compilar el gráfico después de agregar todos los nodos y bordes
    app = workflow.compile()

    try:
        # Ejecutar el flujo de trabajo
        for output in app.stream(inputs):
            for key, value in output.items():
                pprint(f"Finished running: {key}: {value}")
    except Exception as e:
        # Captura cualquier excepción que ocurra y muestra el mensaje de error
        print(f"An unexpected error occurred: {e}")

    return value

if __name__ == "__main__":

    inputs = {"pregunta": """hola""",
                "celular": 321}
    value = crear_grafo(inputs)
    print(value['respuesta'])
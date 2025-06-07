from kafka import KafkaProducer, KafkaConsumer, errors
import os
import json
import logging
import threading
import time
import requests

# Configuración
HOST = os.getenv('CENTRAL_HOST', '0.0.0.0')
PORT = int(os.getenv('CENTRAL_PORT', '8443'))
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'kafka:9092')
REGISTRY_HOST = os.getenv('REGISTRY_HOST', 'registry')
REGISTRY_PORT = os.getenv('REGISTRY_PORT', '5000')
REGISTRY_URL = f"https://{REGISTRY_HOST}:{REGISTRY_PORT}"
logging.basicConfig(filename='logs/central.log', level=logging.INFO, format='%(asctime)s - %(message)s')

def wait_for_kafka(bootstrap_servers, retries=10, delay=5):
    """
    Espera a que Kafka esté disponible antes de proceder.
    
    :param bootstrap_servers: Dirección del broker de Kafka.
    :param retries: Número de reintentos antes de fallar.
    :param delay: Tiempo (en segundos) entre reintentos.
    """
    for attempt in range(retries):
        try:
            producer = KafkaProducer(bootstrap_servers=bootstrap_servers)
            producer.close()  # Verifica la conexión y cierra
            print("Kafka está disponible.")
            logging.info("Kafka is available.")
            return
        except errors.NoBrokersAvailable:
            print(f"Kafka no disponible. Reintentando en {delay} segundos... (Intento {attempt + 1}/{retries})")
            logging.warning(f"Kafka not available. Retrying in {delay} seconds... (Attempt {attempt + 1}/{retries})")
            time.sleep(delay)
    raise Exception("Kafka no está disponible después de múltiples reintentos.")

# Esperar a Kafka
wait_for_kafka(bootstrap_servers=KAFKA_BROKER)

# Inicializar Kafka
producer = KafkaProducer(bootstrap_servers=KAFKA_BROKER, value_serializer=lambda v: json.dumps(v).encode('utf-8'))
consumer = KafkaConsumer('TAXI_POSITIONS', 'CUSTOMER_REQUESTS', bootstrap_servers=KAFKA_BROKER, value_deserializer=lambda v: json.loads(v.decode('utf-8')))

# Mapa y registros
MAP_SIZE = 20
city_map = [[' ' for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]
taxis = {}  # Registro de taxis conectados
clients = {}  # Solicitudes activas

def taxi_is_registered(taxi_id):
    try:
        url = f"{REGISTRY_URL}/registered/{taxi_id}"
        resp = requests.get(url, verify=False)
        if resp.status_code == 200:
            return resp.json().get('registered', False)
    except Exception as e:
        logging.error(f"Error contacting registry: {e}")
    return False

def update_map():
    for x in range(MAP_SIZE):
        for y in range(MAP_SIZE):
            city_map[x][y] = ' '

    for taxi_id, data in taxis.items():
        # Aquí 'position' ahora es (pos_x, pos_y)
        x, y = data['position']  # Esto desempaqueta la tupla (3, 4)
        city_map[x][y] = str(taxi_id)
    logging.info("Map updated")

def process_taxi_message(message):
    taxi_id = message['taxi_id']
    if not taxi_is_registered(taxi_id):
        logging.warning(f"Taxi {taxi_id} not registered. Ignoring message")
        return
    pos_x = message['position']['x']
    pos_y = message['position']['y']

    # Validar y clamplear al rango [0, MAP_SIZE - 1]
    if not (0 <= pos_x < MAP_SIZE and 0 <= pos_y < MAP_SIZE):
        logging.warning(
            f"Taxi {taxi_id} reportó posición fuera de rango: ({pos_x}, {pos_y}). "
            f"Map size = {MAP_SIZE}x{MAP_SIZE}. Ignorando..."
        )
        # ajusta pos_x, pos_y
        pos_x = max(0, min(pos_x, MAP_SIZE - 1))
        pos_y = max(0, min(pos_y, MAP_SIZE - 1))

    # Si está en rango, continuar con la lógica normal.
    taxis[taxi_id] = {
        "position": (pos_x, pos_y),
        "available": message['available']
    }
    update_map()
    logging.info(f"Taxi {taxi_id} updated: {taxis[taxi_id]}")

def process_customer_message(message):
    """Procesar solicitudes de clientes."""
    client_id = message['client_id']
    pickup = message['pickup_location']
    final_destination = message.get('destination')
    clients[client_id] = {
        "pickup_location": pickup,
        "destination": final_destination,
    }

    # Asignar taxi
    assigned_taxi = None
    for taxi_id, details in taxis.items():
        if details['available']:
            assigned_taxi = taxi_id
            taxis[taxi_id]['available'] = False
            break
    if assigned_taxi:
        response = {
            "client_id": client_id,
            "taxi_id": assigned_taxi,
            "pickup_location": pickup,
            "destination": final_destination,
        }
        producer.send('TAXI_ASSIGNMENTS', response)
        logging.info(f"Assigned Taxi {assigned_taxi} to Client {client_id}")
    else:
        logging.info(f"No taxis available for Client {client_id}")

def kafka_listener():
    """Escuchar mensajes en Kafka."""
    for message in consumer:
        topic = message.topic
        if topic == 'TAXI_POSITIONS':
            process_taxi_message(message.value)
        elif topic == 'CUSTOMER_REQUESTS':
            process_customer_message(message.value)

def start_server():
    """Iniciar el servidor Central."""
    logging.info("Central server started")
    kafka_listener()

if __name__ == "__main__":
    threading.Thread(target=start_server).start()

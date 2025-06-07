from kafka import KafkaProducer, KafkaConsumer, errors
import os
import json
import time
import requests
from cryptography.fernet import Fernet, InvalidToken

# Variables de entorno
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'kafka:9092')
TAXI_ID = os.getenv('TAXI_ID', '101')
TAXI_KEY = os.getenv('TAXI_KEY')
REGISTRY_HOST = os.getenv('REGISTRY_HOST', 'registry')
REGISTRY_PORT = os.getenv('REGISTRY_PORT', '5000')
REGISTRY_URL = f"https://{REGISTRY_HOST}:{REGISTRY_PORT}"

def wait_for_kafka(bootstrap_servers, retries=20, delay=5):
    """
    Espera a que Kafka esté disponible antes de proceder.
    
    :param bootstrap_servers: Dirección del broker de Kafka.
    :param retries: Número de reintentos antes de fallar.
    :param delay: Tiempo (en segundos) entre reintentos.
    """
    for attempt in range(retries):
        try:
            producer = KafkaProducer(bootstrap_servers=bootstrap_servers)
            producer.close()  # Verificar conexión y cerrar
            print("Kafka está disponible.")
            return
        except errors.NoBrokersAvailable:
            print(f"Kafka no disponible. Reintentando en {delay} segundos... (Intento {attempt + 1}/{retries})")
            time.sleep(delay)
    raise Exception("Kafka no está disponible después de múltiples reintentos.")

# Esperar a Kafka
wait_for_kafka(bootstrap_servers=KAFKA_BROKER)

# Inicializar cifrado
fernet = Fernet(TAXI_KEY.encode()) if TAXI_KEY else None

# Inicializar productor y consumidor
producer = KafkaProducer(bootstrap_servers=KAFKA_BROKER, value_serializer=lambda v: json.dumps(v).encode('utf-8'))
consumer = KafkaConsumer(
    'TAXI_ASSIGNMENTS',
    bootstrap_servers=KAFKA_BROKER,
    value_deserializer=lambda v: json.loads(v.decode('utf-8'))
)

def register_with_registry():
    try:
        requests.post(f"{REGISTRY_URL}/register", json={"taxi_id": TAXI_ID}, verify=False)
    except Exception as e:
        print(f"Failed to register taxi: {e}")

# Estado inicial del taxi
taxi_state = {
    "taxi_id": TAXI_ID,
    "position": {"x": 0, "y": 0},
    "available": True
}

def send_state():
    """Enviar el estado cifrado al tópico de posiciones."""
    if not fernet:
        payload = taxi_state
    else:
        encrypted = fernet.encrypt(json.dumps(taxi_state).encode()).decode()
        payload = {"taxi_id": TAXI_ID, "payload": encrypted}
    producer.send('TAXI_POSITIONS', payload)

def update_position(destination):
    """Simular movimiento hacia un destino."""
    while taxi_state["position"] != destination:
        if taxi_state["position"]["x"] < destination["x"]:
            taxi_state["position"]["x"] += 1
        elif taxi_state["position"]["x"] > destination["x"]:
            taxi_state["position"]["x"] -= 1

        if taxi_state["position"]["y"] < destination["y"]:
            taxi_state["position"]["y"] += 1
        elif taxi_state["position"]["y"] > destination["y"]:
            taxi_state["position"]["y"] -= 1

        # Publicar posición actualizada
        send_state()
        print(f"Taxi {TAXI_ID} movido a {taxi_state['position']}")
        time.sleep(1)

def listen_for_assignments():
    """Escuchar asignaciones del Central."""
    for message in consumer:
        assignment = message.value
        if assignment["taxi_id"] == TAXI_ID:
            print(f"Asignación recibida: {assignment}")
            pickup = assignment["pickup_location"]
            final_dest = assignment.get("destination")
            taxi_state["available"] = False
            send_state()
            update_position(pickup)
            if final_dest:
                update_position(final_dest)
            taxi_state["available"] = True  # Liberar taxi al terminar
            send_state()

if __name__ == "__main__":
    register_with_registry()
    # Publicar estado inicial
    send_state()
    listen_for_assignments()

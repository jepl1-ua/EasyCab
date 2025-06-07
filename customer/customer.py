from kafka import KafkaProducer, KafkaConsumer, errors
import os
import json
import time

# Variables de entorno
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'kafka:9092')
CLIENT_ID = os.getenv('CLIENT_ID', '1')

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

# Inicializar productor y consumidor
producer = KafkaProducer(bootstrap_servers=KAFKA_BROKER, value_serializer=lambda v: json.dumps(v).encode('utf-8'))
consumer = KafkaConsumer(
    'TAXI_ASSIGNMENTS',
    bootstrap_servers=KAFKA_BROKER,
    value_deserializer=lambda v: json.loads(v.decode('utf-8'))
)

def send_requests_from_file(filename):
    """Leer solicitudes de un archivo y enviarlas al Central."""
    try:
        with open(filename, 'r') as f:
            requests = json.load(f)
            for request in requests:
                request["client_id"] = CLIENT_ID
                producer.send('CUSTOMER_REQUESTS', request)
                print(f"Cliente {CLIENT_ID} envió solicitud: {request}")
                time.sleep(4)  # Esperar 4 segundos entre solicitudes
    except Exception as e:
        print(f"Error leyendo archivo: {e}")

def listen_for_assignments():
    """Escuchar asignaciones de taxis en Kafka."""
    for message in consumer:
        assignment = message.value
        if assignment["client_id"] == CLIENT_ID:
            pickup = assignment.get("pickup_location")
            final_dest = assignment.get("destination")
            print(
                f"Asignación recibida: Taxi {assignment['taxi_id']} "
                f"recogerá en {pickup} y llevará a {final_dest}"
            )

if __name__ == "__main__":
    print(f"Cliente {CLIENT_ID} iniciado...")
    send_requests_from_file('requests.json')
    listen_for_assignments()

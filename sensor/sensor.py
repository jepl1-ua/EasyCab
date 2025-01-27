from kafka import KafkaProducer, errors
import os
import json
import time
import random

# Leer variables de entorno
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'kafka:9092')
TAXI_ID = os.getenv('TAXI_ID', '101')

def wait_for_kafka(bootstrap_servers, retries=20, delay=5):
    """
    Espera a que Kafka esté disponible antes de proceder.
    
    :param bootstrap_servers: Dirección del broker de Kafka.
    :param retries: Número de reintentos antes de fallar.
    :param delay: Tiempo (en segundos) entre reintentos.
    """
    for attempt in range(retries):
        try:
            # Intentar conectarse a Kafka
            producer = KafkaProducer(bootstrap_servers=bootstrap_servers)
            producer.close()  # Cierra la conexión tras verificarla
            print("Kafka está disponible.")
            return
        except errors.NoBrokersAvailable:
            print(f"Kafka no disponible. Reintentando en {delay} segundos... (Intento {attempt + 1}/{retries})")
            time.sleep(delay)
    raise Exception("Kafka no está disponible después de múltiples reintentos.")

# Esperar a que Kafka esté listo
wait_for_kafka(bootstrap_servers=KAFKA_BROKER)

# Inicializar el KafkaProducer tras verificar que Kafka está disponible
producer = KafkaProducer(bootstrap_servers=KAFKA_BROKER, value_serializer=lambda v: json.dumps(v).encode('utf-8'))

# Lógica del productor (puedes añadir tu lógica de negocio aquí)
def send_sensor_status():
    """Enviar mensajes simulados desde un sensor."""
    while True:
        status = random.choice(["OK", "KO"])  # Simula mensajes OK/KO
        message = {
            "taxi_id": TAXI_ID,
            "status": status
        }
        producer.send('TAXI_SENSOR_STATUS', message)
        print(f"Sensor del taxi {TAXI_ID} envió estado: {status}")
        time.sleep(5)

if __name__ == "__main__":
    send_sensor_status()

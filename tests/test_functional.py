import os
import time
from kafka import KafkaConsumer, KafkaProducer

KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'kafka:9092')

def test_functional():
    producer = KafkaProducer(bootstrap_servers=KAFKA_BROKER, value_serializer=lambda v: json.dumps(v).encode('utf-8'))
    consumer = KafkaConsumer('TAXI_ASSIGNMENTS', bootstrap_servers=KAFKA_BROKER, value_deserializer=lambda v: json.loads(v.decode('utf-8')))

    # Enviar solicitud de cliente
    client_request = {"client_id": 1, "pickup_location": {"x": 5, "y": 5}}
    producer.send('CUSTOMER_REQUESTS', client_request)
    print("Client request sent")

    # Esperar asignación
    for message in consumer:
        print(f"Assignment received: {message.value}")
        break

if __name__ == "__main__":
    test_functional()

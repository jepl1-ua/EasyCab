import os
import json
import pytest

try:
    from kafka import KafkaConsumer, KafkaProducer, errors
except Exception:  # pragma: no cover - kafka not installed
    KafkaConsumer = None
    KafkaProducer = None
    errors = None

KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'kafka:9092')


def kafka_available():
    """Check if a Kafka broker is reachable."""
    if KafkaProducer is None:
        return False
    try:
        producer = KafkaProducer(bootstrap_servers=KAFKA_BROKER)
        producer.close()
        return True
    except Exception:
        return False

@pytest.mark.skipif(not kafka_available(), reason="Kafka broker not available")
def test_functional():
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BROKER,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    consumer = KafkaConsumer(
        "TAXI_ASSIGNMENTS",
        bootstrap_servers=KAFKA_BROKER,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )

    # Enviar solicitud de cliente
    client_request = {
        "client_id": 1,
        "pickup_location": {"x": 5, "y": 5},
        "destination": {"x": 1, "y": 1},
    }
    producer.send('CUSTOMER_REQUESTS', client_request)
    print("Client request sent")

    # Esperar asignación
    for message in consumer:
        print(f"Assignment received: {message.value}")
        break

if __name__ == "__main__":
    test_functional()

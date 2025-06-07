import os
import json
import time
import threading
from kafka import KafkaProducer

KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'kafka:9092')
TAXI_ID = os.getenv('TAXI_ID', '101')
SENSOR_INTERVAL = float(os.getenv('SENSOR_INTERVAL', '1'))

# Flag to inject failure
failure = False

# Initialize Kafka producer
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKER,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)


def input_loop():
    """Listen for user input to toggle failure state."""
    global failure
    while True:
        cmd = input("Press 'f' to toggle failure (current: %s): " % ("KO" if failure else "OK")).strip().lower()
        if cmd == 'f':
            failure = not failure


def send_sensor_status():
    """Send sensor status to the Digital Engine every second."""
    while True:
        status = 'KO' if failure else 'OK'
        payload = {"taxi_id": TAXI_ID, "status": status}
        try:
            producer.send('TAXI_SENSOR_STATUS', payload)
            print(f"Sensor {TAXI_ID} sent status: {status}")
        except Exception as exc:
            print(f"Failed to send status: {exc}")
        time.sleep(SENSOR_INTERVAL)


if __name__ == '__main__':
    threading.Thread(target=input_loop, daemon=True).start()
    send_sensor_status()

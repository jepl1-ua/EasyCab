import os
import json
import time
import threading
import requests

DE_HOST = os.getenv('DE_HOST', 'taxi')
DE_PORT = int(os.getenv('DE_PORT', '9000'))
TAXI_ID = os.getenv('TAXI_ID', '101')
SENSOR_INTERVAL = float(os.getenv('SENSOR_INTERVAL', '1'))

# Flag to inject failure
failure = False


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
            requests.post(
                f"http://{DE_HOST}:{DE_PORT}/status",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=1,
            )
            print(f"Sensor {TAXI_ID} sent status: {status}")
        except Exception as exc:
            print(f"Failed to send status: {exc}")
        time.sleep(SENSOR_INTERVAL)


if __name__ == '__main__':
    threading.Thread(target=input_loop, daemon=True).start()
    send_sensor_status()

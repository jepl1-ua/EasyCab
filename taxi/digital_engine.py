import socket
import requests
import json
import time
import threading
from cryptography.fernet import Fernet, InvalidToken

# Configuration values (can be overridden via env vars)
import os

TAXI_ID = os.getenv("TAXI_ID", "123")
CENTRAL_HOST = os.getenv("CENTRAL_HOST", "central")
CENTRAL_PORT = int(os.getenv("CENTRAL_PORT", "8443"))
REGISTRY_HOST = os.getenv("REGISTRY_HOST", "registry")
REGISTRY_PORT = os.getenv("REGISTRY_PORT", "5000")
REGISTRY_URL = f"https://{REGISTRY_HOST}:{REGISTRY_PORT}"
SENSOR_INTERVAL = float(os.getenv("SENSOR_INTERVAL", "1"))
CIFRA_KEY = os.getenv("CIFRA_KEY", None)
BASE_X = int(os.getenv("BASE_X", "0"))
BASE_Y = int(os.getenv("BASE_Y", "0"))
SENSOR_SERVER_PORT = int(os.getenv("SENSOR_SERVER_PORT", "9000"))

if CIFRA_KEY is None:
    # Generate random key if not provided
    CIFRA_KEY = Fernet.generate_key()
else:
    CIFRA_KEY = CIFRA_KEY.encode()

fernet = Fernet(CIFRA_KEY)

# Sensor server state
sensor_status = "OK"

def update_sensor_status(status: str) -> None:
    """Update the last received sensor status."""
    global sensor_status
    sensor_status = status

from http.server import BaseHTTPRequestHandler, HTTPServer

class SensorHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/status":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length)
        try:
            payload = json.loads(data.decode())
            update_sensor_status(payload.get("status", "OK"))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        except Exception:
            self.send_response(400)
            self.end_headers()

    def log_message(self, *args, **kwargs):
        # Silence default logging
        return

def start_sensor_server():
    server = HTTPServer(('', SENSOR_SERVER_PORT), SensorHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Sensor server listening on port {SENSOR_SERVER_PORT}")
    return server

# State
posicion_actual = {"x": 0, "y": 0}
BASE = {"x": BASE_X, "y": BASE_Y}
stop_event = threading.Event()

def obtener_sensor():
    """Return the latest sensor status received."""
    return sensor_status

def obtener_trafico():
    """Simulate traffic status from CTC."""
    return "OK"

def avanzar_un_paso(dest):
    """Move one step towards dest."""
    if posicion_actual["x"] < dest["x"]:
        posicion_actual["x"] += 1
    elif posicion_actual["x"] > dest["x"]:
        posicion_actual["x"] -= 1

    if posicion_actual["y"] < dest["y"]:
        posicion_actual["y"] += 1
    elif posicion_actual["y"] > dest["y"]:
        posicion_actual["y"] -= 1

def registrar():
    try:
        requests.post(f"{REGISTRY_URL}/register", json={"taxi_id": TAXI_ID}, verify=False)
    except Exception:
        pass

def desregistrar():
    try:
        requests.delete(f"{REGISTRY_URL}/unregister/{TAXI_ID}", verify=False)
    except Exception:
        pass

def conectar_socket():
    return socket.create_connection((CENTRAL_HOST, CENTRAL_PORT))

def autenticar(sock):
    sock.sendall(json.dumps({"taxi_id": TAXI_ID}).encode())
    data = sock.recv(1024)
    token = json.loads(data.decode()).get("token")
    return token

def enviar_mensaje(sock, token, payload):
    """Send an encrypted payload including the taxi id."""
    payload_with_id = {"taxi_id": TAXI_ID, **payload}
    try:
        encrypted = fernet.encrypt(json.dumps(payload_with_id).encode())
    except Exception as e:
        print(f"Error al cifrar: {e}")
        return
    mensaje = json.dumps({"token": token, "payload": encrypted.decode()})
    sock.sendall(mensaje.encode())

def leer_sensor(sock, token):
    while not stop_event.is_set():
        estado = obtener_sensor()
        enviar_mensaje(sock, token, {"status": estado})
        if estado == "KO":
            print("Sensor KO. Deteniendo taxi.")
            stop_event.set()
            break
        time.sleep(SENSOR_INTERVAL)

def mover_hacia(sock, token, destino):
    while not stop_event.is_set() and posicion_actual != destino:
        if obtener_trafico() == "KO":
            print("Tráfico KO. Deteniendo taxi.")
            stop_event.set()
            break
        if obtener_sensor() == "KO":
            print("Sensor KO. Deteniendo taxi.")
            stop_event.set()
            break
        avanzar_un_paso(destino)
        enviar_mensaje(sock, token, {"position": posicion_actual})
        time.sleep(1)

def procesar_comandos(sock, token):
    while not stop_event.is_set():
        datos = sock.recv(1024)
        if not datos:
            break
        try:
            mensaje = json.loads(datos.decode())
            if mensaje.get("token") != token:
                continue
            try:
                contenido = json.loads(fernet.decrypt(mensaje["payload"].encode()).decode())
            except InvalidToken:
                print("Clave de cifrado incorrecta o mensaje corrupto")
                continue
            comando = contenido.get("command")
            if comando == "move":
                destino = contenido.get("destination") or BASE
                mover_hacia(sock, token, destino)
            elif comando == "return_to_base":
                mover_hacia(sock, token, BASE)
            elif comando == "stop":
                stop_event.set()
        except Exception:
            continue

def main():
    registrar()
    start_sensor_server()
    sock = conectar_socket()
    token = autenticar(sock)
    sensor_thread = threading.Thread(target=leer_sensor, args=(sock, token), daemon=True)
    sensor_thread.start()
    try:
        procesar_comandos(sock, token)
    finally:
        desregistrar()
        sock.close()

if __name__ == "__main__":
    main()

from kafka import KafkaProducer, KafkaConsumer, errors
import os
import json
import logging
import threading
import time
import requests
import uuid
import sys
from cryptography.fernet import Fernet, InvalidToken
from flask import Flask, jsonify

# EC_CTC configuration
CTC_HOST = os.getenv('CTC_HOST', 'ctc')
CTC_PORT = os.getenv('CTC_PORT', '8080')
CTC_URL = f"http://{CTC_HOST}:{CTC_PORT}/traffic"

# Configuración
HOST = os.getenv('CENTRAL_HOST', '0.0.0.0')
PORT = int(os.getenv('CENTRAL_PORT', '8443'))
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'kafka:9092')
REGISTRY_HOST = os.getenv('REGISTRY_HOST', 'registry')
REGISTRY_PORT = os.getenv('REGISTRY_PORT', '5000')
REGISTRY_URL = f"https://{REGISTRY_HOST}:{REGISTRY_PORT}"
logging.basicConfig(filename='logs/central.log', level=logging.INFO, format='%(asctime)s - %(message)s')

# Captura de últimos errores y auditoría para exponer vía API
last_errors = []
audit_entries = []

class APILogHandler(logging.Handler):
    def emit(self, record):
        msg = self.format(record)
        if record.levelno >= logging.ERROR:
            last_errors.append(msg)
            # Limitar tamaño de la lista a 50 entradas
            if len(last_errors) > 50:
                del last_errors[0]
        if msg.startswith("AUDIT"):
            audit_entries.append(msg)
            if len(audit_entries) > 50:
                del audit_entries[0]

logger = logging.getLogger()
logger.addHandler(APILogHandler())

# Aplicación Flask para exponer el estado del sistema
app = Flask(__name__)

# Carga de claves de taxis para desencriptar mensajes
DEFAULT_KEYS_PATH = os.path.join(os.path.dirname(__file__), 'taxi_keys.json')
TAXI_KEYS_FILE = os.getenv('TAXI_KEYS_FILE', DEFAULT_KEYS_PATH)
try:
    with open(TAXI_KEYS_FILE, 'r') as f:
        TAXI_KEYS = json.load(f)
except Exception as e:
    TAXI_KEYS = {}
    logging.error(f"Could not load taxi keys: {e}")

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
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKER,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)
consumer = KafkaConsumer(
    'TAXI_POSITIONS',
    'CUSTOMER_REQUESTS',
    'TAXI_AUTH',
    'TAXI_SENSOR_STATUS',
    bootstrap_servers=KAFKA_BROKER,
    value_deserializer=lambda v: json.loads(v.decode('utf-8')),
)

# Mapa y registros
MAP_SIZE = 20
city_map = [[' ' for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]
taxis = {}  # Registro de taxis conectados
clients = {}  # Solicitudes activas
# Tokens de autenticación por taxi
taxi_tokens = {}
# Archivo opcional de localizaciones iniciales
LOCATIONS_FILE = os.getenv('LOCATIONS_FILE', os.path.join(os.path.dirname(__file__), 'locations.json'))

# Estado de tráfico reportado por CTC
traffic_status = 'UNKNOWN'

# Tiempo de espera para considerar que un taxi ha caído (segundos)
TAXI_TIMEOUT = int(os.getenv('TAXI_TIMEOUT', '10'))


@app.route('/state', methods=['GET'])
def state():
    """Exponer estado completo del sistema."""
    return jsonify({
        'map': city_map,
        'taxis': taxis,
        'clients': clients,
        'traffic': traffic_status,
        'errors': last_errors[-10:],
    })


@app.route('/audit', methods=['GET'])
def audit():
    """Exponer últimas entradas de auditoría."""
    return jsonify({'audit': audit_entries[-50:]})


def audit_log(ip, action, result):
    """Registrar evento en log de auditoría."""
    logging.info(f"AUDIT | IP:{ip} | {action} | {result}")


def broadcast_map():
    """Enviar mapa actualizado a Kafka."""
    producer.send('CITY_MAP', {'map': city_map})


def load_locations():
    """Leer posiciones iniciales desde un archivo opcional."""
    if os.path.exists(LOCATIONS_FILE):
        try:
            with open(LOCATIONS_FILE, 'r') as f:
                data = json.load(f)
            for taxi_id, pos in data.get('taxis', {}).items():
                taxis[str(taxi_id)] = {
                    'position': (pos['x'], pos['y']),
                    'available': True,
                }
            update_map()
            broadcast_map()
            logging.info(f"Loaded locations from {LOCATIONS_FILE}")
        except Exception as e:
            logging.error(f"Failed to load locations: {e}")
    else:
        logging.info(f"Locations file {LOCATIONS_FILE} not found")

def check_city_status():
    global traffic_status
    try:
        resp = requests.get(CTC_URL, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            traffic_status = data.get('status', 'UNKNOWN')
            city = data.get('city')
            print(f"CTC status for {city}: {traffic_status}")
            logging.info(f"CTC status for {city}: {traffic_status}")
        else:
            logging.warning(f"CTC responded with status {resp.status_code}")
            traffic_status = 'UNKNOWN'
    except Exception as e:
        logging.error(f"Error contacting CTC: {e}")
        traffic_status = 'UNKNOWN'

def monitor_traffic():
    while True:
        check_city_status()
        time.sleep(10)


def monitor_taxis():
    """Detectar taxis desconectados."""
    while True:
        now = time.time()
        for taxi_id, info in list(taxis.items()):
            last = info.get('last_update')
            if last and not info.get('incident') and now - last > TAXI_TIMEOUT:
                logging.error(f"Taxi {taxi_id} lost connection")
                info['incident'] = True
                update_map()
                client_id = info.get('client_id')
                if client_id is not None:
                    producer.send('CLIENT_NOTIFICATIONS', {
                        'client_id': client_id,
                        'message': 'Taxi lost'
                    })
        time.sleep(1)

def taxi_is_registered(taxi_id):
    try:
        url = f"{REGISTRY_URL}/registered/{taxi_id}"
        resp = requests.get(url, verify=False)
        if resp.status_code == 200:
            return resp.json().get('registered', False)
    except Exception as e:
        logging.error(f"Error contacting registry: {e}")
    return False


def process_auth_request(message):
    """Procesar solicitud de autenticación de un taxi."""
    taxi_id = str(message.get('taxi_id'))
    if not taxi_is_registered(taxi_id):
        logging.warning(f"Taxi {taxi_id} tried to auth but is not registered")
        return
    token = str(uuid.uuid4())
    taxi_tokens[taxi_id] = token
    producer.send('TAXI_AUTH_RESPONSE', {"taxi_id": taxi_id, "token": token})
    logging.info(f"Auth token generated for taxi {taxi_id}")


def send_return_to_base(taxi_id):
    """Enviar orden de volver a base e invalidar token."""
    if taxi_id in taxi_tokens:
        del taxi_tokens[taxi_id]
    producer.send('TAXI_COMMANDS', {"taxi_id": taxi_id, "command": "return_to_base"})
    logging.info(f"Return to base sent to taxi {taxi_id}")

def update_map():
    for x in range(MAP_SIZE):
        for y in range(MAP_SIZE):
            city_map[x][y] = ' '

    for taxi_id, data in taxis.items():
        x, y = data['position']
        symbol = 'X' if data.get('incident') else str(taxi_id)
        city_map[x][y] = symbol
    logging.info("Map updated")
    broadcast_map()

def process_taxi_message(message):
    taxi_id = str(message.get('taxi_id'))
    token = message.get('token')
    payload = message.get('payload')
    key = TAXI_KEYS.get(taxi_id)
    if not key or not payload:
        logging.warning(f"Missing key or payload for taxi {taxi_id}")
        return

    fernet = Fernet(key.encode())
    try:
        decrypted = fernet.decrypt(payload.encode())
        data = json.loads(decrypted.decode())
    except InvalidToken:
        print("mensaje no comprensible")
        logging.error(f"Invalid encryption from taxi {taxi_id}")
        return

    if taxi_tokens.get(taxi_id) != token:
        logging.warning(f"Invalid or missing token from taxi {taxi_id}")
        return

    if not taxi_is_registered(taxi_id):
        logging.warning(f"Taxi {taxi_id} not registered. Ignoring message")
        return

    pos_x = data['position']['x']
    pos_y = data['position']['y']

    # Validar y clamplear al rango [0, MAP_SIZE - 1]
    if not (0 <= pos_x < MAP_SIZE and 0 <= pos_y < MAP_SIZE):
        logging.warning(
            f"Taxi {taxi_id} reportó posición fuera de rango: ({pos_x}, {pos_y}). "
            f"Map size = {MAP_SIZE}x{MAP_SIZE}. Ignorando..."
        )
        pos_x = max(0, min(pos_x, MAP_SIZE - 1))
        pos_y = max(0, min(pos_y, MAP_SIZE - 1))

    entry = taxis.setdefault(taxi_id, {})
    entry.update({
        "position": (pos_x, pos_y),
        "available": data['available'],
        "last_update": time.time()
    })
    entry.pop('incident', None)
    if data['available']:
        entry.pop('client_id', None)
    update_map()
    logging.info(f"Taxi {taxi_id} updated: {taxis[taxi_id]}")
    audit_log('N/A', f'taxi_update_{taxi_id}', 'OK')

def process_customer_message(message):
    """Procesar solicitudes de clientes."""
    client_id = message['client_id']
    pickup = message['pickup_location']
    final_destination = message.get('destination')
    clients[client_id] = {
        "pickup_location": pickup,
        "destination": final_destination,
    }

    if traffic_status == 'KO':
        logging.info(f"Service request from Client {client_id} denied due to traffic KO")
        audit_log('N/A', f'client_{client_id}_request', 'DENIED')
        return

    # Asignar taxi
    assigned_taxi = None
    for taxi_id, details in taxis.items():
        if details['available']:
            assigned_taxi = taxi_id
            taxis[taxi_id]['available'] = False
            taxis[taxi_id]['client_id'] = client_id
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
        audit_log('N/A', f'assign_taxi_{assigned_taxi}', f'Client {client_id}')
    else:
        logging.info(f"No taxis available for Client {client_id}")

def process_sensor_message(message):
    """Procesar mensajes del sensor del taxi."""
    taxi_id = str(message.get('taxi_id'))
    status = message.get('status')
    if status == 'KO':
        send_return_to_base(taxi_id)
        audit_log('N/A', f'sensor_KO_{taxi_id}', 'return_to_base')

def kafka_listener():
    """Escuchar mensajes en Kafka."""
    for message in consumer:
        topic = message.topic
        if topic == 'TAXI_POSITIONS':
            process_taxi_message(message.value)
        elif topic == 'CUSTOMER_REQUESTS':
            process_customer_message(message.value)
        elif topic == 'TAXI_AUTH':
            process_auth_request(message.value)
        elif topic == 'TAXI_SENSOR_STATUS':
            process_sensor_message(message.value)

def start_server():
    """Iniciar el servidor Central."""
    logging.info("Central server started")
    kafka_listener()


def start_api():
    """Run the REST API to expose system state."""
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)


def command_loop():
    """Aceptar comandos manuales desde consola."""
    while True:
        try:
            cmd = input()
        except EOFError:
            print("STDIN closed, exiting command loop.")
            logging.info("STDIN closed, exiting command loop.")
            break
        cmd = cmd.strip().split()
        if not cmd:
            continue
        action = cmd[0].lower()
        if action == 'parar' and len(cmd) == 2:
            producer.send('TAXI_COMMANDS', {'taxi_id': cmd[1], 'command': 'stop'})
            audit_log('N/A', f'stop_{cmd[1]}', 'sent')
        elif action == 'reanudar' and len(cmd) == 2:
            producer.send('TAXI_COMMANDS', {'taxi_id': cmd[1], 'command': 'resume'})
            audit_log('N/A', f'resume_{cmd[1]}', 'sent')
        elif action == 'cambiar' and len(cmd) == 4:
            destination = {'x': int(cmd[2]), 'y': int(cmd[3])}
            producer.send('TAXI_COMMANDS', {
                'taxi_id': cmd[1],
                'command': 'change_destination',
                'destination': destination,
            })
            audit_log('N/A', f'change_dest_{cmd[1]}', destination)
        elif action == 'volver' and len(cmd) == 2:
            send_return_to_base(cmd[1])
            audit_log('N/A', f'return_base_{cmd[1]}', 'sent')
        else:
            print('Comando no reconocido')

if __name__ == "__main__":
    load_locations()
    threading.Thread(target=start_server, daemon=True).start()
    threading.Thread(target=monitor_traffic, daemon=True).start()
    threading.Thread(target=monitor_taxis, daemon=True).start()
    if sys.stdin.isatty():
        threading.Thread(target=command_loop, daemon=True).start()
    threading.Thread(target=start_api, daemon=True).start()
    while True:
        time.sleep(1)

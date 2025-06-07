import os
import sys
import threading
import time
import requests
from flask import Flask, jsonify

app = Flask(__name__)

API_KEY = os.getenv('OPENWEATHER_API_KEY', '')
CTC_CITY = os.getenv('CTC_CITY', 'London')
CITY_LOCK = threading.Lock()


def get_temperature(city):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
    resp = requests.get(url, timeout=5)
    data = resp.json()
    return data['main']['temp']


@app.route('/traffic', methods=['GET'])
def traffic_status():
    with CITY_LOCK:
        city = CTC_CITY
    try:
        temp = get_temperature(city)
        status = 'OK' if temp >= 0 else 'KO'
        return jsonify({'city': city, 'temperature': temp, 'status': status})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def menu():
    global CTC_CITY
    while True:
        try:
            new_city = input('Enter city name (current: %s): ' % CTC_CITY).strip()
        except EOFError:
            # End of input stream, avoid busy loop
            time.sleep(0.1)
            break
        if new_city:
            with CITY_LOCK:
                CTC_CITY = new_city
            print(f'City changed to {new_city}')


if __name__ == '__main__':
    if sys.stdin.isatty():
        threading.Thread(target=menu, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.getenv('CTC_PORT', '8080')))

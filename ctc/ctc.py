import os
import requests
import threading
from flask import Flask, jsonify

CITY = os.getenv("CITY", "Madrid")
API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

app = Flask(__name__)


def get_weather():
    url = (
        f"http://api.openweathermap.org/data/2.5/weather?q={CITY}&units=metric&appid={API_KEY}"
    )
    r = requests.get(url, timeout=5)
    data = r.json()
    temp = data.get("main", {}).get("temp")
    status = "KO" if temp is not None and temp < 0 else "OK"
    return temp, status


@app.route("/status", methods=["GET"])
def status():
    temp, stat = get_weather()
    return jsonify({"city": CITY, "status": stat, "temperature": temp})


def city_input():
    global CITY
    while True:
        try:
            new_city = input("New city (leave blank to keep current): ").strip()
            if new_city:
                CITY = new_city
                print(f"City changed to {CITY}")
        except EOFError:
            break


if __name__ == "__main__":
    threading.Thread(target=city_input, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)

import importlib
import taxi.digital_engine as de

def test_update_sensor_status():
    de.update_sensor_status("KO")
    assert de.sensor_status == "KO"

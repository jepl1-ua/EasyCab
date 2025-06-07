import importlib
import json
import sys
import types

import pytest

class DummyProducer:
    def __init__(self, *args, **kwargs):
        self.sent = []

    def send(self, topic, value):
        self.sent.append((topic, value))

    def close(self):
        pass

class DummyConsumer:
    def __init__(self, *args, **kwargs):
        pass

@pytest.fixture
def central_module(monkeypatch):
    monkeypatch.setattr('kafka.KafkaProducer', DummyProducer)
    monkeypatch.setattr('kafka.KafkaConsumer', DummyConsumer)
    if 'central.central' in sys.modules:
        module = importlib.reload(sys.modules['central.central'])
    else:
        module = importlib.import_module('central.central')
    return module

def test_customer_denied_when_traffic_ko(monkeypatch, central_module):
    module = central_module
    module.traffic_status = 'KO'
    module.taxis = {'1': {'position': (0, 0), 'available': True}}
    module.producer.sent.clear()

    message = {
        'client_id': 1,
        'pickup_location': {'x': 1, 'y': 1},
        'destination': {'x': 2, 'y': 2},
    }
    module.process_customer_message(message)
    assert module.producer.sent == []
    assert module.taxis['1']['available'] is True

def test_load_locations_updates_map(monkeypatch, tmp_path, central_module):
    module = central_module
    data = {'taxis': {'101': {'x': 3, 'y': 4}}}
    loc_file = tmp_path / 'loc.json'
    loc_file.write_text(json.dumps(data))
    monkeypatch.setattr(module, 'LOCATIONS_FILE', str(loc_file))

    module.taxis = {}
    module.city_map = [[' ' for _ in range(module.MAP_SIZE)] for _ in range(module.MAP_SIZE)]
    module.producer.sent.clear()

    module.load_locations()
    assert module.taxis['101']['position'] == (3, 4)
    assert any(topic == 'CITY_MAP' for topic, _ in module.producer.sent)


def test_sensor_status_triggers_return(monkeypatch, central_module):
    """Central should send a return_to_base command when sensor reports KO."""
    module = central_module
    module.producer.sent.clear()
    module.taxi_tokens = {'55': 'token'}

    message = {'taxi_id': '55', 'status': 'KO'}
    module.process_sensor_message(message)

    assert ('TAXI_COMMANDS', {'taxi_id': '55', 'command': 'return_to_base'}) in module.producer.sent


def test_kafka_listener_processes_sensor_message(monkeypatch, central_module):
    module = central_module

    class SingleMessageConsumer:
        def __iter__(self_inner):
            msg = types.SimpleNamespace(topic='TAXI_SENSOR_STATUS', value={'taxi_id': '42', 'status': 'KO'})
            return iter([msg])

    module.consumer = SingleMessageConsumer()
    module.producer.sent.clear()
    module.taxi_tokens = {'42': 'token'}

    # Run listener once (will exit after iterator is exhausted)
    module.kafka_listener()

    assert ('TAXI_COMMANDS', {'taxi_id': '42', 'command': 'return_to_base'}) in module.producer.sent

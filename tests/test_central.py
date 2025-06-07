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

import importlib
import json
import sys

import pytest
from cryptography.fernet import Fernet

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


def encrypt_payload(key, data):
    f = Fernet(key.encode())
    token = f.encrypt(json.dumps(data).encode()).decode()
    return token


def test_process_taxi_message_clamps_position(monkeypatch, central_module):
    module = central_module
    taxi_id = '9'
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(module, 'TAXI_KEYS', {taxi_id: key})
    monkeypatch.setattr(module, 'taxi_is_registered', lambda tid: True)
    module.taxi_tokens = {taxi_id: 'tok'}
    module.producer.sent.clear()
    payload = encrypt_payload(key, {'position': {'x': 50, 'y': -5}, 'available': True})
    message = {'taxi_id': taxi_id, 'token': 'tok', 'payload': payload}
    module.taxis = {}

    module.process_taxi_message(message)

    assert module.taxis[taxi_id]['position'] == (module.MAP_SIZE - 1, 0)
    assert any(topic == 'CITY_MAP' for topic, _ in module.producer.sent)


def test_process_auth_request_generates_token(monkeypatch, central_module):
    module = central_module
    monkeypatch.setattr(module, 'taxi_is_registered', lambda tid: True)
    module.producer.sent.clear()

    monkeypatch.setattr(module.uuid, 'uuid4', lambda: 'testtoken')
    module.process_auth_request({'taxi_id': '5'})

    assert module.taxi_tokens['5'] == 'testtoken'
    assert ('TAXI_AUTH_RESPONSE', {'taxi_id': '5', 'token': 'testtoken'}) in module.producer.sent


def test_send_return_to_base_invalidates_token(central_module):
    module = central_module
    module.taxi_tokens = {'7': 'token'}
    module.producer.sent.clear()

    module.send_return_to_base('7')

    assert '7' not in module.taxi_tokens
    assert ('TAXI_COMMANDS', {'taxi_id': '7', 'command': 'return_to_base'}) in module.producer.sent

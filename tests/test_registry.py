from registry.registry import app, registered_taxis


def test_register_and_unregister():
    client = app.test_client()
    resp = client.post('/register', json={'taxi_id': 'abc'})
    assert resp.status_code == 201
    assert 'abc' in registered_taxis

    resp = client.get('/registered/abc')
    assert resp.json['registered'] is True

    resp = client.delete('/unregister/abc')
    assert resp.status_code == 200
    assert 'abc' not in registered_taxis


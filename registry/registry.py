from flask import Flask, request, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)

registered_taxis = set()

@app.route('/register', methods=['POST'])
def register_taxi():
    data = request.get_json()
    taxi_id = data.get('taxi_id')
    if not taxi_id:
        return jsonify({'error': 'taxi_id required'}), 400
    registered_taxis.add(str(taxi_id))
    return jsonify({'registered': list(registered_taxis)}), 201

@app.route('/unregister/<taxi_id>', methods=['DELETE'])
def unregister_taxi(taxi_id):
    if taxi_id in registered_taxis:
        registered_taxis.remove(taxi_id)
        return jsonify({'unregistered': taxi_id}), 200
    return jsonify({'error': 'taxi not found'}), 404

@app.route('/registered/<taxi_id>', methods=['GET'])
def is_registered(taxi_id):
    return jsonify({'registered': taxi_id in registered_taxis})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, ssl_context='adhoc')

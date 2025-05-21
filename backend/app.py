# backend/app.py

# CRITICAL: eventlet.monkey_patch() must be the very first thing.
import eventlet
eventlet.monkey_patch()

print("DEBUG: Monkey patch called.")

from flask import Flask
from flask_socketio import SocketIO
import logging # For basic logging

# Configure basic logging to see Flask-SocketIO messages
logging.basicConfig(level=logging.DEBUG)

print("DEBUG: Flask and Flask-SocketIO imported.")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'temporary_secret_for_debugging!' # Use a simple secret

# Define allowed origins, including your frontend's actual origin
allowed_origins_list = ["http://localhost:5173", "http://192.168.0.18:5173"]

# Explicitly set async_mode and add cors_allowed_origins
socketio = SocketIO(app, async_mode='eventlet', logger=True, engineio_logger=True, cors_allowed_origins=allowed_origins_list)

print("DEBUG: Flask app and SocketIO instance created.")

@app.route('/')
def index():
    return "Minimal Flask App with Socket.IO is Running!"

@socketio.on('connect')
def handle_connect():
    print('DEBUG: Client connected to Socket.IO')

@socketio.on('disconnect')
def handle_disconnect():
    print('DEBUG: Client disconnected from Socket.IO')

# Basic test event
@socketio.on('test_event')
def handle_my_custom_event(json):
    print('DEBUG: received json: ' + str(json))
    socketio.emit('response_event', {'data': 'Server response to test_event'})

if __name__ == '__main__':
    print("DEBUG: Starting Flask-SocketIO server with Eventlet...")
    print(f"DEBUG: SocketIO server instance should be Eventlet: {socketio.server}")
    try:
        socketio.run(app, host="0.0.0.0", port=5001, debug=True, use_reloader=False)
    except Exception as e:
        print(f"ERROR starting server: {e}") 
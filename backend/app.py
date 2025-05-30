# app.py
from flask import Flask, request, jsonify, Response, current_app
from flask_cors import CORS
from flask_socketio import SocketIO
import sqlite3, json, logging
import secrets
import uuid
import io # Standard io module for StringIO
import csv # Standard csv module

from .auth import authenticate, token_required
from .db import DB_NAME, init_db
from .inventory import add_records
from .stats import fetch_logs, logs_to_csv
from .serial_io import serial_mgr
from . import task_queue
from .error_messages import get_error_message
from .camera_stream import mjpeg_feed  # Import the mjpeg_feed function

# Define SECRET_KEY for the application
# This should be a long, random, and secret string in production
# For development, secrets.token_hex(16) is fine.
# If you have an existing SECRET_KEY, ensure it's defined here.
FLASK_APP_SECRET_KEY = secrets.token_hex(16) 

# Configuration for enabling/disabling serial communication
SERIAL_COMMUNICATION_ENABLED = True # Set to False for development without hardware

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = FLASK_APP_SECRET_KEY
app.config['SERIAL_COMMUNICATION_ENABLED'] = SERIAL_COMMUNICATION_ENABLED

# Initialize SocketIO
# Make sure to replace 192.168.0.16 with your Mac's actual current IP if it changes,
# or use a more dynamic solution for production on Pi later.
allowed_origins_list = ["http://localhost:5173", "http://192.168.0.18:5173", "http://192.168.0.16:8080"]
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins=allowed_origins_list, logger=True, engineio_logger=True)

# Configure basic logging
logging.basicConfig(level=logging.DEBUG)

# ---- Pass the socketio instance to the task_queue module ----
task_queue.set_socketio(socketio)

# ---- DEBUG: Log all incoming request paths ----
@app.before_request
def log_request_info():
    app.logger.debug(f'Request Path: {request.path}')
    app.logger.debug(f'Request Method: {request.method}')
    app.logger.debug(f'Request Headers: {request.headers}')
    if request.method == 'POST' and request.is_json:
        app.logger.debug(f'Request JSON Body: {request.get_json(silent=True)}')

CORS(app, resources={r"/api/*": {"origins": "*"}}) # Allow all origins for /api routes
init_db()

# Configure serial manager based on app config BEFORE starting workers
serial_mgr.configure_and_discover(app.config)

# ---- Reset racks if serial communication is enabled ----
if app.config.get('SERIAL_COMMUNICATION_ENABLED', True): # Check the same config key
    if serial_mgr.ports: # Check if any ports were actually discovered
        app.logger.info("Attempting to reset discovered racks...")
        serial_mgr.reset_all_racks()
        app.logger.info("Finished reset attempt for discovered racks.")
    else:
        app.logger.info("SERIAL_COMMUNICATION_ENABLED but no racks discovered. Skipping reset.")
else:
    app.logger.info("SERIAL_COMMUNICATION_DISABLED. Skipping reset of racks.")

# Start rack workers (ensure this uses the task_queue module's function)
task_queue.start_global_worker()

# ───── routes ─────
@app.route("/api/ping")
def ping():
    return {"message": "pong"}

# ---- DEBUG: Simple test route ----
@app.route("/api/test-debug")
def test_debug_route():
    app.logger.info("Accessed /api/test-debug successfully")
    return jsonify({"message": "Debug route for /api/test-debug is working!"}), 200

# ---- JWT 로그인 ----
@app.route("/api/check-user", methods=["POST"])
def check_user_route():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    
    app.logger.debug(f"Checking user: {username}")

    if not username:
        app.logger.warning("check_user_route: No username provided")
        return jsonify({"error": "username required"}), 400
    
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT username FROM users WHERE username=?", (username,))
        user_exists = cur.fetchone()
    except sqlite3.Error as e:
        app.logger.error(f"Database error in check_user_route: {str(e)}")
        return jsonify({"error": "Database error", "message": str(e)}), 500
    finally:
        if conn:
            conn.close()
    
    if user_exists:
        app.logger.info(f"User '{username}' exists.")
        return jsonify({"exists": True}), 200
    else:
        app.logger.info(f"User '{username}' does not exist.")
        return jsonify({"exists": False}), 200

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    
    print(f"Login attempt: username='{username}'")
    
    tok = authenticate(username, password)
    
    if tok:
        print(f"Login successful for '{username}', token generated.")
        return {"token": tok}, 200
    else:
        print(f"Login failed for '{username}'.")
        return {"error": get_error_message("invalid_credentials")}, 401

# ---- 인벤토리 ----
@app.route("/api/inventory")
def inventory():
    rack, slot = request.args.get("rack"), request.args.get("slot")
    q, p = "SELECT * FROM current_inventory", []
    if rack and slot:
        q += " WHERE rack=? AND slot=?"; p = [rack.upper(), int(slot)]
    elif rack:
        q += " WHERE rack=?"; p = [rack.upper()]
    con = sqlite3.connect(DB_NAME); cur = con.cursor(); cur.execute(q, p)
    rows = cur.fetchall(); con.close()
    return jsonify([{
        "id": r[0], "product_code": r[1], "product_name": r[2],
        "rack": r[3], "slot": r[4], "total_quantity": r[5],
        "cargo_owner": r[6], "last_update": r[7]
    } for r in rows])

@app.route("/api/activity-logs")
@token_required
def get_activity_logs():
    try:
        limit = request.args.get('limit', default=100, type=int) # Default to 100 logs if not specified
        order = request.args.get('order', default='desc').lower()

        if order not in ['asc', 'desc']:
            order = 'desc' # Default to descending if an invalid order is provided

        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row # This allows accessing columns by name
        cur = conn.cursor()

        # Ensure column names match your product_logs table exactly
        # Common columns: id, product_code, product_name, rack, slot, movement_type, quantity, cargo_owner, timestamp
        query = f"SELECT id, product_code, product_name, rack, slot, movement_type, quantity, cargo_owner, timestamp, batch_id FROM product_logs ORDER BY timestamp {order.upper()} LIMIT ?"
        
        cur.execute(query, (limit,))
        log_rows = cur.fetchall()
        conn.close()

        logs_list = [dict(row) for row in log_rows]
        
        return jsonify(logs_list), 200

    except sqlite3.Error as e:
        current_app.logger.error(f"Database error in get_activity_logs: {str(e)}")
        return jsonify({"error": "Database error", "message": str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error in get_activity_logs: {str(e)}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred", "message": str(e)}), 500

# ---- record JSON ----
@app.route("/api/record", methods=["POST"])
@token_required
def record_inventory_and_queue_tasks():
    data = request.get_json()
    if not isinstance(data, list):
        return jsonify({
            "success": False, 
            "message": get_error_message("invalid_data_format")
        }), 400
    
    success, message = add_records(data)
    
    if success:
        return jsonify({
            "success": True, 
            "message": "작업이 성공적으로 처리되었습니다"
        }), 200
    else:
        return jsonify({
            "success": False, 
            "message": message
        }), 500

# ---- New Work Tasks Endpoint ----
@app.route("/api/work-tasks")
@token_required
def get_work_tasks_route():
    status = request.args.get("status")
    try:
        tasks = task_queue.get_work_tasks_by_status(status)
        return jsonify(tasks), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching work tasks: {e}", exc_info=True)
        return jsonify({
            "error": get_error_message("fetch_tasks_error"),
            "message": str(e)
        }), 500

@app.route("/api/pending-task-counts")
@token_required
def get_pending_task_counts_route():
    try:
        counts = task_queue.get_pending_task_counts()
        return jsonify(counts), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching pending task counts: {e}", exc_info=True)
        return jsonify({
            "error": get_error_message("fetch_counts_error"),
            "message": str(e)
        }), 500

@app.route("/api/upload-tasks", methods=["POST"])
@token_required
def upload_tasks_route():
    if not request.is_json:
        return jsonify({
            "error": get_error_message("json_body_required")
        }), 400

    tasks_data = request.get_json()
    if not isinstance(tasks_data, list):
        return jsonify({
            "error": get_error_message("invalid_request_body")
        }), 400

    if not tasks_data:
        return jsonify({
            "message": get_error_message("no_tasks_provided"),
            "processed_count": 0,
            "errors": []
        }), 200

    app.logger.debug(f"--- /api/upload-tasks: Received {len(tasks_data)} tasks. Processing as a single batch. ---")
    
    batch_id = str(uuid.uuid4())
    # Get user info from token_required decorator
    user_info = getattr(request, 'user', None)
    if not user_info:
        return jsonify({
            "error": get_error_message("invalid_credentials")
        }), 401

    success, message = add_records(tasks_data, batch_id, user_info)

    if success:
        app.logger.info(f"--- /api/upload-tasks: Batch {batch_id} processed successfully. {len(tasks_data)} tasks queued. ---")
        return jsonify({
            "message": f"{len(tasks_data)}개의 작업이 성공적으로 처리되어 대기열에 추가되었습니다",
            "processed_count": len(tasks_data),
            "errors": [],
            "batch_id": batch_id
        }), 200
    else:
        app.logger.error(f"--- /api/upload-tasks: Error processing batch {batch_id}: {message}. Attempted {len(tasks_data)} tasks. ---")
        return jsonify({
            "message": f"배치 처리 중 오류 발생: {message}",
            "processed_count": 0,
            "errors": [message]
        }), 400

@app.route("/api/download-batch-task/<batch_id>")
@token_required
def download_batch_task(batch_id):
    if not batch_id:
        return jsonify({
            "error": get_error_message("batch_not_found")
        }), 400

    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("""
            SELECT product_code, product_name, rack, slot, movement_type, quantity, cargo_owner, timestamp 
            FROM product_logs 
            WHERE batch_id = ? 
            ORDER BY timestamp ASC
        """, (batch_id,))
        log_rows = cur.fetchall()

        if not log_rows:
            return jsonify({
                "error": get_error_message("batch_not_found")
            }), 404

        si = io.StringIO()
        fieldnames = ['product_code', 'product_name', 'rack', 'slot', 'movement_type', 'quantity', 'cargo_owner', 'timestamp']
        writer = csv.DictWriter(si, fieldnames=fieldnames)

        writer.writeheader()
        for row in log_rows:
            writer.writerow(dict(row))

        output = si.getvalue()
        si.close()
        
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename=batch_task_{batch_id}.csv"}
        )

    except sqlite3.Error as e:
        current_app.logger.error(f"Database error in download_batch_task for batch_id {batch_id}: {str(e)}")
        return jsonify({
            "error": get_error_message("database_error"),
            "message": str(e)
        }), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error in download_batch_task for batch_id {batch_id}: {str(e)}", exc_info=True)
        return jsonify({
            "error": get_error_message("unexpected_error"),
            "message": str(e)
        }), 500
    finally:
        if conn:
            conn.close()

@app.route("/api/camera/live_feed")
def camera_live_feed():
    return mjpeg_feed()

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# ───── run ─────
if __name__ == "__main__":
    print("Starting Flask-SocketIO server with threading mode on port 5001...")
    print(f"SocketIO server instance: {socketio.server}") # Log the server instance
    socketio.run(app, host="0.0.0.0", port=5001, debug=True, use_reloader=False)
    # allow_unsafe_werkzeug=True might be needed for newer Werkzeug versions if use_reloader=False and debug=True 
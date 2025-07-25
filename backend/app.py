# app.py
from flask import Flask, request, jsonify, Response, current_app
from flask_cors import CORS
from flask_socketio import SocketIO
import sqlite3, json, logging
import secrets
import uuid
import io # Standard io module for StringIO
import csv # Standard csv module
import threading
import time

from .auth import authenticate, token_required, logout_current_session, get_current_session_info
from .db import DB_NAME, init_db
from .inventory import add_records
from .stats import fetch_logs, logs_to_csv
from .serial_io import serial_mgr
from . import task_queue
from .error_messages import get_error_message
from .camera_stream import mjpeg_feed, get_available_cameras  # Import the mjpeg_feed function and camera list
from .camera_history import get_camera_history

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
allowed_origins_list = ["http://localhost:5173", "http://192.168.0.37:5173", "http://192.168.0.18:5173", "http://192.168.0.16:8080"]
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins=allowed_origins_list, logger=True, engineio_logger=True)

# Configure basic logging
logging.basicConfig(level=logging.INFO)

# ---- Pass the socketio instance and app instance to the task_queue module ----
task_queue.set_socketio(socketio)
task_queue.set_app(app)

# ---- Optional Module Health Check Service ----
def optional_module_health_check_service():
    """Background service to check optional module health every minute"""
    while True:
        try:
            time.sleep(60)  # Check every 1 minute
            
            if serial_mgr.is_optional_module_connected():
                is_healthy = serial_mgr.check_optional_module_health()
                
                # Emit status update to connected clients
                socketio.emit('optional_module_status', {
                    'connected': True,
                    'healthy': is_healthy,
                    'status': 'online' if is_healthy else 'offline',
                    'timestamp': time.time()
                })
                
                if not is_healthy:
                    print(f"WARNING: Optional module health check failed at {time.ctime()}")
            else:
                # Module not connected
                socketio.emit('optional_module_status', {
                    'connected': False,
                    'healthy': False,
                    'status': 'disconnected',
                    'timestamp': time.time()
                })
                
        except Exception as e:
            print(f"Error in optional module health check service: {e}")

# Start health check service in background thread
health_check_thread = threading.Thread(target=optional_module_health_check_service, daemon=True)
health_check_thread.start()
print("Optional module health check service started")

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

# Reset any tasks that were stuck in 'in_progress' from a previous run
# This logic was causing a crash and was requested to be removed.
# from . import task_queue
# task_queue.reset_stale_tasks()

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

# Start the background worker for task processing
from . import task_queue
task_queue.set_socketio(socketio)
task_queue.start_worker(app)

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
    
    app.logger.info(f"Login attempt: username='{username}'")
    
    tok = authenticate(username, password)
    
    if tok:
        app.logger.info(f"Login successful for '{username}', token generated.")
        return {"token": tok}, 200
    else:
        app.logger.warning(f"Login failed for '{username}' - invalid credentials.")
        return {"error": get_error_message("invalid_credentials")}, 401

@app.route("/api/logout", methods=["POST"])
@token_required
def logout():
    """Logout the current user and invalidate their session"""
    try:
        user_info = getattr(request, 'user', None)
        if user_info:
            username = user_info['username']
            session_id = user_info['session_id']
            
            # Logout the current session
            logout_success = logout_current_session()
            
            if logout_success:
                app.logger.info(f"User '{username}' with session '{session_id}' logged out successfully")
                return jsonify({
                    "success": True,
                    "message": "로그아웃되었습니다."
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "message": "로그아웃 처리 중 오류가 발생했습니다."
                }), 500
        else:
            return jsonify({
                "success": False,
                "message": "사용자 정보를 찾을 수 없습니다."
            }), 400
            
    except Exception as e:
        app.logger.error(f"Error during logout: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "message": "로그아웃 처리 중 오류가 발생했습니다."
        }), 500

@app.route("/api/session-status")
@token_required
def session_status():
    """Get current session status information"""
    try:
        session_info = get_current_session_info()
        user_info = getattr(request, 'user', None)
        
        if session_info and user_info:
            return jsonify({
                "active": True,
                "username": session_info['username'],
                "login_time": session_info['login_time'].isoformat(),
                "session_id": session_info['session_id'][:8] + "...",  # Partial session ID for security
                "current_user": user_info['username']
            }), 200
        else:
            return jsonify({
                "active": False,
                "message": "세션이 활성화되지 않았습니다."
            }), 200
            
    except Exception as e:
        app.logger.error(f"Error getting session status: {str(e)}", exc_info=True)
        return jsonify({
            "active": False,
            "error": "세션 상태 확인 중 오류가 발생했습니다."
        }), 500

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

        # FIXED: Only return product_logs entries that have corresponding completed work_tasks
        # This prevents pending tasks from showing up as "completed" in the UI
        query = f"""
            WITH latest_logs AS (
                SELECT 
                    pl.id, pl.product_code, pl.product_name, pl.rack, pl.slot, 
                    pl.movement_type, pl.quantity, pl.cargo_owner, pl.timestamp, pl.batch_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY pl.rack, pl.slot, pl.movement_type, pl.product_code 
                        ORDER BY pl.timestamp DESC
                    ) as rn
                FROM product_logs pl
            )
            SELECT 
                ll.id, ll.product_code, ll.product_name, ll.rack, ll.slot, 
                ll.movement_type, ll.quantity, ll.cargo_owner, ll.timestamp, ll.batch_id,
                wt.start_time, wt.end_time, wt.status as task_status
            FROM latest_logs ll
            INNER JOIN batch_task_links btl ON ll.batch_id = btl.batch_id
            INNER JOIN work_tasks wt ON btl.task_id = wt.id 
                AND wt.rack = ll.rack 
                AND wt.slot = ll.slot 
                AND wt.movement = ll.movement_type
                AND wt.product_code = ll.product_code
                AND wt.status = 'done'
            WHERE ll.rn = 1
            ORDER BY ll.timestamp {order.upper()} 
            LIMIT ?
        """
        
        cur.execute(query, (limit,))
        log_rows = cur.fetchall()
        conn.close()

        logs_list = []
        for row in log_rows:
            log_dict = dict(row)
            # Use precise timing from work_tasks since we're only showing completed tasks
            logs_list.append(log_dict)
        
        return jsonify(logs_list), 200

    except sqlite3.Error as e:
        current_app.logger.error(f"Database error in get_activity_logs: {str(e)}")
        return jsonify({"error": "Database error", "message": str(e)}), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error in get_activity_logs: {str(e)}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred", "message": str(e)}), 500

@app.route("/api/camera-history")
@token_required
def camera_history():
    try:
        limit = request.args.get('limit', default=50, type=int)
        history = get_camera_history(limit)
        return jsonify(history), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching camera history: {e}", exc_info=True)
        return jsonify({
            "error": get_error_message("fetch_history_error"),
            "message": str(e)
        }), 500

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
        # Get user info from token_required decorator
        user_info = getattr(request, 'user', None)
        if not user_info:
            return jsonify({
                "error": get_error_message("invalid_credentials")
            }), 401
            
        tasks = task_queue.get_work_tasks_by_status(status, user_info)
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
        # Get user info from token_required decorator
        user_info = getattr(request, 'user', None)
        if not user_info:
            return jsonify({
                "error": get_error_message("invalid_credentials")
            }), 401
            
        counts = task_queue.get_pending_task_counts(user_info)
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

@app.route("/api/reset", methods=["POST"])
@token_required
def reset_system():
    """Reset all racks and clear task queues"""
    try:
        app.logger.info("Reset signal received - resetting all racks and clearing queues")
        
        # Reset all racks if serial communication is enabled
        if app.config.get('SERIAL_COMMUNICATION_ENABLED', True):
            if serial_mgr.ports:
                app.logger.info("Resetting all discovered racks...")
                serial_mgr.reset_all_racks()
                app.logger.info("All racks reset successfully")
            else:
                app.logger.warning("No racks discovered for reset")
        else:
            app.logger.info("Serial communication disabled - skipping rack reset")
        
        # Clear task queues
        task_queue.clear_all_queues()
        app.logger.info("Task queues cleared")
        
        # Emit reset signal to all connected clients
        socketio.emit('system_reset', {'message': '시스템이 초기화되었습니다.'})
        
        return jsonify({
            "success": True,
            "message": "시스템이 성공적으로 초기화되었습니다."
        }), 200
        
    except Exception as e:
        app.logger.error(f"Error during system reset: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "시스템 초기화 중 오류가 발생했습니다.",
            "message": str(e)
        }), 500

@app.route("/api/optional-module/activate", methods=["POST"])
@token_required
def activate_optional_module():
    """Activate the optional module by sending '1' command"""
    try:
        app.logger.info("Optional module activation requested")
        
        if not serial_mgr.is_optional_module_connected():
            return jsonify({
                "success": False,
                "error": "선택적 모듈이 연결되지 않았습니다.",
                "message": "Optional module not connected"
            }), 404
        
        success = serial_mgr.activate_optional_module()
        
        if success:
            app.logger.info("Optional module activated successfully")
            return jsonify({
                "success": True
            }), 200
        else:
            app.logger.error("Failed to activate optional module")
            return jsonify({
                "success": False,
                "error": "선택적 모듈 활성화에 실패했습니다.",
                "message": "Failed to send activation command"
            }), 500
        
    except Exception as e:
        app.logger.error(f"Error during optional module activation: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "선택적 모듈 활성화 중 오류가 발생했습니다.",
            "message": str(e)
        }), 500

@app.route("/api/optional-module/status")
@token_required
def get_optional_module_status():
    """Get the status of the optional module"""
    try:
        is_connected = serial_mgr.is_optional_module_connected()
        is_healthy = False
        
        if is_connected:
            is_healthy = serial_mgr.check_optional_module_health()
        
        return jsonify({
            "success": True,
            "connected": is_connected,
            "healthy": is_healthy,
            "status": "online" if (is_connected and is_healthy) else "offline"
        }), 200
        
    except Exception as e:
        app.logger.error(f"Error checking optional module status: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "선택적 모듈 상태 확인 중 오류가 발생했습니다.",
            "message": str(e)
        }), 500

@app.route("/api/camera/live_feed")
def camera_live_feed():
    return mjpeg_feed()

@app.route("/api/camera/<int:camera_num>/live_feed")
def camera_live_feed_specific(camera_num):
    """Get live feed for a specific camera"""
    return mjpeg_feed(camera_num)

@app.route("/api/cameras/available")
def get_available_cameras_endpoint():
    """Get list of available cameras"""
    try:
        available_cameras = get_available_cameras()
        return jsonify({
            "success": True,
            "cameras": available_cameras,
            "total_cameras": len(available_cameras)
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error getting available cameras: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "카메라 정보를 가져오는 중 오류가 발생했습니다.",
            "message": str(e)
        }), 500

# Debug endpoint to help troubleshoot session issues
@app.route("/api/debug/session-info")
@token_required
def debug_session_info():
    """Debug endpoint to get detailed session information"""
    try:
        from .auth import get_current_session_info
        session_info = get_current_session_info()
        user_info = getattr(request, 'user', None)
        
        return jsonify({
            "current_session": {
                "session_id": session_info['session_id'] if session_info else None,
                "username": session_info['username'] if session_info else None,
                "login_time": session_info['login_time'].isoformat() if session_info else None
            } if session_info else None,
            "token_info": {
                "username": user_info['username'] if user_info else None,
                "session_id": user_info['session_id'] if user_info else None,
                "user_id": user_info['id'] if user_info else None
            } if user_info else None,
            "session_match": session_info['session_id'] == user_info['session_id'] if (session_info and user_info) else False
        }), 200
        
    except Exception as e:
        app.logger.error(f"Error in debug session info: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

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
    socketio.run(app, host="0.0.0.0", port=5001, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)
    # allow_unsafe_werkzeug=True might be needed for newer Werkzeug versions if use_reloader=False and debug=True 
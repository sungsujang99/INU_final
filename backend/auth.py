# auth.py
import datetime, sqlite3, jwt, uuid
from functools import wraps
from flask import request, jsonify, current_app
from passlib.hash import bcrypt
from .db import DB_NAME
from .error_messages import get_error_message

SECRET = "ChangeThisSecret!"  # 환경변수로 바꾸길 권장

# Global variable to track the current active session
current_active_session = None

def authenticate(username, password):
    global current_active_session
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, hashed_password, role, display_name FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    conn.close()
    
    if row and bcrypt.verify(password, row[1]):
        # Generate a unique session ID
        session_id = str(uuid.uuid4())
        
        # Invalidate any previous session by updating the global session
        current_active_session = {
            'session_id': session_id,
            'username': username,
            'user_id': row[0],
            'login_time': datetime.datetime.utcnow()
        }
        
        # Create JWT token with session ID
        token = jwt.encode(
            {"sub": username,
             "user_id": row[0],
             "role": row[2],
             "display_name": row[3],
             "session_id": session_id,
             "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=12)},
            SECRET, algorithm="HS256")
        
        current_app.logger.info(f"New session created for user '{username}' with session ID: {session_id}")
        if current_active_session:
            current_app.logger.info(f"Previous session invalidated")
        
        return token
    return None

def logout_current_session():
    """Logout the current active session"""
    global current_active_session
    if current_active_session:
        current_app.logger.info(f"Session {current_active_session['session_id']} for user '{current_active_session['username']}' logged out")
        current_active_session = None
        return True
    return False

def get_current_session_info():
    """Get information about the current active session"""
    global current_active_session
    return current_active_session

def token_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        global current_active_session
        
        hdr = request.headers.get("Authorization", "")
        if not hdr.startswith("Bearer "):
            return jsonify({"error": get_error_message("token_required")}), 401
        token = hdr.split()[1]
        try:
            decoded = jwt.decode(token, SECRET, algorithms=["HS256"])
            username = decoded['sub']
            token_session_id = decoded.get('session_id')
            
            # Check if this token's session is the current active session
            if not current_active_session or current_active_session['session_id'] != token_session_id:
                current_app.logger.warning(f"Invalid session attempt by user '{username}' with session ID: {token_session_id}")
                return jsonify({
                    "error": "세션이 만료되었습니다. 다른 사용자가 로그인했거나 세션이 무효화되었습니다.",
                    "code": "session_invalidated"
                }), 401
            
            # Get user info from database
            conn = None
            try:
                conn = sqlite3.connect(DB_NAME)
                cur = conn.cursor()
                cur.execute("SELECT id, role, display_name FROM users WHERE username=?", (username,))
                user_row = cur.fetchone()
                
                if not user_row:
                    current_app.logger.error(f"User {username} not found in database")
                    return jsonify({"error": get_error_message("invalid_credentials")}), 401
                
                # Set user info in request object
                request.user = {
                    'id': user_row[0],
                    'username': username,
                    'role': user_row[1],
                    'display_name': user_row[2],
                    'session_id': token_session_id
                }
            except sqlite3.Error as e:
                current_app.logger.error(f"Database error in token validation: {str(e)}")
                return jsonify({"error": get_error_message("database_error")}), 500
            finally:
                if conn:
                    conn.close()
                    
        except jwt.ExpiredSignatureError:
            return jsonify({"error": get_error_message("token_expired")}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": get_error_message("invalid_token")}), 401
        except Exception as e:
            current_app.logger.error(f"Unexpected error in token validation: {str(e)}")
            return jsonify({"error": get_error_message("unexpected_error")}), 500
            
        return f(*args, **kwargs)
    return wrapper

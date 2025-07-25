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
    
    try:
        # Check user credentials
        cur.execute("SELECT id, hashed_password, role, display_name FROM users WHERE username=?", (username,))
        row = cur.fetchone()
        
        if not row or not bcrypt.verify(password, row[1]):
            return None
            
        # Update login counter
        cur.execute("SELECT count FROM login_counter WHERE id = 1")
        counter_row = cur.fetchone()
        current_count = counter_row[0] if counter_row else 0
        new_count = (current_count + 1) % 5  # Reset to 0 after every 5 logins
        
        # Update counter
        if new_count == 0:  # Every 5th login
            # Clear rack status by deleting product_logs
            cur.execute("DELETE FROM product_logs")
            # Reset counter and update timestamp
            cur.execute("""
                UPDATE login_counter 
                SET count = ?, last_reset = CURRENT_TIMESTAMP 
                WHERE id = 1
            """, (new_count,))
        else:
            # Just increment counter
            cur.execute("UPDATE login_counter SET count = ? WHERE id = 1", (new_count,))
        
        # Generate a unique session ID
        session_id = str(uuid.uuid4())
        
        # Log previous session before invalidating
        previous_session = current_active_session
        if previous_session:
            current_app.logger.warning(f"🔄 MULTIPLE LOGIN DETECTED: Previous session invalidated for user '{previous_session['username']}' with session ID: {previous_session['session_id']}")
            current_app.logger.warning(f"🔄 New login attempt by user '{username}' - this will create session ID: {session_id}")
            current_app.logger.warning(f"🔄 This indicates multiple browser tabs or duplicate login attempts")
        
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
        
        current_app.logger.info(f"✅ New session created for user '{username}' with session ID: {session_id}")
        
        conn.commit()
        return token
        
    except Exception as e:
        current_app.logger.error(f"Error in authenticate: {str(e)}", exc_info=True)
        return None
    finally:
        conn.close()

def logout_current_session():
    """Logout the current active session"""
    global current_active_session
    if current_active_session:
        current_app.logger.info(f"🚪 Session {current_active_session['session_id']} for user '{current_active_session['username']}' logged out")
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
            
            # Add detailed logging for session validation
            current_app.logger.debug(f"🔍 Token validation for user '{username}' with session ID: {token_session_id}")
            if current_active_session:
                current_app.logger.debug(f"🔍 Current active session: user '{current_active_session['username']}' with session ID: {current_active_session['session_id']}")
            else:
                current_app.logger.debug("🔍 No current active session")
            
            # Special case: if no active session exists (e.g., after server restart)
            # and we have a valid JWT token, re-establish the session
            if not current_active_session and token_session_id:
                current_app.logger.info(f"🔄 Re-establishing session for user '{username}' after server restart")
                current_active_session = {
                    'session_id': token_session_id,
                    'username': username,
                    'user_id': decoded['user_id'],
                    'login_time': datetime.datetime.utcnow()  # Use current time since we don't have original
                }
            
            # Check if this token's session is the current active session
            elif current_active_session['session_id'] != token_session_id:
                current_app.logger.warning(f"❌ Session validation failed for user '{username}' with session ID: {token_session_id}")
                current_app.logger.warning(f"❌ Expected session ID: {current_active_session['session_id']}")
                current_app.logger.warning(f"❌ This usually means multiple browser tabs or a new login invalidated this session")
                return jsonify({
                    "error": "세션이 만료되었습니다. 다른 사용자가 로그인했거나 다른 탭에서 로그인했습니다.",
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
                    current_app.logger.error(f"❌ User {username} not found in database")
                    return jsonify({"error": get_error_message("invalid_credentials")}), 401
                
                # Set user info in request object
                request.user = {
                    'id': user_row[0],
                    'username': username,
                    'role': user_row[1],
                    'display_name': user_row[2],
                    'session_id': token_session_id
                }
                
                current_app.logger.debug(f"✅ Token validation successful for user '{username}'")
                
            except sqlite3.Error as e:
                current_app.logger.error(f"❌ Database error in token validation: {str(e)}")
                return jsonify({"error": get_error_message("database_error")}), 500
            finally:
                if conn:
                    conn.close()
                    
        except jwt.ExpiredSignatureError:
            current_app.logger.info(f"⏰ Expired token for user")
            return jsonify({"error": get_error_message("token_expired")}), 401
        except jwt.InvalidTokenError:
            current_app.logger.warning(f"❌ Invalid token received")
            return jsonify({"error": get_error_message("invalid_token")}), 401
        except Exception as e:
            current_app.logger.error(f"❌ Unexpected error in token validation: {str(e)}")
            return jsonify({"error": get_error_message("unexpected_error")}), 500
            
        return f(*args, **kwargs)
    return wrapper

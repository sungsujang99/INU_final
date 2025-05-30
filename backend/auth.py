# auth.py
import datetime, sqlite3, jwt
from functools import wraps
from flask import request, jsonify, current_app
from passlib.hash import bcrypt
from .db import DB_NAME
from .error_messages import get_error_message

SECRET = "ChangeThisSecret!"  # 환경변수로 바꾸길 권장

def authenticate(username, password):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, hashed_password, role, display_name FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    conn.close()
    if row and bcrypt.verify(password, row[1]):
        return jwt.encode(
            {"sub": username,
             "user_id": row[0],
             "role": row[2],
             "display_name": row[3],
             "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=12)},
            SECRET, algorithm="HS256")
    return None

def token_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        hdr = request.headers.get("Authorization", "")
        if not hdr.startswith("Bearer "):
            return jsonify({"error": get_error_message("token_required")}), 401
        token = hdr.split()[1]
        try:
            decoded = jwt.decode(token, SECRET, algorithms=["HS256"])
            username = decoded['sub']
            
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
                    'display_name': user_row[2]
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

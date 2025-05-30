# auth.py
import datetime, sqlite3, jwt
from functools import wraps
from flask import request, jsonify
from passlib.hash import bcrypt
from .db import DB_NAME
from .error_messages import get_error_message

SECRET = "ChangeThisSecret!"  # 환경변수로 바꾸길 권장

def authenticate(username, password):
    conn = sqlite3.connect(DB_NAME)
    cur  = conn.cursor()
    cur.execute("SELECT id, hashed_password FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    conn.close()
    if row and bcrypt.verify(password, row[1]):
        return jwt.encode(
            {"sub": username,
             "user_id": row[0],
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
            # Set user info in request object
            request.user = {
                'id': decoded['user_id'],
                'username': decoded['sub']
            }
        except jwt.ExpiredSignatureError:
            return jsonify({"error": get_error_message("token_expired")}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": get_error_message("invalid_token")}), 401
        return f(*args, **kwargs)
    return wrapper

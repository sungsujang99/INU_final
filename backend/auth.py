# auth.py
import datetime, sqlite3, jwt
from functools import wraps
from flask import request, jsonify
from passlib.hash import bcrypt
from .db import DB_NAME

SECRET = "ChangeThisSecret!"  # 환경변수로 바꾸길 권장

def authenticate(username, password):
    conn = sqlite3.connect(DB_NAME)
    cur  = conn.cursor()
    cur.execute("SELECT hashed_password FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    conn.close()
    if row and bcrypt.verify(password, row[0]):
        return jwt.encode(
            {"sub": username,
             "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=12)},
            SECRET, algorithm="HS256")
    return None

def token_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        hdr = request.headers.get("Authorization", "")
        if not hdr.startswith("Bearer "):
            return jsonify({"error": "token required"}), 401
        token = hdr.split()[1]
        try:
            jwt.decode(token, SECRET, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "invalid token"}), 401
        return f(*args, **kwargs)
    return wrapper

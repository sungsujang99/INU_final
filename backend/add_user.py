import sqlite3
from passlib.hash import bcrypt as bcrypt_hasher # Use the same as in auth.py
import .db # Use absolute import

# Define valid roles
VALID_ROLES = ['admin', 'user', 'notouch']

def add_user_to_db(username, password, display_name=None, role=None):
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}")

    conn = sqlite3.connect(db.DB_NAME)
    cur = conn.cursor()

    hashed_pw = bcrypt_hasher.hash(password)
    # If display_name is not provided, use username
    display_name = display_name or username

    try:
        cur.execute(
            "INSERT INTO users (username, display_name, hashed_password, role) VALUES (?, ?, ?, ?)",
            (username, display_name, hashed_pw, role)
        )
        conn.commit()
        print(f"User '{username}' added successfully with role '{role}'.")
    except sqlite3.IntegrityError:
        print(f"Error: User '{username}' already exists.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        conn.close()

def list_users():
    """List all users and their roles (but not passwords)"""
    conn = sqlite3.connect(db.DB_NAME)
    cur = conn.cursor()
    try:
        cur.execute("SELECT username, display_name, role FROM users")
        users = cur.fetchall()
        print("\nCurrent Users:")
        print("Username | Display Name | Role")
        print("-" * 40)
        for user in users:
            print(f"{user[0]} | {user[1]} | {user[2]}")
    finally:
        conn.close()

if __name__ == "__main__":
    # --- IMPORTANT ---
    # After running this script ONCE to add the user,
    # it's a good practice to either:
    # 1. Delete this script, or
    # 2. Comment out the user creation lines below,
    # to avoid accidentally trying to re-add the user or leaving plain passwords in scripts.
    
    # --- Set your desired username and password here ---
    users_to_add = [
        {
            "username": "admin",
            "password": "admin123",
            "display_name": "Administrator",
            "role": "admin"
        },
        {
            "username": "user1",
            "password": "user123",
            "display_name": "Regular User",
            "role": "user"
        },
        {
            "username": "viewer1",
            "password": "viewer123",
            "display_name": "View Only User",
            "role": "notouch"
        }
    ]

    # Initialize database
    db.init_db()

    # Add all users
    for user in users_to_add:
        try:
            add_user_to_db(
                user["username"],
                user["password"],
                user["display_name"],
                user["role"]
            )
        except ValueError as e:
            print(f"Error adding user {user['username']}: {e}")

    # List all users
    list_users() 
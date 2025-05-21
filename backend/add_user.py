import sqlite3
from passlib.hash import bcrypt as bcrypt_hasher # Use the same as in auth.py
from .db import DB_NAME # Use relative import

def add_user_to_db(username, password, role=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    hashed_pw = bcrypt_hasher.hash(password)

    try:
        cur.execute(
            "INSERT INTO users (username, hashed_password, role) VALUES (?, ?, ?)",
            (username, hashed_pw, role)
        )
        conn.commit()
        print(f"User '{username}' added successfully.")
    except sqlite3.IntegrityError:
        print(f"Error: User '{username}' already exists.")
    except Exception as e:
        print(f"An error occurred: {e}")
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
    new_username = "admin"  # Replace with your desired username
    new_password = "admin123"  # Replace with your desired strong password
    user_role = "admin" # Optional, set to None if not using roles

    if new_username == "your_username" or new_password == "your_password":
        print("Please update new_username and new_password in the script before running.")
    else:
        # Make sure the database and tables are initialized first
        # You might need to run your main app once to trigger init_db()
        # or call init_db() here if it's safe to do so.
        from .db import init_db
        init_db() # Initialize the database first
        
        add_user_to_db(new_username, new_password, user_role) 
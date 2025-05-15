import sqlite3
import bcrypt
from db import DB_NAME, init_db

def setup_test():
    # Initialize the database
    init_db()
    
    # Create users table if it doesn't exist
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL
    )
    ''')
    
    # Add test user
    username = 'sungsujang99'
    password = 'ss273890'
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    cur.execute('INSERT OR REPLACE INTO users (username, password) VALUES (?, ?)',
                (username, hashed))
    
    # Verify user was added
    cur.execute('SELECT * FROM users WHERE username = ?', (username,))
    result = cur.fetchone()
    print(f"User added: {result[0]}")
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    setup_test() 
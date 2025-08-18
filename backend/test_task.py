#!/usr/bin/env python3
import sqlite3
import datetime
from db import DB_NAME, init_db

def create_test_task():
    """Create a test task and mark it as completed to test camera history."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    try:
        # First make sure we have a test user
        cur.execute("""
            INSERT OR IGNORE INTO users (username, display_name, hashed_password, role)
            VALUES ('test_user', 'Test User', 'test_hash', 'admin')
        """)
        
        # Get the user ID
        cur.execute("SELECT id FROM users WHERE username = 'test_user'")
        user_id = cur.fetchone()[0]
        
        # Current timestamp
        now = datetime.datetime.now().isoformat()
        
        # Insert a test task
        cur.execute("""
            INSERT INTO work_tasks (
                rack, slot, product_code, product_name, movement,
                quantity, cargo_owner, status, created_at, updated_at,
                start_time, end_time, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'A', 1, 'TEST001', 'Test Product', 'IN',
            1, 'Test Owner', 'done', now, now,
            now, now, user_id
        ))
        task_id = cur.lastrowid  # Fix: Use lastrowid instead of fetchone()
        print(f"Created task with ID: {task_id}")
        
        # Insert batch link
        batch_id = f"TEST_BATCH_{now}"
        cur.execute("""
            INSERT INTO batch_task_links (batch_id, task_id, created_by)
            VALUES (?, ?, ?)
        """, (batch_id, task_id, user_id))
        
        # Insert camera history
        cur.execute("""
            INSERT INTO camera_batch_history (
                batch_id, rack, slot, movement_type,
                start_time, end_time, product_code, product_name,
                quantity, cargo_owner, created_by, created_by_username,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            batch_id, 'A', 1, 'IN',
            now, now, 'TEST001', 'Test Product',
            1, 'Test Owner', user_id, 'test_user',
            'done', now, now
        ))
        
        conn.commit()
        print("✅ Test task created successfully!")
        
        # Verify camera history
        cur.execute("SELECT COUNT(*) FROM camera_batch_history")
        count = cur.fetchone()[0]
        print(f"📊 Camera history records: {count}")
        
        if count > 0:
            print("\n📝 Latest camera history entry:")
            cur.execute("""
                SELECT * FROM camera_batch_history 
                ORDER BY created_at DESC LIMIT 1
            """)
            row = cur.fetchone()
            print(f"  Rack: {row[2]}, Slot: {row[3]}")
            print(f"  Movement: {row[4]}")
            print(f"  Product: {row[8]} (x{row[9]})")
            print(f"  Time: {row[5]} → {row[6]}")
            print(f"  Status: {row[13]}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    # Initialize DB if needed
    init_db()
    # Create test task
    create_test_task() 
#!/usr/bin/env python3
import sqlite3
from db import DB_NAME

def check_camera_history():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Check if table exists
    cur.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='camera_batch_history';
    """)
    if not cur.fetchone():
        print("❌ camera_batch_history table does not exist!")
        return

    # Get table schema
    print("📋 Table Schema:")
    cur.execute("PRAGMA table_info(camera_batch_history);")
    for col in cur.fetchall():
        print(f"  {col['name']} ({col['type']})")

    # Get row count
    cur.execute("SELECT COUNT(*) FROM camera_batch_history")
    count = cur.fetchone()[0]
    print(f"\n📊 Total records: {count}")

    # Get latest records
    if count > 0:
        print("\n📝 Latest records:")
        cur.execute("""
            SELECT * FROM camera_batch_history 
            ORDER BY end_time DESC LIMIT 5
        """)
        rows = cur.fetchall()
        for row in rows:
            print(f"\nRecord {row['id']}:")
            print(f"  Rack {row['rack']}, Slot {row['slot']}")
            print(f"  Movement: {row['movement_type']}")
            print(f"  Time: {row['start_time']} → {row['end_time']}")
            print(f"  Product: {row['product_name']} (x{row['quantity']})")
            print(f"  Status: {row['status']}")
            print(f"  User: {row['created_by_username']}")

if __name__ == "__main__":
    check_camera_history() 
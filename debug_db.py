#!/usr/bin/env python3
import sqlite3
import os

DB_NAME = "database.db"  # Use the database in root directory

def check_tables():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # List all tables
    print("📚 Tables in database:")
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cur.fetchall()
    for table in tables:
        table_name = table['name']
        print(f"\n📋 Table: {table_name}")
        
        # Get table schema
        cur.execute(f"PRAGMA table_info({table_name});")
        columns = cur.fetchall()
        print("  Columns:")
        for col in columns:
            print(f"    {col['name']} ({col['type']})")
        
        # Get row count
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cur.fetchone()[0]
        print(f"  Row count: {count}")

        # Show sample data if exists
        if count > 0:
            cur.execute(f"SELECT * FROM {table_name} LIMIT 1")
            row = dict(cur.fetchone())
            print("  Sample row:")
            for key, value in row.items():
                print(f"    {key}: {value}")

    conn.close()

if __name__ == "__main__":
    if not os.path.exists(DB_NAME):
        print(f"❌ Database file not found: {DB_NAME}")
    else:
        print(f"✅ Found database: {DB_NAME}")
        check_tables() 
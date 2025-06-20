#!/usr/bin/env python3
import sqlite3
import json

# Connect to the database
db_path = "database.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== DEBUGGING DATABASE ENTRIES ===\n")

# Check product_logs for the coffee pot entries
print("1. Product Logs for coffee pot (5465433):")
cur.execute("""
    SELECT id, product_code, product_name, rack, slot, movement_type, 
           quantity, cargo_owner, timestamp, batch_id 
    FROM product_logs 
    WHERE product_code = '5465433' 
    ORDER BY timestamp DESC
""")
product_logs = cur.fetchall()

for i, row in enumerate(product_logs):
    print(f"   {i+1}. ID: {row['id']}, Rack: {row['rack']}, Slot: {row['slot']}, "
          f"Movement: {row['movement_type']}, Batch: {row['batch_id']}, "
          f"Timestamp: {row['timestamp']}")

print(f"\nTotal product_logs entries: {len(product_logs)}")

# Check work_tasks for the coffee pot entries
print("\n2. Work Tasks for coffee pot (5465433):")
cur.execute("""
    SELECT id, rack, slot, product_code, product_name, movement, 
           quantity, cargo_owner, status, created_at, updated_at,
           start_time, end_time
    FROM work_tasks 
    WHERE product_code = '5465433' 
    ORDER BY created_at DESC
""")
work_tasks = cur.fetchall()

for i, row in enumerate(work_tasks):
    print(f"   {i+1}. ID: {row['id']}, Rack: {row['rack']}, Slot: {row['slot']}, "
          f"Movement: {row['movement']}, Status: {row['status']}")
    print(f"       Start: {row['start_time']}, End: {row['end_time']}")

print(f"\nTotal work_tasks entries: {len(work_tasks)}")

# Check batch_task_links
print("\n3. Batch Task Links:")
if product_logs:
    batch_id = product_logs[0]['batch_id']
    cur.execute("""
        SELECT btl.id, btl.batch_id, btl.task_id, wt.rack, wt.slot, wt.movement, wt.status
        FROM batch_task_links btl
        LEFT JOIN work_tasks wt ON btl.task_id = wt.id
        WHERE btl.batch_id = ?
        ORDER BY btl.id
    """, (batch_id,))
    batch_links = cur.fetchall()
    
    for i, row in enumerate(batch_links):
        print(f"   {i+1}. Batch: {row['batch_id'][:8]}..., Task ID: {row['task_id']}, "
              f"Rack: {row['rack']}, Slot: {row['slot']}, Movement: {row['movement']}, "
              f"Status: {row['status']}")
    
    print(f"\nTotal batch_task_links entries: {len(batch_links)}")

# Test the actual activity logs query that's causing the issue
print("\n4. Activity Logs Query Result (same as API):")
cur.execute("""
    SELECT DISTINCT
        pl.id, pl.product_code, pl.product_name, pl.rack, pl.slot, 
        pl.movement_type, pl.quantity, pl.cargo_owner, pl.timestamp, pl.batch_id,
        wt.start_time, wt.end_time, wt.status as task_status
    FROM product_logs pl
    LEFT JOIN batch_task_links btl ON pl.batch_id = btl.batch_id
    LEFT JOIN work_tasks wt ON btl.task_id = wt.id 
    WHERE pl.id IS NOT NULL AND pl.product_code = '5465433'
    ORDER BY pl.timestamp DESC
""")
api_results = cur.fetchall()

for i, row in enumerate(api_results):
    print(f"   {i+1}. {row['rack']}{row['slot']} {row['movement_type']} - "
          f"Start: {row['start_time']}, End: {row['end_time']}, Status: {row['task_status']}")

print(f"\nTotal API results: {len(api_results)}")

conn.close()
print("\n=== DEBUG COMPLETE ===") 
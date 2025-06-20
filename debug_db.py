#!/usr/bin/env python3
import sqlite3
import json

# Connect to the database (using correct path)
db_path = "database.db"  # Root level database
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== INVESTIGATING DUPLICATE ENTRIES ===\n")

# Check all product_logs entries for coffee pot
print("1. All product_logs entries for coffee pot (5465433):")
cur.execute("""
    SELECT id, product_code, product_name, rack, slot, movement_type, 
           quantity, cargo_owner, timestamp, batch_id 
    FROM product_logs 
    WHERE product_code = '5465433' 
    ORDER BY timestamp DESC
""")
product_logs = cur.fetchall()

for i, row in enumerate(product_logs):
    print(f"   {i+1}. ID: {row['id']}, {row['rack']}{row['slot']} {row['movement_type']}, "
          f"Batch: {row['batch_id'][:8]}..., Timestamp: {row['timestamp']}")

print(f"\nTotal product_logs entries: {len(product_logs)}")

# Check unique batch_ids
unique_batches = set(row['batch_id'] for row in product_logs if row['batch_id'])
print(f"Unique batch IDs: {len(unique_batches)}")
for batch in unique_batches:
    print(f"   - {batch[:8]}...")

# Check work_tasks entries
print("\n2. All work_tasks entries for coffee pot (5465433):")
cur.execute("""
    SELECT id, rack, slot, product_code, movement, status, 
           start_time, end_time, created_at
    FROM work_tasks 
    WHERE product_code = '5465433' 
    ORDER BY created_at DESC
""")
work_tasks = cur.fetchall()

for i, row in enumerate(work_tasks):
    print(f"   {i+1}. ID: {row['id']}, {row['rack']}{row['slot']} {row['movement']}, "
          f"Status: {row['status']}, Created: {row['created_at']}")

print(f"\nTotal work_tasks entries: {len(work_tasks)}")

# The real issue: we need to filter by the LATEST batch or use DISTINCT properly
print("\n3. SOLUTION - Get latest entry per rack/slot combination:")
cur.execute("""
    SELECT DISTINCT
        pl.rack, pl.slot, pl.movement_type,
        MAX(pl.timestamp) as latest_timestamp,
        pl.product_code, pl.product_name
    FROM product_logs pl
    WHERE pl.product_code = '5465433'
    GROUP BY pl.rack, pl.slot, pl.movement_type, pl.product_code
    ORDER BY latest_timestamp DESC
""")
distinct_results = cur.fetchall()

print(f"Distinct rack/slot combinations: {len(distinct_results)}")
for i, row in enumerate(distinct_results):
    print(f"   {i+1}. {row['rack']}{row['slot']} {row['movement_type']} - Latest: {row['latest_timestamp']}")

conn.close()

print("\n=== CONCLUSION ===")
print("The issue is duplicate product_logs entries from multiple CSV uploads.")
print("We need to either:")
print("1. Clean up duplicate entries in the database, OR")
print("2. Modify the activity logs API to show only the latest entry per rack/slot") 
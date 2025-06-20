#!/usr/bin/env python3
import sqlite3
import json

# Connect to the database (using correct path)
db_path = "database.db"  # Root level database
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== TESTING FIXED QUERY ===\n")

# Test the FIXED activity logs query
print("Testing the FIXED query (with proper JOIN conditions):")
cur.execute("""
    SELECT 
        pl.id, pl.product_code, pl.product_name, pl.rack, pl.slot, 
        pl.movement_type, pl.quantity, pl.cargo_owner, pl.timestamp, pl.batch_id,
        wt.start_time, wt.end_time, wt.status as task_status
    FROM product_logs pl
    LEFT JOIN batch_task_links btl ON pl.batch_id = btl.batch_id
    LEFT JOIN work_tasks wt ON btl.task_id = wt.id 
        AND wt.rack = pl.rack 
        AND wt.slot = pl.slot 
        AND wt.movement = pl.movement_type
        AND wt.product_code = pl.product_code
    WHERE pl.product_code = '5465433'
    ORDER BY pl.timestamp DESC
""")
fixed_results = cur.fetchall()

print(f"FIXED query results: {len(fixed_results)} entries")
for i, row in enumerate(fixed_results):
    print(f"   {i+1}. {row['rack']}{row['slot']} {row['movement_type']} - "
          f"Start: {row['start_time']}, End: {row['end_time']}, Status: {row['task_status']}")

print(f"\n✅ Expected: 2 entries")
print(f"🔧 Actual: {len(fixed_results)} entries")

if len(fixed_results) == 2:
    print("✅ QUERY IS FIXED! Restart backend to apply changes.")
else:
    print("❌ Query still has issues - need to investigate further.")

conn.close() 
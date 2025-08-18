#!/usr/bin/env python3
import sqlite3
from db import DB_NAME

def check_work_tasks():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get task counts by status
    print("📊 Task counts by status:")
    cur.execute("""
        SELECT status, COUNT(*) as count 
        FROM work_tasks 
        GROUP BY status
    """)
    for row in cur.fetchall():
        print(f"  {row['status']}: {row['count']}")

    # Get latest tasks
    print("\n📝 Latest tasks:")
    cur.execute("""
        SELECT wt.*, btl.batch_id, u.username as created_by_username
        FROM work_tasks wt
        LEFT JOIN batch_task_links btl ON wt.id = btl.task_id
        LEFT JOIN users u ON wt.created_by = u.id
        ORDER BY wt.created_at DESC
        LIMIT 5
    """)
    tasks = cur.fetchall()
    for task in tasks:
        print(f"\nTask {task['id']}:")
        print(f"  Rack {task['rack']}, Slot {task['slot']}")
        print(f"  Movement: {task['movement']}")
        print(f"  Status: {task['status']}")
        print(f"  Created: {task['created_at']}")
        print(f"  Updated: {task['updated_at']}")
        print(f"  By: {task['created_by_username']}")
        if task['start_time']:
            print(f"  Started: {task['start_time']}")
        if task['end_time']:
            print(f"  Ended: {task['end_time']}")

    conn.close()

if __name__ == "__main__":
    check_work_tasks() 
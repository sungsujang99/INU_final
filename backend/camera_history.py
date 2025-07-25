import sqlite3
import logging
from .db import DB_NAME

# Set up basic logging for this module
logger = logging.getLogger(__name__)

def store_camera_batch(history_data):
    """Store a completed task's details in the permanent camera_batch_history table."""
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO camera_batch_history (
                batch_id, rack, slot, movement_type, start_time, end_time,
                product_code, product_name, quantity, cargo_owner,
                created_by, created_by_username, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            history_data.get('batch_id'),
            history_data.get('rack'),
            history_data.get('slot'),
            history_data.get('movement'),
            history_data.get('start_time'),
            history_data.get('end_time'),
            history_data.get('product_code'),
            history_data.get('product_name'),
            history_data.get('quantity'),
            history_data.get('cargo_owner'),
            history_data.get('created_by'),
            history_data.get('created_by_username'),
            history_data.get('status'),
            history_data.get('created_at'),
            history_data.get('updated_at')
        ))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"DATABASE ERROR in store_camera_batch: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def get_camera_history(limit=50):
    """Retrieve camera batch history logs from the database."""
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM camera_batch_history ORDER BY end_time DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        logger.error(f"DATABASE ERROR in get_camera_history: {e}")
        return [] # Return empty list on error
    finally:
        if conn:
            conn.close() 
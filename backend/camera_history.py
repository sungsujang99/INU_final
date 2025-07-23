import sqlite3
import logging
from .db import DB_NAME

# Set up basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def store_camera_batch(history_data):
    """Store camera batch job history in the database"""
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
        logger.info(f"Stored camera batch history for rack {history_data.get('rack')} slot {history_data.get('slot')}")

    except Exception as e:
        logger.error(f"Error storing camera batch history: {str(e)}")
        if conn:
            conn.rollback()
        # We don't re-raise here to avoid crashing the worker thread
    finally:
        if conn:
            conn.close()

def get_camera_history(batch_id=None, limit=100):
    """Get camera batch job history from the database"""
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        query = "SELECT * FROM camera_batch_history"
        params = []

        if batch_id:
            query += " WHERE batch_id = ?"
            params.append(batch_id)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        return [dict(row) for row in rows]

    except Exception as e:
        logger.error(f"Error getting camera history: {str(e)}")
        return []
    finally:
        if conn:
            conn.close() 
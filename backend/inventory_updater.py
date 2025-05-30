# inventory_updater.py
"""
Handles inventory database updates when tasks are completed
"""

import sqlite3, datetime, logging
from .db import DB_NAME
from flask import current_app

def _now() -> str:
    """ISO-8601(초 단위) 타임스탬프"""
    return datetime.datetime.now().isoformat(timespec="seconds")

def update_inventory_on_done(task: dict, cur=None):
    """
    Update the inventory database when a task is completed (done signal received).
    This updates the physical state of the equipment in current_inventory table.
    
    Args:
        task (dict): Task dictionary containing rack, slot, movement, etc.
        cur (sqlite3.Cursor, optional): Database cursor. If not provided, creates a new connection.
    """
    logger = current_app.logger if current_app else logging.getLogger(__name__)
    logger.debug("update_inventory_on_done: Updating inventory for task: %s", task)
    
    rack = task['rack'].upper()
    slot = int(task['slot'])
    movement = task['movement'].upper()
    product_code = task['product_code']
    product_name = task['product_name']
    quantity = int(task['quantity'])
    cargo_owner = task.get('cargo_owner', '')

    own_connection = False
    conn = None
    
    try:
        if cur is None:
            conn = sqlite3.connect(DB_NAME, timeout=10)
            cur = conn.cursor()
            own_connection = True

        if movement == "IN":
            # Insert new record for IN operation
            cur.execute("""
                INSERT INTO current_inventory
                  (product_code, product_name, rack, slot,
                   total_quantity, cargo_owner, last_update)
                VALUES (?,?,?,?,?,?,?)
            """, (product_code, product_name, rack, slot, quantity, cargo_owner, _now()))
            logger.debug("update_inventory_on_done: Inserted new record for IN at %s-%d", rack, slot)
        elif movement == "OUT":
            # Delete record for OUT operation
            cur.execute("DELETE FROM current_inventory WHERE rack=? AND slot=?", (rack, slot))
            logger.debug("update_inventory_on_done: Deleted record for OUT at %s-%d", rack, slot)

        if own_connection:
            conn.commit()
            
        logger.debug("update_inventory_on_done: Successfully updated inventory")
        return True
    except Exception as e:
        logger.error("update_inventory_on_done: Exception occurred: %s", str(e), exc_info=True)
        if own_connection and conn:
            conn.rollback()
        return False
    finally:
        if own_connection and conn:
            conn.close() 
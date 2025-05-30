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

def update_inventory_on_done(rack: str, slot: int, movement: str, product_code: str, product_name: str, quantity: int, cargo_owner: str):
    """
    Update the inventory database when a task is completed (done signal received).
    This updates the physical state of the equipment in current_inventory table.
    """
    logger = current_app.logger if current_app else logging.getLogger(__name__)
    logger.debug("update_inventory_on_done: Updating inventory for rack=%s, slot=%d, movement=%s", rack, slot, movement)
    
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME, timeout=10)
        cur = conn.cursor()

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

        conn.commit()
        logger.debug("update_inventory_on_done: Successfully updated inventory")
        return True
    except Exception as e:
        logger.error("update_inventory_on_done: Exception occurred: %s", str(e), exc_info=True)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close() 
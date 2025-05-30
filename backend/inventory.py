# inventory.py
"""
재고( current_inventory )와 이력( product_logs )을 관리하고
각 레코드를 랙별 작업 큐로 전달하는 모듈.
"""

import sqlite3, datetime, logging
from .db import DB_NAME
from .task_queue import enqueue_work_task          # ← 큐 모듈 import
from flask import current_app # Added for logging
from .error_messages import get_error_message


# ────────────────────────────────────────────────
def _now() -> str:
    """ISO-8601(초 단위) 타임스탬프"""
    return datetime.datetime.now().isoformat(timespec="seconds")


# ────────────────────────────────────────────────
def add_records(records: list[dict], batch_id: str = None, user_info: dict = None):
    """
    records 예시:
    {
      "product_code": "ABC-001",
      "product_name": "Cable",
      "rack":         "A",           # 'A'/'B'/'C'
      "slot":         17,            # 1-80
      "movement":     "IN",          # 또는 'OUT'
      "quantity":     10,
      "cargo_owner":  "Acme"
    }

    user_info 예시:
    {
      "id": 1,
      "username": "admin"
    }
    """
    if not user_info or 'id' not in user_info or 'username' not in user_info:
        raise ValueError(get_error_message("invalid_credentials"))

    logger = current_app.logger if current_app else logging.getLogger(__name__)
    logger.debug("add_records: Called with %s records", len(records))
    
    conn = None
    try:
        logger.debug("add_records: Connecting to DB: %s", DB_NAME)
        conn = sqlite3.connect(DB_NAME, timeout=10)
        logger.debug("add_records: DB Connected. Creating cursor.")
        cur = conn.cursor()
        logger.debug("add_records: Cursor created.")

        # First pass: collect all operations and validate
        slots_to_be_emptied = set()  # Slots that will be emptied by OUT operations
        slots_to_be_filled = set()   # Slots that will be filled by IN operations
        current_inventory = {}       # Track current inventory state

        # Get current inventory state
        cur.execute("SELECT rack, slot, product_code, total_quantity FROM current_inventory")
        for row in cur.fetchall():
            rack, slot, product_code, quantity = row
            current_inventory[(rack, slot)] = (product_code, quantity)

        # Validate all records first
        for record in records:
            rack = record['rack'].upper()
            slot = int(record['slot'])
            movement = record['movement'].upper()
            
            if movement == 'IN':
                if (rack, slot) in current_inventory:
                    return False, get_error_message("slot_occupied", rack=rack, slot=slot)
                if (rack, slot) in slots_to_be_filled:
                    return False, get_error_message("multiple_in_operations", rack=rack, slot=slot)
                slots_to_be_filled.add((rack, slot))
            
            elif movement == 'OUT':
                if (rack, slot) not in current_inventory:
                    return False, get_error_message("no_inventory", rack=rack, slot=slot)
                if (rack, slot) in slots_to_be_emptied:
                    return False, get_error_message("multiple_out_operations", rack=rack, slot=slot)
                slots_to_be_emptied.add((rack, slot))
            
            else:
                return False, get_error_message("invalid_movement", movement=movement)

        # All records validated, proceed with insertion
        now = _now()
        generated_task_ids = []  # To store task IDs for batch linking

        for i, record in enumerate(records):
            # Add to product_logs with user info
            cur.execute("""
                INSERT INTO product_logs
                (product_code, product_name, rack, slot, movement_type,
                 quantity, cargo_owner, timestamp, batch_id, user_id, username)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record['product_code'],
                record['product_name'],
                record['rack'].upper(),
                int(record['slot']),
                record['movement'].upper(),
                int(record['quantity']),
                record.get('cargo_owner', ''),
                now,
                batch_id,
                user_info['id'],
                user_info['username']
            ))

            # Enqueue task with user info
            task_id = enqueue_work_task(record, user_info, conn, cur)
            if task_id:
                generated_task_ids.append(task_id)
                logger.debug("add_records: Task enqueued for record %d with task_id: %s.", i, task_id)

            # If this is part of a batch, link the task
            if batch_id and task_id:
                cur.execute(
                    "INSERT INTO batch_task_links (batch_id, task_id, created_by) VALUES (?, ?, ?)",
                    (batch_id, task_id, user_info['id'])
                )

        logger.debug("add_records: All records processed. Attempting to commit.")
        conn.commit()
        logger.debug("add_records: Commit successful.")
        return True, ""
    except Exception as e:
        logger.error("add_records: Exception occurred: %s", str(e), exc_info=True)
        if conn:
            logger.debug("add_records: Rolling back transaction.")
            conn.rollback()
            logger.debug("add_records: Rollback complete.")
        return False, get_error_message("unexpected_error")
    finally:
        if conn:
            logger.debug("add_records: Closing DB connection.")
            conn.close()
            logger.debug("add_records: DB connection closed.")
        else:
            logger.debug("add_records: No DB connection to close (was None).")

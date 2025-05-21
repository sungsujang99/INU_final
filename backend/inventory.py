# inventory.py
"""
재고( current_inventory )와 이력( product_logs )을 관리하고
각 레코드를 랙별 작업 큐로 전달하는 모듈.
"""

import sqlite3, datetime
from .db import DB_NAME
from .task_queue import enqueue_task          # ← 큐 모듈 import
from flask import current_app # Added for logging


# ────────────────────────────────────────────────
def _now() -> str:
    """ISO-8601(초 단위) 타임스탬프"""
    return datetime.datetime.now().isoformat(timespec="seconds")


# ────────────────────────────────────────────────
def add_records(records: list[dict], batch_id: str = None):
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
    """
    logger = current_app.logger if current_app else logging.getLogger(__name__)
    logger.debug("add_records: Called with %s records", len(records))
    
    conn = None
    try:
        logger.debug("add_records: Connecting to DB: %s", DB_NAME)
        conn = sqlite3.connect(DB_NAME, timeout=10)
        logger.debug("add_records: DB Connected. Creating cursor.")
        cur = conn.cursor()
        logger.debug("add_records: Cursor created.")

        for i, rec in enumerate(records):
            logger.debug("add_records: Processing record %d: %s", i, rec)
            # ---------- 파싱 ----------
            pc, name = rec["product_code"], rec["product_name"]
            rack = rec["rack"].upper()
            slot = int(rec["slot"])
            mv = rec["movement"].upper()         # 'IN' / 'OUT'
            qty = int(rec["quantity"])
            owner = rec.get("cargo_owner", "")
            logger.debug("add_records: Parsed record %d: pc=%s, rack=%s, slot=%d, mv=%s, qty=%d", i, pc, rack, slot, mv, qty)

            # ---------- Pre-operation Validation ----------
            logger.debug("add_records: Selecting from current_inventory for validation %d (rack=%s, slot=%s)...", i, rack, slot)
            cur.execute("""
                SELECT id, product_code, total_quantity
                  FROM current_inventory
                 WHERE rack=? AND slot=?
            """, (rack, slot))
            row_for_validation = cur.fetchone()
            logger.debug("add_records: Validation SELECT for record %d. Row: %s", i, row_for_validation)

            if mv == "IN":
                if row_for_validation: # Slot is occupied by ANY product
                    error_msg = f"Slot {rack}-{slot} is already occupied by product '{row_for_validation[1]}' (quantity: {row_for_validation[2]}). Slot must be empty for 'IN' operation."
                    logger.error("add_records: Validation failed for record %d: %s", i, error_msg)
                    return False, error_msg
            elif mv == "OUT":
                if not row_for_validation: # Slot is empty
                    error_msg = f"Cannot 'OUT' from empty slot {rack}-{slot} (no record in current_inventory)."
                    logger.error("add_records: Validation failed for record %d: %s", i, error_msg)
                    return False, error_msg
                if row_for_validation[1] != pc: # Product mismatch
                    error_msg = f"Product mismatch in slot {rack}-{slot}. Slot contains '{row_for_validation[1]}', but tried to 'OUT' '{pc}'."
                    logger.error("add_records: Validation failed for record %d: %s", i, error_msg)
                    return False, error_msg
            
            logger.debug("add_records: Pre-operation validation passed for record %d.", i)

            # ---------- product_logs INSERT ----------
            logger.debug("add_records: Inserting into product_logs for record %d...", i)
            cur.execute("""
                INSERT INTO product_logs
                  (product_code, product_name, rack, slot,
                   movement_type, quantity, cargo_owner, timestamp, batch_id)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (pc, name, rack, slot, mv, qty, owner, _now(), batch_id))
            logger.debug("add_records: Inserted into product_logs for record %d.", i)

            # ---------- 장치 명령을 큐에 넣기 ----------
            cmd_val = slot  # Arduino expects the slot number directly
            if mv == "OUT":
                cmd_val *= -1 # Prepend '-' for OUT operations
            logger.debug("add_records: Enqueuing task for record %d: rack=%s, cmd_val=%s", i, rack, str(cmd_val))
            enqueue_task(rack, cmd_val, wait=True) # Pass cmd_val as int
            logger.debug("add_records: Task enqueued for record %d.", i)

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
        return False, str(e)
    finally:
        if conn:
            logger.debug("add_records: Closing DB connection.")
            conn.close()
            logger.debug("add_records: DB connection closed.")
        else:
            logger.debug("add_records: No DB connection to close (was None).")

def update_inventory_on_done(rack: str, slot: int, movement: str, product_code: str, product_name: str, quantity: int, cargo_owner: str):
    """
    Update the inventory database when a task is completed (done signal received)
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

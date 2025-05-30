# task_queue.py  ─────────────────────────────────────────────
import queue, threading, time, logging, sqlite3, datetime
from typing import Optional
# Use DEFAULT_MAX_ECHO_ATTEMPTS from serial_io for regular commands
from .serial_io import serial_mgr, DEFAULT_MAX_ECHO_ATTEMPTS
from flask import current_app
from .inventory_updater import update_inventory_on_done
from .db import DB_NAME
from .error_messages import get_error_message

io = None                           # SocketIO 인스턴스 홀더
def set_socketio(sock):             # app.py 가 주입
    global io; io = sock

# --- DB Task Management ---
def enqueue_work_task(task, user_info, conn=None, cur=None):
    now = datetime.datetime.now().isoformat(timespec="seconds")
    
    own_connection = False
    if conn is None or cur is None:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        own_connection = True

    new_task_id = None
    try:
        # Add start_time and end_time columns, initially NULL
        cur.execute("""
            INSERT INTO work_tasks
            (rack, slot, product_code, product_name, movement, quantity, cargo_owner, status, 
             created_at, updated_at, start_time, end_time, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, NULL, NULL, ?)
        """, (
            task['rack'].upper(),
            int(task['slot']),
            task['product_code'],
            task['product_name'],
            task['movement'].upper(),
            int(task['quantity']),
            task.get('cargo_owner', ''),
            now, now,
            user_info['id']
        ))
        new_task_id = cur.lastrowid
        if own_connection:
            conn.commit()
        
        logger = current_app.logger if current_app else logging.getLogger(__name__)
        logger.info(f"[enqueue_work_task] Task enqueued with ID: {new_task_id}. Attempting to emit.")

        if io and new_task_id:
            io.emit("task_status_changed", {
                "id": new_task_id, 
                "status": "pending", 
                "action": "created", 
                "rack": task['rack'].upper(), 
                "slot": int(task['slot']), 
                "movement": task['movement'].upper(),
                "created_by": user_info['username']  # Include username in the event
            })
            logger.info(f"[enqueue_work_task] Emitted task_status_changed for new task ID: {new_task_id} (pending, no batch_id yet)")

    finally:
        if own_connection:
            conn.close()
    return new_task_id

def set_task_status(task_id, status):
    now = datetime.datetime.now().isoformat(timespec="seconds")
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    # Update timestamps based on status
    if status == 'in_progress':
        # When task starts, set start_time
        cur.execute("""
            UPDATE work_tasks 
            SET status=?, updated_at=?, start_time=? 
            WHERE id=?
        """, (status, now, now, task_id))
    elif status == 'done' or status.startswith('failed_'):
        # When task ends (success or failure), set end_time
        cur.execute("""
            UPDATE work_tasks 
            SET status=?, updated_at=?, end_time=? 
            WHERE id=?
        """, (status, now, now, task_id))
    else:
        # For other status changes, just update status and updated_at
        cur.execute("""
            UPDATE work_tasks 
            SET status=?, updated_at=? 
            WHERE id=?
        """, (status, now, task_id))
    
    conn.commit()
    
    task_details_for_event = {"id": task_id, "status": status}
    
    if status != 'pending': 
        cur.execute("""
            SELECT wt.id, wt.rack, wt.slot, wt.movement, wt.product_name, wt.product_code, 
                   wt.start_time, wt.end_time, btl.batch_id 
            FROM work_tasks wt
            LEFT JOIN batch_task_links btl ON wt.id = btl.task_id
            WHERE wt.id=?
        """, (task_id,))
        row = cur.fetchone()
        if row:
            columns = [desc[0] for desc in cur.description]
            fetched_details = dict(zip(columns, row))
            task_details_for_event.update(fetched_details) 
            
    conn.close()

    if io:
        io.emit("task_status_changed", task_details_for_event)
        logger = current_app.logger if current_app else logging.getLogger(__name__)
        logger.info(f"[set_task_status] Emitted task_status_changed: {task_details_for_event}")

def get_next_pending_task(): # Fetches only 'pending' tasks
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM work_tasks WHERE status='pending' ORDER BY created_at ASC LIMIT 1")
    row = cur.fetchone()
    
    if row:
        columns = [desc[0] for desc in cur.description]
        conn.close()
        return dict(zip(columns, row))
    conn.close()
    return None

def get_task_by_id(task_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM work_tasks WHERE id=?", (task_id,))
    row = cur.fetchone()
    columns = [desc[0] for desc in cur.description]
    conn.close()
    if row:
        return dict(zip(columns, row))
    return None

# --- Worker Thread ---
class GlobalWorker(threading.Thread):
    def __init__(self):
        super().__init__()
        self.daemon = True

    def run(self):
        logger = current_app.logger if current_app else logging.getLogger(__name__)
        main_equipment_id = "M"
        main_done_token = b"fin"
        rack_done_token = b"done"

        while True:
            task = get_next_pending_task()
            if not task:
                time.sleep(1)
                continue

            task_id = task['id']
            target_rack_id = task['rack'].upper()
            current_slot = int(task['slot'])
            movement = task['movement'].upper()
            
            logger.info(f"[Worker] Picked task {task_id}: {movement} for {target_rack_id}-{current_slot}. Setting to in_progress.")
            set_task_status(task_id, 'in_progress')

            final_task_status = None
            physical_op_successful = False

            try:
                # --- M Command Generation ---
                cmd_for_m = "0"
                rack_to_num_map = {'A': 1, 'B': 2, 'C': 3}
                rack_numeric_id = rack_to_num_map.get(target_rack_id)

                if rack_numeric_id is None:
                    logger.error(f"[Worker] Task {task_id}: Unknown target_rack_id '{target_rack_id}' for M cmd gen.")
                    final_task_status = 'failed_invalid_rack_for_m'
                else:
                    m_base_val = rack_numeric_id * 100 + current_slot
                    cmd_for_m = str(m_base_val) if movement == 'IN' else str(-m_base_val)
                # --- End M Command Generation ---
                
                # Rack commands
                cmd_for_rack = str(current_slot) if movement == 'IN' else str(-current_slot)

                logger.info(f"[Worker] Task {task_id}: M Cmd: '{cmd_for_m}', Rack Cmd: '{cmd_for_rack}'")

                if final_task_status: # Error from M command generation
                    pass # Skip to end
                elif not serial_mgr.enabled:
                    logger.warning(f"[Worker] Task {task_id}: {get_error_message('serial_disabled')}")
                    physical_op_successful = True
                
                elif movement == 'IN':
                    # 1. Main equipment (M) delivers to rack approach area
                    if main_equipment_id not in serial_mgr.ports:
                        logger.error(f"[Worker] Task {task_id} (IN): {get_error_message('failed_m_not_found')}")
                        final_task_status = 'failed_m_not_found'
                    else:
                        logger.info(f"[Worker] Task {task_id} (IN) - M Op: Cmd '{cmd_for_m}' to '{main_equipment_id}'.")
                        res_m = serial_mgr.send(main_equipment_id, cmd_for_m, wait_done=True, done_token=main_done_token)
                        if res_m["status"] == "done":
                            logger.info(f"[Worker] Task {task_id} (IN) - M Op SUCCESS.")
                            # 2. Target rack stores item
                            if target_rack_id not in serial_mgr.ports:
                                logger.error(f"[Worker] Task {task_id} (IN): {get_error_message('failed_rack_not_found')}")
                                final_task_status = 'failed_rack_not_found'
                            else:
                                logger.info(f"[Worker] Task {task_id} (IN) - Rack Op: Cmd '{cmd_for_rack}' to '{target_rack_id}'.")
                                res_rack = serial_mgr.send(target_rack_id, cmd_for_rack, wait_done=True, done_token=rack_done_token)
                                if res_rack["status"] == "done":
                                    logger.info(f"[Worker] Task {task_id} (IN) - Rack Op SUCCESS.")
                                    physical_op_successful = True
                                else:
                                    final_task_status = 'failed_rack_echo' if res_rack["status"] == "echo_error_max_retries" else 'failed_rack_timeout'
                                    logger.error(f"[Worker] Task {task_id} (IN) - Rack Op FAILED: {get_error_message(final_task_status)}")
                        else:
                            final_task_status = 'failed_m_echo' if res_m["status"] == "echo_error_max_retries" else 'failed_m_timeout'
                            logger.error(f"[Worker] Task {task_id} (IN) - M Op FAILED: {get_error_message(final_task_status)}")

                elif movement == 'OUT':
                    # 1. Target rack dispenses item to approach area
                    if target_rack_id not in serial_mgr.ports:
                        logger.error(f"[Worker] Task {task_id} (OUT): {get_error_message('failed_rack_not_found')}")
                        final_task_status = 'failed_rack_not_found'
                    else:
                        logger.info(f"[Worker] Task {task_id} (OUT) - Rack Op: Cmd '{cmd_for_rack}' to '{target_rack_id}'.")
                        res_rack = serial_mgr.send(target_rack_id, cmd_for_rack, wait_done=True, done_token=rack_done_token)
                        if res_rack["status"] == "done":
                            logger.info(f"[Worker] Task {task_id} (OUT) - Rack Op SUCCESS.")
                            # 2. Main equipment (M) collects item
                            if main_equipment_id not in serial_mgr.ports:
                                logger.error(f"[Worker] Task {task_id} (OUT): {get_error_message('failed_m_not_found')}")
                                final_task_status = 'failed_m_not_found'
                            else:
                                logger.info(f"[Worker] Task {task_id} (OUT) - M Op: Cmd '{cmd_for_m}' to '{main_equipment_id}'.")
                                res_m = serial_mgr.send(main_equipment_id, cmd_for_m, wait_done=True, done_token=main_done_token)
                                if res_m["status"] == "done":
                                    logger.info(f"[Worker] Task {task_id} (OUT) - M Op SUCCESS.")
                                    physical_op_successful = True
                                else:
                                    final_task_status = 'failed_m_echo' if res_m["status"] == "echo_error_max_retries" else 'failed_m_timeout'
                                    logger.error(f"[Worker] Task {task_id} (OUT) - M Op FAILED: {get_error_message(final_task_status)}")
                        else:
                            final_task_status = 'failed_rack_echo' if res_rack["status"] == "echo_error_max_retries" else 'failed_rack_timeout'
                            logger.error(f"[Worker] Task {task_id} (OUT) - Rack Op FAILED: {get_error_message(final_task_status)}")
                else:
                    logger.error(f"[Worker] Task {task_id}: {get_error_message('failed_unknown_movement')}")
                    final_task_status = 'failed_unknown_movement'
                        
            except Exception as e:
                logger.error(f"[Worker] Task {task_id}: {get_error_message('failed_exception')}: {e}", exc_info=True)
                final_task_status = 'failed_exception'

            # Post-operation: Update inventory and set final task status
            if physical_op_successful:
                logger.info(f"[Worker] Task {task_id}: Physical ops successful. Updating inventory.")
                inventory_update_success = update_inventory_on_done(
                    task['rack'],
                    int(task['slot']),
                    task['movement'].upper(),
                    task['product_code'],
                    task['product_name'],
                    int(task['quantity']),
                    task.get('cargo_owner', '')
                )
                if inventory_update_success:
                    final_task_status = 'done'
                    logger.info(f"[Worker] Task {task_id}: Inventory updated. Marked 'done'.")
                else:
                    final_task_status = 'failed_inventory_update'
                    logger.error(f"[Worker] Task {task_id}: {get_error_message('failed_inventory_update')}")
            
            if final_task_status:
                set_task_status(task_id, final_task_status)
            else:
                logger.error(f"[Worker] Task {task_id}: {get_error_message('failed_exception')}")
                set_task_status(task_id, 'failed_exception')
            
            time.sleep(0.1)

def start_global_worker():
    worker = GlobalWorker()
    worker.start()

# --- API Helper ---
def get_work_tasks_by_status(status=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    base_query = "SELECT wt.*, btl.batch_id FROM work_tasks wt LEFT JOIN batch_task_links btl ON wt.id = btl.task_id"
    
    if status:
        query = f"{base_query} WHERE wt.status=? ORDER BY wt.created_at ASC"
        cur.execute(query, (status,))
    else:
        query = f"{base_query} ORDER BY wt.created_at ASC"
        cur.execute(query)
        
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    conn.close()
    return [dict(zip(columns, row)) for row in rows]

def get_pending_task_counts():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    # Count pending IN tasks
    cur.execute("SELECT COUNT(*) FROM work_tasks WHERE status='pending' AND movement='IN'")
    pending_in_count = cur.fetchone()[0]
    
    # Count pending OUT tasks
    cur.execute("SELECT COUNT(*) FROM work_tasks WHERE status='pending' AND movement='OUT'")
    pending_out_count = cur.fetchone()[0]
    
    conn.close()
    return {"pending_in_count": pending_in_count, "pending_out_count": pending_out_count}

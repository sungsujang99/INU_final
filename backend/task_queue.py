# task_queue.py  ─────────────────────────────────────────────
import queue, threading, time, logging, sqlite3, datetime
from typing import Optional
# Use DEFAULT_MAX_ECHO_ATTEMPTS from serial_io for regular commands
from .serial_io import serial_mgr, DEFAULT_MAX_ECHO_ATTEMPTS
from flask import current_app
from .inventory_updater import update_inventory_on_done
from .db import DB_NAME

io = None                           # SocketIO 인스턴스 홀더
def set_socketio(sock):             # app.py 가 주입
    global io; io = sock

# --- DB Task Management ---
def enqueue_work_task(task, conn=None, cur=None):
    now = datetime.datetime.now().isoformat(timespec="seconds")
    
    own_connection = False
    if conn is None or cur is None:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        own_connection = True

    new_task_id = None
    try:
        cur.execute("""
            INSERT INTO work_tasks
            (rack, slot, product_code, product_name, movement, quantity, cargo_owner, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
        """, (
            task['rack'].upper(),
            int(task['slot']),
            task['product_code'],
            task['product_name'],
            task['movement'].upper(),
            int(task['quantity']),
            task.get('cargo_owner', ''),
            now, now
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
                "movement": task['movement'].upper()
                # batch_id will be added by set_task_status for subsequent events
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
    cur.execute("UPDATE work_tasks SET status=?, updated_at=? WHERE id=?", (status, now, task_id))
    conn.commit()
    
    task_details_for_event = {"id": task_id, "status": status}
    
    if status != 'pending': 
        cur.execute("""
            SELECT wt.id, wt.rack, wt.slot, wt.movement, wt.product_name, wt.product_code, btl.batch_id 
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
            
            logger.info(f"[Worker] Picked task {task_id}: {movement} for {target_rack_id}-{current_slot}")
            set_task_status(task_id, 'in_progress')

            final_task_status = None
            operation_successful_on_rack = False

            try:
                if not serial_mgr.enabled:
                    logger.warning(f"[Worker] Task {task_id}: Serial communication is DISABLED. Simulating successful rack operation.")
                    operation_successful_on_rack = True # Simulate for inventory update test
                
                elif target_rack_id not in serial_mgr.ports:
                    logger.error(f"[Worker] Task {task_id}: Target rack '{target_rack_id}' not found.")
                    final_task_status = 'failed_port_not_found'
                
                else:
                    # Generate command for the target rack
                    rack_command = str(current_slot) if movement == 'IN' else str(-current_slot)
                    logger.info(f"[Worker] Task {task_id}: Sending command '{rack_command}' to rack '{target_rack_id}'.")
                    
                    res_rack = serial_mgr.send(
                        target_rack_id,
                        rack_command,
                        wait_done=True,
                        done_token=rack_done_token,
                        custom_max_echo_attempts=DEFAULT_MAX_ECHO_ATTEMPTS # Use default attempts
                    )
                    rack_serial_status = res_rack["status"]
                    logger.info(f"[Worker] Task {task_id}: Rack '{target_rack_id}' serial response status: {rack_serial_status}")

                    if rack_serial_status == "done":
                        operation_successful_on_rack = True
                    elif rack_serial_status == "echo_error_max_retries":
                        final_task_status = 'failed_echo'
                    elif rack_serial_status == "timeout_after_echo":
                        final_task_status = 'failed_timeout_after_echo'
                    else: # Other unhandled serial statuses
                        final_task_status = f'failed_serial_{rack_serial_status}'
                        logger.warning(f"[Worker] Task {task_id}: Unhandled serial status '{rack_serial_status}' from rack '{target_rack_id}'.")
            
            except Exception as e:
                logger.error(f"[Worker] Task {task_id}: Exception during processing: {e}", exc_info=True)
                final_task_status = 'failed_exception'

            # Post-operation: Update inventory and set final status
            if operation_successful_on_rack:
                logger.info(f"[Worker] Task {task_id}: Rack operation successful. Updating inventory.")
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
                    final_task_status = 'done' # Final success state
                    logger.info(f"[Worker] Task {task_id}: Inventory updated. Task marked 'done'.")
                else:
                    final_task_status = 'failed_inventory_update'
                    logger.error(f"[Worker] Task {task_id}: Inventory update FAILED. Task marked 'failed_inventory_update'.")
            
            # Ensure a status is always set
            if final_task_status:
                set_task_status(task_id, final_task_status)
            elif not operation_successful_on_rack: # Should have been caught by specific errors
                logger.error(f"[Worker] Task {task_id}: Operation not successful but no specific error status set. Defaulting to 'failed_exception'.")
                set_task_status(task_id, 'failed_exception')
            
            time.sleep(0.1) # Loop delay

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

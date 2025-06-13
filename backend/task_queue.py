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
            operation_start_time = None
            operation_end_time = None

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
                
                # Rack commands
                cmd_for_rack = str(current_slot) if movement == 'IN' else str(-current_slot)

                logger.info(f"[Worker] Task {task_id}: M Cmd: '{cmd_for_m}', Rack Cmd: '{cmd_for_rack}'")

                if final_task_status: # Error from M command generation
                    pass # Skip to end
                elif not serial_mgr.enabled:
                    logger.warning(f"[Worker] Task {task_id}: {get_error_message('serial_disabled')}")
                    physical_op_successful = True
                    operation_start_time = datetime.datetime.now().isoformat(timespec="seconds")
                    operation_end_time = operation_start_time
                
                elif movement == 'IN':
                    # Record start time before first equipment command
                    operation_start_time = datetime.datetime.now().isoformat(timespec="seconds")
                    
                    # 1. Main equipment (M) delivers to rack approach area
                    if not serial_mgr.send(main_equipment_id, cmd_for_m, wait_done=True, done_token=main_done_token):
                        final_task_status = 'failed_m_echo'
                    # 2. Rack receives from approach area
                    elif not serial_mgr.send(target_rack_id, cmd_for_rack, wait_done=True, done_token=rack_done_token):
                        final_task_status = 'failed_rack_echo'
                    else:
                        physical_op_successful = True
                        # Record end time after last equipment response
                        operation_end_time = datetime.datetime.now().isoformat(timespec="seconds")
                
                elif movement == 'OUT':
                    # Record start time before first equipment command
                    operation_start_time = datetime.datetime.now().isoformat(timespec="seconds")
                    
                    # 1. Rack delivers to approach area
                    if not serial_mgr.send(target_rack_id, cmd_for_rack, wait_done=True, done_token=rack_done_token):
                        final_task_status = 'failed_rack_echo'
                    # 2. Main equipment (M) receives from approach area
                    elif not serial_mgr.send(main_equipment_id, cmd_for_m, wait_done=True, done_token=main_done_token):
                        final_task_status = 'failed_m_echo'
                    else:
                        physical_op_successful = True
                        # Record end time after last equipment response
                        operation_end_time = datetime.datetime.now().isoformat(timespec="seconds")
                
                else:
                    final_task_status = 'failed_unknown_movement'
                        
            except Exception as e:
                logger.error(f"[Worker] Task {task_id}: Exception during execution: {e}", exc_info=True)
                final_task_status = 'failed_exception'

            # Update task status and times in database
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            try:
                if physical_op_successful:
                    # Update inventory first
                    update_inventory_on_done(task, cur)
                    # Then update task status with operation times
                    cur.execute("""
                        UPDATE work_tasks 
                        SET status='done', updated_at=?, start_time=?, end_time=?
                        WHERE id=?
                    """, (operation_end_time, operation_start_time, operation_end_time, task_id))
                    final_task_status = 'done'
                else:
                    # Update task status with operation times even for failed tasks
                    cur.execute("""
                        UPDATE work_tasks 
                        SET status=?, updated_at=?, start_time=?, end_time=?
                        WHERE id=?
                    """, (final_task_status, operation_end_time or datetime.datetime.now().isoformat(timespec="seconds"),
                         operation_start_time, operation_end_time, task_id))
                conn.commit()
            except Exception as e:
                logger.error(f"[Worker] Task {task_id}: Database update failed: {e}", exc_info=True)
                conn.rollback()
                if final_task_status == 'done':
                    final_task_status = 'failed_inventory_update'
            finally:
                conn.close()

            # Emit status update
            if io:
                task_details = get_task_by_id(task_id)
                if task_details:
                    io.emit("task_status_changed", {
                        "id": task_id,
                        "status": final_task_status,
                        "start_time": operation_start_time,
                        "end_time": operation_end_time,
                        **task_details
                    })

            time.sleep(0.1)

def start_global_worker():
    worker = GlobalWorker()
    worker.start()

# --- API Helper ---
def get_work_tasks_by_status(status=None, user_info=None):
    """
    Get work tasks filtered by status and user permissions.
    Admin users can see all tasks, regular users only see their own tasks.
    
    Args:
        status (str, optional): Filter tasks by status
        user_info (dict): User information including id and role
    """
    if not user_info:
        return []
        
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    base_query = """
        SELECT wt.*, btl.batch_id, u.username as created_by_username 
        FROM work_tasks wt 
        LEFT JOIN batch_task_links btl ON wt.id = btl.task_id
        LEFT JOIN users u ON wt.created_by = u.id
    """
    
    params = []
    where_clauses = []
    
    # Add status filter if provided
    if status:
        where_clauses.append("wt.status = ?")
        params.append(status)
    
    # Add user filter based on role
    if user_info.get('role') != 'admin':
        where_clauses.append("wt.created_by = ?")
        params.append(user_info['id'])
    
    # Combine where clauses if any exist
    if where_clauses:
        base_query += " WHERE " + " AND ".join(where_clauses)
    
    base_query += " ORDER BY wt.created_at ASC"
    
    cur.execute(base_query, params)
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    conn.close()
    return [dict(zip(columns, row)) for row in rows]

def get_pending_task_counts(user_info=None):
    """
    Get pending task counts filtered by user permissions.
    Admin users see all pending tasks, regular users only see their own.
    
    Args:
        user_info (dict): User information including id and role
    """
    if not user_info:
        return {"pending_in_count": 0, "pending_out_count": 0}
        
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    base_query = "SELECT COUNT(*) FROM work_tasks WHERE status='pending' AND movement=?"
    params = []
    
    # Add user filter for non-admin users
    if user_info.get('role') != 'admin':
        base_query += " AND created_by = ?"
        params = ['IN', user_info['id']]
    else:
        params = ['IN']
    
    # Count pending IN tasks
    cur.execute(base_query, params)
    pending_in_count = cur.fetchone()[0]
    
    # Update params for OUT query
    params[0] = 'OUT'
    
    # Count pending OUT tasks
    cur.execute(base_query, params)
    pending_out_count = cur.fetchone()[0]
    
    conn.close()
    return {"pending_in_count": pending_in_count, "pending_out_count": pending_out_count}

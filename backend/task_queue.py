# task_queue.py  ─────────────────────────────────────────────
import queue, threading, time, logging, sqlite3, datetime
from typing import Optional
# Use DEFAULT_MAX_ECHO_ATTEMPTS from serial_io for regular commands
from .serial_io import serial_mgr, DEFAULT_MAX_ECHO_ATTEMPTS
from flask import current_app
from .inventory_updater import update_inventory_on_done
from .db import DB_NAME
from .error_messages import get_error_message
from .camera_history import store_camera_batch

io = None                           # SocketIO 인스턴스 홀더
app_instance = None                 # Flask app instance holder

# Global lock to ensure only one task is claimed at a time
task_lock = threading.Lock()

def set_socketio(sock):             # app.py 가 주입
    global io; io = sock

def set_app(app):                   # Store Flask app instance
    global app_instance; app_instance = app

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

def set_task_status(task_id: int, status: str, conn=None):
    """Sets the status of a specific task and emits a socket event."""
    now = datetime.datetime.now().isoformat(timespec="seconds")
    
    own_connection = False
    if conn is None:
        conn = sqlite3.connect(DB_NAME)
        own_connection = True
    
    cur = conn.cursor()

    try:
        if status == 'in_progress':
            cur.execute("UPDATE work_tasks SET status=?, updated_at=?, start_time=? WHERE id=?", (status, now, now, task_id))
        else:
            # For non-in_progress statuses, only update status, updated_at, and end_time
            # Do NOT modify start_time
            cur.execute("UPDATE work_tasks SET status=?, updated_at=?, end_time=? WHERE id=?", (status, now, now, task_id))
        
        if own_connection:
            conn.commit()

        # Fetch details for the event
        task_details = get_task_by_id(task_id)
        if io and task_details:
            io.emit("task_status_changed", task_details)
            logger = current_app.logger if current_app else logging.getLogger(__name__)
            logger.info(f"Emitted task_status_changed for task {task_id} with status {status}")

    finally:
        if own_connection:
            conn.close()

def claim_next_task():
    """
    Atomically fetches the next pending task and sets its status to 'in_progress'.
    This prevents multiple workers from picking up tasks simultaneously.
    """
    with task_lock:
        conn = sqlite3.connect(DB_NAME, timeout=10)
        cur = conn.cursor()
        try:
            # First, check if any task is already in progress
            cur.execute("SELECT COUNT(*) FROM work_tasks WHERE status = 'in_progress'")
            in_progress_count = cur.fetchone()[0]
            if in_progress_count > 0:
                return None  # A task is already running

            # If no tasks are in progress, get the next pending one
            # MUST fetch all columns needed by update_inventory_on_done
            cur.execute("""
                SELECT 
                    id, rack, slot, movement, product_code, 
                    product_name, quantity, cargo_owner
                FROM work_tasks
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT 1
            """)
            task_row = cur.fetchone()

            if task_row:
                # Get column names BEFORE the UPDATE query resets the cursor's description
                columns = [desc[0] for desc in cur.description]
                task_id = task_row[0]
                
                # Get current time for both updated_at and start_time
                now = datetime.datetime.now().isoformat(timespec="seconds")
                
                # Immediately claim it by setting status to in_progress AND setting start_time
                cur.execute("""
                    UPDATE work_tasks 
                    SET status = ?, updated_at = ?, start_time = ? 
                    WHERE id = ?
                """, ('in_progress', now, now, task_id))
                conn.commit()
                
                # Create a full task dictionary from the row
                task = dict(zip(columns, task_row))
                return task
            else:
                return None # No pending tasks
        finally:
            conn.close()

def get_task_by_id(task_id: int) -> Optional[dict]:
    """Fetches a single task by its ID."""
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
class WorkerThread(threading.Thread):
    def __init__(self, app_context):
        super().__init__()
        self.daemon = True
        self.app_context = app_context

    def run(self):
        with self.app_context:
            logger = current_app.logger
            main_equipment_id = "M"
            main_done_token = b"fin"
            rack_done_token = b"done"

            while True:
                task = claim_next_task()
                if not task:
                    time.sleep(1)
                    continue

                task_id = task['id']
                try:
                    logger.info(f"[Worker] Picked up task {task_id}. Already marked as 'in_progress'.")
                    
                    target_rack_id = task['rack'].upper()
                    current_slot = int(task['slot'])
                    movement = task['movement'].upper()

                    final_task_status = None
                    physical_op_successful = False
                    operation_start_time = datetime.datetime.now(datetime.timezone.utc)
                    
                    # --- M Command Generation ---
                    cmd_for_m = "0"
                    rack_to_num_map = {'A': 1, 'B': 2, 'C': 3}
                    rack_numeric_id = rack_to_num_map.get(target_rack_id)
                    if rack_numeric_id is not None:
                        m_base_val = rack_numeric_id * 100 + current_slot
                        cmd_for_m = str(m_base_val) if movement == 'IN' else str(-m_base_val)
                    else:
                        final_task_status = 'failed_invalid_rack'
                    
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
                        # 1. Main equipment (M) delivers to rack approach area
                        m_result = serial_mgr.send(main_equipment_id, cmd_for_m, wait_done=True, done_token=main_done_token)
                        if m_result["status"] != "done":
                            final_task_status = 'failed_m_comm'
                        else:
                            # Record start time from when the first command was sent
                            operation_start_time = m_result["command_sent_time"]
                            
                            # 2. Rack receives from approach area
                            rack_result = serial_mgr.send(target_rack_id, cmd_for_rack, wait_done=True, done_token=rack_done_token)
                            if rack_result["status"] != "done":
                                final_task_status = 'failed_rack_comm'
                            else:
                                physical_op_successful = True
                                # Record end time from when the last "done" signal was received
                                operation_end_time = rack_result["done_received_time"]
                    
                    elif movement == 'OUT':
                        # 1. Rack delivers to approach area
                        rack_result = serial_mgr.send(target_rack_id, cmd_for_rack, wait_done=True, done_token=rack_done_token)
                        if rack_result["status"] != "done":
                            final_task_status = 'failed_rack_echo'
                        else:
                            # Record start time from when the first command was sent
                            operation_start_time = rack_result["command_sent_time"]
                            
                            # 2. Main equipment (M) receives from approach area
                            m_result = serial_mgr.send(main_equipment_id, cmd_for_m, wait_done=True, done_token=main_done_token)
                            if m_result["status"] != "done":
                                final_task_status = 'failed_m_echo'
                            else:
                                physical_op_successful = True
                                # Record end time from when the last "done" signal was received
                                operation_end_time = m_result["done_received_time"]
                    
                    else:
                        final_task_status = 'failed_unknown_movement'

                    # Complete the task after physical operation
                    if physical_op_successful:
                        # Update inventory first
                        update_inventory_on_done(task)
                        # Then mark task as done
                        set_task_status(task_id, 'done')
                        
                        # Get task details for history
                        task_details = get_task_by_id(task_id)
                        if task_details:
                            # Record in camera batch history
                            history_data = {
                                'batch_id': task_details.get('batch_id'),
                                'rack': task_details['rack'],
                                'slot': task_details['slot'],
                                'movement': task_details['movement'],
                                'start_time': operation_start_time.isoformat() if isinstance(operation_start_time, datetime.datetime) else operation_start_time,
                                'end_time': operation_end_time.isoformat() if isinstance(operation_end_time, datetime.datetime) else operation_end_time,
                                'product_code': task_details['product_code'],
                                'product_name': task_details['product_name'],
                                'quantity': task_details['quantity'],
                                'cargo_owner': task_details['cargo_owner'],
                                'created_by': task_details['created_by'],
                                'created_by_username': task_details.get('created_by_username', 'Unknown'),
                                'status': 'done',
                                'created_at': task_details['created_at'],
                                'updated_at': task_details['updated_at']
                            }
                            store_camera_batch(history_data)
                            logger.info(f"[Worker] Task {task_id} recorded in camera batch history.")
                        
                        logger.info(f"[Worker] Task {task_id} completed successfully.")
                    else:
                        # Mark task as failed with specific error
                        set_task_status(task_id, final_task_status if final_task_status else 'failed_unknown')
                        logger.error(f"[Worker] Task {task_id} failed with status: {final_task_status}")
                            
                except Exception as e:
                    logger.error(f"[Worker] UNHANDLED EXCEPTION processing task {task_id}: {e}", exc_info=True)
                    set_task_status(task_id, 'failed_exception')
                
                finally:
                    # Brief pause before next task
                    time.sleep(1)

def start_worker(app):
    with app.app_context():
        worker = WorkerThread(app.app_context())
        worker.start()
        current_app.logger.info("Task processing worker started.")

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

def clear_all_queues():
    """
    Clear all pending tasks from the work_tasks table.
    This is used during system reset.
    """
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    try:
        # Delete all pending tasks
        cur.execute("DELETE FROM work_tasks WHERE status='pending'")
        deleted_count = cur.rowcount
        
        # Also clear any batch task links for deleted tasks
        cur.execute("DELETE FROM batch_task_links WHERE task_id NOT IN (SELECT id FROM work_tasks)")
        
        conn.commit()
        
        logger = current_app.logger if current_app else logging.getLogger(__name__)
        logger.info(f"[clear_all_queues] Cleared {deleted_count} pending tasks from queue")
        
        return deleted_count
        
    except Exception as e:
        logger = current_app.logger if current_app else logging.getLogger(__name__)
        logger.error(f"[clear_all_queues] Error clearing queues: {e}", exc_info=True)
        conn.rollback()
        raise
    finally:
        conn.close()

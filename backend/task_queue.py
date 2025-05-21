# task_queue.py  ─────────────────────────────────────────────
import queue, threading, time, logging, sqlite3, datetime
from typing import Optional
from .serial_io import serial_mgr, RESET_COMMAND_MAX_ECHO_ATTEMPTS
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
            # For the initial pending event, we don't have batch_id yet from batch_task_links,
            # as it's inserted by inventory.py *after* this call.
            # So, the initial 'pending' event will not have batch_id here.
            # Batch_id will be added to 'in_progress' and 'done' events from set_task_status.
            io.emit("task_status_changed", {
                "id": new_task_id, 
                "status": "pending", 
                "action": "created", 
                "rack": task['rack'].upper(), 
                "slot": int(task['slot']), 
                "movement": task['movement'].upper()
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
    
    # Fetch task details from work_tasks and batch_id from batch_task_links
    if status == "done" or status == "in_progress":
        cur.execute("""
            SELECT wt.id, wt.rack, wt.slot, wt.movement, btl.batch_id 
            FROM work_tasks wt
            LEFT JOIN batch_task_links btl ON wt.id = btl.task_id
            WHERE wt.id=?
        """, (task_id,))
        row = cur.fetchone()
        if row:
            columns = [desc[0] for desc in cur.description]
            fetched_details = dict(zip(columns, row))
            task_details_for_event.update(fetched_details) # Add rack, slot, movement, batch_id
            
    conn.close()

    if io:
        io.emit("task_status_changed", task_details_for_event)
        logger = current_app.logger if current_app else logging.getLogger(__name__)
        logger.info(f"[set_task_status] Emitted task_status_changed: {task_details_for_event}")

def get_next_pending_task():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM work_tasks WHERE status='pending' ORDER BY created_at ASC LIMIT 1")
    row = cur.fetchone()
    columns = [desc[0] for desc in cur.description]
    conn.close()
    if row:
        return dict(zip(columns, row))
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
        while True:
            task = get_next_pending_task()
            if not task:
                time.sleep(1)
                continue
            task_id = task['id']
            set_task_status(task_id, 'in_progress')
            status = "unknown"
            try:
                if not serial_mgr.enabled:
                    status = "done (simulated_disabled)"
                elif task['rack'] not in serial_mgr.ports:
                    status = "port_not_found"
                else:
                    res = serial_mgr.send(
                        task['rack'],
                        str(task['slot']) if task['movement'].upper() == 'IN' else str(-int(task['slot'])),
                        wait_done=True,
                        custom_max_echo_attempts=RESET_COMMAND_MAX_ECHO_ATTEMPTS
                    )
                    status = res["status"]
            except Exception as e:
                status = f"error:{str(e)[:100]}" 
            
            if status == "done":
                # Update inventory
                success = update_inventory_on_done(
                    task['rack'],
                    int(task['slot']),
                    task['movement'].upper(),
                    task['product_code'],
                    task['product_name'],
                    int(task['quantity']),
                    task.get('cargo_owner', '')
                )
                if success:
                    set_task_status(task_id, 'done')
                else:
                    # Optionally: handle DB update failure (log, retry, etc.)
                    pass
            else:
                # Optionally: handle error state
                pass
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

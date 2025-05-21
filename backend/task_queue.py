# task_queue.py  ─────────────────────────────────────────────
import queue, threading, time, logging, sqlite3
from typing import Optional
from .serial_io import serial_mgr, RESET_COMMAND_MAX_ECHO_ATTEMPTS
from flask import current_app
from .inventory_updater import update_inventory_on_done
from .db import DB_NAME

io = None                           # SocketIO 인스턴스 홀더
def set_socketio(sock):             # app.py 가 주입
    global io; io = sock

class Task:
    def __init__(self, rack:str, code:int, wait=True):
        self.rack, self.code, self.wait = rack.upper(), code, wait

class RackWorker(threading.Thread):
    def __init__(self, rack, q):
        super().__init__()
        self.rack = rack.upper()
        self.q = q
        self.daemon = True  # Thread will exit when main program exits
        # Optional: Log worker creation
        print(f"DEBUG: RackWorker [{self.rack}] instance CREATED.")

    def run(self):
        print(f"DEBUG: RackWorker [{self.rack}] run() method ENTERED.") 
        # Define print-based log functions directly, avoid current_app in thread
        def log_func(msg): print(f"INFO: {msg}")
        def warn_func(msg): print(f"WARNING: {msg}")
        def error_func(msg, exc_info=False): # Add exc_info compatibility
            print(f"ERROR: {msg}")
            if exc_info:
                import traceback
                traceback.print_exc() # Print stack trace if exc_info is True
        def debug_func(msg): print(f"DEBUG: {msg}")

        while True:
            debug_func(f"RackWorker [{self.rack}] run() loop: WAITING for task from queue...")
            task = self.q.get()
            if task is None: 
                debug_func(f"RackWorker [{self.rack}] run() loop: Received None, BREAKING loop.")
                break
            
            log_func(f"RackWorker [{self.rack}]: Picked up task with code {task.code} for rack {task.rack}.")
            
            status = "unknown"
            try:
                if not serial_mgr.enabled:
                    log_func(f"RackWorker [{self.rack}]: Serial communication disabled. Task {task.code} processed (simulated).")
                    status = "done (simulated_disabled)"
                
                elif self.rack not in serial_mgr.ports:
                    warn_func(f"RackWorker [{self.rack}]: Serial port not discovered/mapped for code {task.code}. Task re-queued.")
                    time.sleep(1) 
                    self.q.put(task) 
                    self.q.task_done()
                    continue 
                
                else:
                    log_func(f"RackWorker [{self.rack}]: Sending task {task.code} (command: '{str(task.code)}') to serial_mgr for rack {self.rack}. Waiting for completion: {task.wait}. Echo attempts: {RESET_COMMAND_MAX_ECHO_ATTEMPTS}")
                    res = serial_mgr.send(
                        task.rack, 
                        str(task.code), 
                        wait_done=task.wait,
                        custom_max_echo_attempts=RESET_COMMAND_MAX_ECHO_ATTEMPTS
                    )
                    status = res["status"]
                    
                    debug_func(f"RackWorker [{self.rack}]: Task {task.code} - serial_mgr.send returned status: {status}")
                    if status == "echo_error_max_retries":
                        debug_func(f"RackWorker [{self.rack}]: Task {task.code} - Echo debug: Failed to receive/confirm echo after {RESET_COMMAND_MAX_ECHO_ATTEMPTS} attempts.")
                    elif status == "timeout_after_echo":
                        debug_func(f"RackWorker [{self.rack}]: Task {task.code} - Echo debug: Echo was successful, but 'done' signal timed out.")
                    elif status in ["done", "sent_echo_confirmed"]:
                        debug_func(f"RackWorker [{self.rack}]: Task {task.code} - Echo debug: Echo was successful.")
                    
                    if status == "done":
                        log_func(f"RackWorker [{self.rack}]: Task {task.code} (command: '{str(task.code)}') successfully COMPLETED by Arduino. Status: {status}")
                        # Get the task details from the product_logs table
                        conn = sqlite3.connect(DB_NAME)
                        cur = conn.cursor()
                        try:
                            # Get the most recent log entry for this rack and slot
                            slot = abs(task.code)  # Convert command code back to slot number
                            debug_func(f"RackWorker [{self.rack}]: Looking up task details for rack={task.rack}, slot={slot}")
                            cur.execute("""
                                SELECT product_code, product_name, movement_type, quantity, cargo_owner
                                FROM product_logs
                                WHERE rack = ? AND slot = ?
                                ORDER BY timestamp DESC
                                LIMIT 1
                            """, (task.rack, slot))
                            row = cur.fetchone()
                            if row:
                                product_code, product_name, movement_type, quantity, cargo_owner = row
                                debug_func(f"RackWorker [{self.rack}]: Found task details: product_code={product_code}, movement_type={movement_type}")
                                # Update inventory only when we get the done signal
                                success = update_inventory_on_done(
                                    task.rack,
                                    slot,
                                    movement_type,
                                    product_code,
                                    product_name,
                                    quantity,
                                    cargo_owner
                                )
                                if success:
                                    log_func(f"RackWorker [{self.rack}]: Successfully updated inventory for task {task.code}")
                                else:
                                    error_func(f"RackWorker [{self.rack}]: Failed to update inventory for task {task.code}")
                            else:
                                error_func(f"RackWorker [{self.rack}]: No task details found in product_logs for rack={task.rack}, slot={slot}")
                        except Exception as e:
                            error_func(f"RackWorker [{self.rack}]: Error updating inventory: {e}", exc_info=True)
                        finally:
                            conn.close()
                        for t in TASK_STATE:
                            if t['rack'] == task.rack and t['code'] == task.code and t['state'] == 'in_progress':
                                t['state'] = 'done'
                                break
                    elif status == "sent_echo_confirmed": 
                        log_func(f"RackWorker [{self.rack}]: Task {task.code} (command: '{str(task.code)}') sent and ECHO CONFIRMED by Arduino (wait_done=False). Status: {status}")
                    else:
                        error_func(f"RackWorker [{self.rack}]: Task {task.code} (command: '{str(task.code)}') FAILED or did not complete as expected by Arduino. Serial status: {status}")
                        
            except Exception as e:
                error_msg = f"RackWorker [{self.rack}]: Exception for code {task.code}: {e}"
                error_func(error_msg, exc_info=True) # Use the updated error_func
                status = f"error:{str(e)[:100]}" 
            
            if io:
                io.emit("task_done", {"rack": task.rack, "code": task.code, "status": status})
                debug_func(f"RackWorker [{self.rack}]: Emitted 'task_done' via SocketIO for task {task.code}, status: {status}")
                current_qsize = 0
                try:
                    current_qsize = self.q.qsize()
                except Exception as e_qsize:
                    error_func(f"RackWorker [{self.rack}]: Error getting qsize: {e_qsize}")
                io.emit("queue_size", {"rack": task.rack, "size": current_qsize})
            self.q.task_done()

RACK_TASK_QUEUES = {r: queue.Queue() for r in ("A","B","C")}
# Define workers but do not start them here
workers = {r: RackWorker(r, q) for r,q in RACK_TASK_QUEUES.items()}

def start_rack_workers():
    print("Starting RackWorker threads...")
    for r, w in workers.items():
        if not w.is_alive(): # Start only if not already started (e.g. dev server reload)
            print(f"Starting worker for rack {r}")
            w.start()
    print("RackWorker threads started.")

# In-memory task state tracking
TASK_STATE = []  # Each item: {'rack': 'A', 'code': 2, 'state': 'queued'}

def enqueue_task(rack:str, code:int, wait=True):
    RACK_TASK_QUEUES[rack.upper()].put(Task(rack, code, wait))
    TASK_STATE.append({'rack': rack.upper(), 'code': code, 'state': 'queued'})

# Helper functions for API use

def get_waiting_tasks():
    return [t for t in TASK_STATE if t['state'] in ('queued', 'in_progress')]

def get_done_tasks():
    return [t for t in TASK_STATE if t['state'] == 'done']

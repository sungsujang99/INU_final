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

GLOBAL_TASK_QUEUE = queue.Queue()
TASK_STATE = []

class Task:
    def __init__(self, rack, code, wait=True):
        self.rack, self.code, self.wait = rack.upper(), code, wait

class GlobalWorker(threading.Thread):
    def __init__(self, q):
        super().__init__()
        self.q = q
        self.daemon = True

    def run(self):
        while True:
            task = self.q.get()
            # Mark as in_progress
            for t in TASK_STATE:
                if t['rack'] == task.rack and t['code'] == task.code and t['state'] == 'queued':
                    t['state'] = 'in_progress'
                    break

            # --- Arduino communication logic (copied from old RackWorker) ---
            status = "unknown"
            try:
                if not serial_mgr.enabled:
                    status = "done (simulated_disabled)"
                elif task.rack not in serial_mgr.ports:
                    # Optionally: requeue or skip
                    status = "port_not_found"
                else:
                    res = serial_mgr.send(
                        task.rack,
                        str(task.code),
                        wait_done=task.wait,
                        custom_max_echo_attempts=RESET_COMMAND_MAX_ECHO_ATTEMPTS
                    )
                    status = res["status"]
            except Exception as e:
                status = f"error:{str(e)[:100]}"

            # --- Mark as done only if status is 'done' ---
            if status == "done":
                # Fetch task details from product_logs (as in your old code)
                conn = sqlite3.connect(DB_NAME)
                cur = conn.cursor()
                try:
                    slot = abs(task.code)
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
                            for t in TASK_STATE:
                                if t['rack'] == task.rack and t['code'] == task.code and t['state'] == 'in_progress':
                                    t['state'] = 'done'
                                    break
                            # Emit SocketIO event for real-time UI update
                            if io:
                                io.emit("task_done", {
                                    "rack": task.rack,
                                    "code": task.code,
                                    "status": "done"
                                })
                        else:
                            # Optionally: handle DB update failure (log, retry, etc.)
                            pass
                finally:
                    conn.close()
            # Optionally: emit socket events, update inventory, etc.

            self.q.task_done()

def enqueue_task(rack, code, wait=True):
    GLOBAL_TASK_QUEUE.put(Task(rack, code, wait))
    TASK_STATE.append({'rack': rack.upper(), 'code': code, 'state': 'queued'})

def start_global_worker():
    worker = GlobalWorker(GLOBAL_TASK_QUEUE)
    worker.start()

def get_waiting_tasks():
    return [t for t in TASK_STATE if t['state'] in ('queued', 'in_progress')]

def get_done_tasks():
    return [t for t in TASK_STATE if t['state'] == 'done']

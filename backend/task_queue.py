# task_queue.py  ─────────────────────────────────────────────
import queue, threading, time, logging
from typing import Optional
from .serial_io import serial_mgr
from flask import current_app

io = None                           # SocketIO 인스턴스 홀더
def set_socketio(sock):             # app.py 가 주입
    global io; io = sock

class Task:
    def __init__(self, rack:str, code:str, wait=True):
        self.rack, self.code, self.wait = rack.upper(), code, wait

class RackWorker(threading.Thread):
    def __init__(self, rack, q):
        super().__init__(daemon=True)
        self.rack, self.q = rack, q
    def run(self):
        while True:
            task = self.q.get()
            if task is None: break
            current_app.logger.info(f"RackWorker [{self.rack}]: Picked up task {task.code} for rack {task.rack}.")
            
            status = "unknown"
            try:
                # Check if serial communication is globally enabled via SerialManager's state
                # (which should reflect current_app.config.get('SERIAL_COMMUNICATION_ENABLED'))
                if not serial_mgr.enabled:
                    if current_app: # Log with app logger if available
                        current_app.logger.info(f"RackWorker [{self.rack}]: Serial communication disabled. Task {task.code} processed (simulated).")
                    else:
                        print(f"RackWorker [{self.rack}]: Serial communication disabled. Task {task.code} processed (simulated).")
                    status = "done (simulated_disabled)"
                    # No re-queue, task will be marked as done. Frontend should reflect this.
                
                # If serial is enabled, then check if this specific rack's port was discovered
                elif self.rack not in serial_mgr.ports:
                    if current_app:
                        current_app.logger.warning(f"RackWorker [{self.rack}]: Serial port not discovered/mapped for code {task.code}. Task re-queued.")
                    else:
                        print(f"RackWorker [{self.rack}]: Serial port not discovered/mapped for code {task.code}. Task re-queued.")
                    time.sleep(1) 
                    self.q.put(task) # Re-queue the task
                    self.q.task_done() # Mark this attempt as done, but it's re-queued
                    continue # Skip emitting 'task_done' for this attempt or decide if client needs this status
                
                # Serial is enabled and port was found - proceed with actual send
                else:
                    current_app.logger.info(f"RackWorker [{self.rack}]: Attempting to send task {task.code} to serial_mgr.")
                    res = serial_mgr.send(task.rack, task.code, wait_done=task.wait)
                    current_app.logger.info(f"RackWorker [{self.rack}]: serial_mgr.send for task {task.code} returned: {res}")
                    status = res["status"]
                    if current_app:
                        current_app.logger.info(f"RackWorker [{self.rack}]: Task {task.code} sent. Status: {status}")
                    else:
                        print(f"RackWorker [{self.rack}]: Task {task.code} sent. Status: {status}")
                        
            except Exception as e:
                error_msg = f"RackWorker [{self.rack}]: Exception for code {task.code}: {e}"
                if current_app:
                    current_app.logger.error(error_msg, exc_info=True)
                else:
                    print(error_msg)
                status = f"error:{str(e)[:100]}" # Keep error short for status
            
            if io:
                io.emit("task_done", {"rack": task.rack, "code": task.code, "status": status})
                # Ensure qsize is fetched safely if tasks might be added/removed concurrently by other parts
                current_qsize = 0
                try:
                    current_qsize = self.q.qsize()
                except Exception as e_qsize:
                    if current_app:
                        current_app.logger.error(f"RackWorker [{self.rack}]: Error getting qsize: {e_qsize}")
                    else:
                        print(f"RackWorker [{self.rack}]: Error getting qsize: {e_qsize}")
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

def enqueue_task(rack:str, code:str, wait=True):
    RACK_TASK_QUEUES[rack.upper()].put(Task(rack, code, wait))

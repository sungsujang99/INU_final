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
            # TODO: Add your Arduino communication logic here
            # When done:
            for t in TASK_STATE:
                if t['rack'] == task.rack and t['code'] == task.code and t['state'] == 'in_progress':
                    t['state'] = 'done'
                    break
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

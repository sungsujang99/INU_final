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
    
    # For all non-pending states, fetch more details including batch_id
    # The original 'pending' event is minimal, subsequent ones are richer.
    if status != 'pending': # Fetch details for all processing, completed, and failed states
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
        main_equipment_id = "M"
        main_done_token = b"fin"
        rack_done_token = b"done"

        while True:
            task = get_next_pending_task()
            if not task:
                time.sleep(1)
                continue

            task_id = task['id']
            movement = task['movement'].upper()
            target_rack_id = task['rack'].upper()
            current_slot = int(task['slot'])
            
            logger.info(f"[Worker] Picked task {task_id}: {movement} for {target_rack_id}-{current_slot}")

            # --- Command Generation ---
            cmd_for_rack_in = str(current_slot)
            cmd_for_rack_out = str(-current_slot)
            cmd_for_m = "0" # Default/error command for M

            rack_to_num_map = {'A': 1, 'B': 2, 'C': 3}
            rack_numeric_id = rack_to_num_map.get(target_rack_id)

            if rack_numeric_id is None:
                logger.error(f"[Worker] Task {task_id}: Unknown target_rack_id '{target_rack_id}' for M command generation.")
                final_task_status = 'failed_invalid_rack_for_m' 
                # This status will be picked up later in the logic
            else:
                m_base_command_value = rack_numeric_id * 100 + current_slot
                if movement == 'IN':
                    cmd_for_m = str(m_base_command_value)  
                elif movement == 'OUT':
                    cmd_for_m = str(-m_base_command_value) 
                # else: cmd_for_m remains "0", which should ideally not be used if movement is validated
            
            logger.info(f"[Worker] Task {task_id}: Generated M Command: '{cmd_for_m}', Rack IN Cmd: '{cmd_for_rack_in}', Rack OUT Cmd: '{cmd_for_rack_out}'")
            # --- End Command Generation ---

            operation_fully_successful = False
            final_task_status = None

            if final_task_status: # If error already identified (e.g. invalid rack for M command)
                pass # Skip serial operations
            elif not serial_mgr.enabled:
                logger.warning(f"[Worker] Task {task_id}: Serial communication is DISABLED. Simulating successful task.")
                # Simulate full success for testing purposes if serial is off
                operation_fully_successful = True
                # Skip actual serial calls below

            elif movement == 'IN':
                # Step 1: Main equipment (M) moves item to rack
                set_task_status(task_id, 'processing_main_to_rack')
                logger.info(f"[Worker] Task {task_id} (IN) - Step 1: Main ({main_equipment_id}) to {target_rack_id}-{current_slot}. Cmd: '{cmd_for_m}'")
                
                if main_equipment_id not in serial_mgr.ports:
                    logger.error(f"[Worker] Task {task_id}: Main equipment '{main_equipment_id}' not found. Marking failed.")
                    final_task_status = 'failed_port_not_found'
                else:
                    res_main = serial_mgr.send(main_equipment_id, cmd_for_m, wait_done=True, done_token=main_done_token)
                    main_status = res_main["status"]
                    logger.info(f"[Worker] Task {task_id}: Main ({main_equipment_id}) result: {main_status}")

                    if main_status == "done": # 'done' from send means 'fin' token was received
                        # Step 2: Target rack receives item
                        set_task_status(task_id, 'processing_rack_storing')
                        logger.info(f"[Worker] Task {task_id} (IN) - Step 2: Rack ({target_rack_id}) storing. Cmd: '{cmd_for_rack_in}'")
                        
                        if target_rack_id not in serial_mgr.ports:
                            logger.error(f"[Worker] Task {task_id}: Target rack '{target_rack_id}' not found. Marking failed.")
                            final_task_status = 'failed_port_not_found'
                        else:
                            res_rack = serial_mgr.send(target_rack_id, cmd_for_rack_in, wait_done=True, done_token=rack_done_token)
                            rack_status = res_rack["status"]
                            logger.info(f"[Worker] Task {task_id}: Rack ({target_rack_id}) result: {rack_status}")

                            if rack_status == "done":
                                operation_fully_successful = True
                            else: # Rack failed
                                final_task_status = 'failed_rack_comms' if rack_status == "echo_error_max_retries" else 'failed_rack_timeout'
                                logger.error(f"[Worker] Task {task_id}: Rack op failed for IN. Final status: {final_task_status}")
                    else: # Main failed
                        final_task_status = 'failed_main_comms' if main_status == "echo_error_max_retries" else 'failed_main_timeout'
                        logger.error(f"[Worker] Task {task_id}: Main op failed for IN. Final status: {final_task_status}")
            
            elif movement == 'OUT':
                # Step 1: Target rack dispenses item
                set_task_status(task_id, 'processing_rack_dispensing')
                logger.info(f"[Worker] Task {task_id} (OUT) - Step 1: Rack ({target_rack_id}) dispensing. Cmd: '{cmd_for_rack_out}'")

                if target_rack_id not in serial_mgr.ports:
                    logger.error(f"[Worker] Task {task_id}: Target rack '{target_rack_id}' not found. Marking failed.")
                    final_task_status = 'failed_port_not_found'
                else:
                    res_rack = serial_mgr.send(target_rack_id, cmd_for_rack_out, wait_done=True, done_token=rack_done_token)
                    rack_status = res_rack["status"]
                    logger.info(f"[Worker] Task {task_id}: Rack ({target_rack_id}) result: {rack_status}")

                    if rack_status == "done":
                        # Step 2: Main equipment (M) collects item
                        set_task_status(task_id, 'processing_main_from_rack')
                        logger.info(f"[Worker] Task {task_id} (OUT) - Step 2: Main ({main_equipment_id}) collecting from {target_rack_id}-{current_slot}. Cmd: '{cmd_for_m}'")

                        if main_equipment_id not in serial_mgr.ports:
                            logger.error(f"[Worker] Task {task_id}: Main equipment '{main_equipment_id}' not found. Marking failed.")
                            final_task_status = 'failed_port_not_found'
                        else:
                            res_main = serial_mgr.send(main_equipment_id, cmd_for_m, wait_done=True, done_token=main_done_token)
                            main_status = res_main["status"]
                            logger.info(f"[Worker] Task {task_id}: Main ({main_equipment_id}) result: {main_status}")
                        
                            if main_status == "done": # 'done' from send means 'fin' token was received
                                operation_fully_successful = True
                            else: # Main failed
                                final_task_status = 'failed_main_comms' if main_status == "echo_error_max_retries" else 'failed_main_timeout'
                                logger.error(f"[Worker] Task {task_id}: Main op failed for OUT. Final status: {final_task_status}")
                    else: # Rack failed
                        final_task_status = 'failed_rack_comms' if rack_status == "echo_error_max_retries" else 'failed_rack_timeout'
                        logger.error(f"[Worker] Task {task_id}: Rack op failed for OUT. Final status: {final_task_status}")
            else: # Should not happen if movement is validated before enqueue
                logger.error(f"[Worker] Task {task_id}: Unknown movement type '{movement}'. Setting to an error state.")
                final_task_status = 'failed_unknown_movement'


            # Post-operation status update and inventory management
            if operation_fully_successful:
                logger.info(f"[Worker] Task {task_id}: Operation fully successful. Updating inventory.")
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
                    final_task_status = 'completed'
                    logger.info(f"[Worker] Task {task_id}: Inventory updated. Task marked '{final_task_status}'.")
                else:
                    final_task_status = 'failed_inventory_update'
                    logger.error(f"[Worker] Task {task_id}: Inventory update FAILED. Task marked '{final_task_status}'.")
            
            if final_task_status: # This will be set if success or any prior failure
                 set_task_status(task_id, final_task_status)
            else:
                # This case should ideally not be reached if logic is sound,
                # means operation_fully_successful was false but no specific error status was set.
                logger.error(f"[Worker] Task {task_id}: Reached end of processing with no definitive success or error status. Defaulting to generic failure.")
                set_task_status(task_id, 'failed_processing_logic')


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

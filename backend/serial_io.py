# serial_io.py
import serial, glob, time, threading, sys, datetime
from flask import current_app

BAUD = 19200
TIMEOUT = 120 # Timeout for waiting for 'done'
DISCOVERY_TIMEOUT = 1 # Specific timeout for WHO command during discovery
ECHO_TIMEOUT = 1 # Timeout for waiting for command echo
WHO_CMD = b"WHO\n"
RACKS   = {"A", "B", "C", "M"}
OPTIONAL_MODULE_ID = "I"  # Optional module responds with "X" to WHO command
# A: 1, B: 2, C: 3, M: main rack

DEFAULT_MAX_ECHO_ATTEMPTS = 6    # Default number of attempts (1 initial + 5 retries) to get command echo
RESET_COMMAND_MAX_ECHO_ATTEMPTS = 15 # More attempts for the critical reset command

class SerialManager:
    def __init__(self):
        self.lock  = threading.Lock()
        self.ports = {}                    # { 'A': {ser, mutex}, … }
        
        # Initial assumption, might be re-evaluated by app
        self.enabled = True 
        # self._discover_all() # Don't call discover here, let app trigger it or re-check
        print("INFO: SerialManager initialized. Discovery pending app configuration.")

    def configure_and_discover(self, app_config):
        """Called by the main app to configure based on app settings and run discovery if enabled."""
        self.enabled = app_config.get('SERIAL_COMMUNICATION_ENABLED', True)
        
        if self.enabled:
            print("INFO: Serial communication ENABLED by configuration. Starting discovery...")
            self._discover_all()
        else:
            self.ports = {} # Ensure ports are empty if disabled
            print("INFO: Serial communication is DISABLED by configuration. Discovery skipped.")

    # ──────────────────────────────
    def _discover_all(self):
        # This method only runs if self.enabled was True during __init__
        platform = sys.platform
        
        if platform.startswith("linux"):
            candidates = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
        elif platform.startswith("darwin"):  # macOS
            candidates = glob.glob("/dev/tty.usbserial*") + glob.glob("/dev/tty.usbmodem*")
        elif platform.startswith("win"):
            candidates = [f"COM{i}" for i in range(1, 21)]
        else:
            print(f"⚠️ Unknown platform: {platform}. No serial discovery.")
            return

        if not candidates:
            print("⚠️ No serial ports found.")
            return

        print(f"INFO: Scanning ports: {candidates}")

        for port in candidates:
            ser = None 
            try:
                # Initialize with the general long timeout.
                ser = serial.Serial(port, BAUD, timeout=TIMEOUT)
                time.sleep(2.0) # Increased settle time
                ser.reset_input_buffer()  # Explicitly clear buffers before discovery attempts
                ser.reset_output_buffer() # Explicitly clear buffers before discovery attempts
                
                original_port_timeout = ser.timeout
                found_rack_id = None

                for attempt in range(1, 10): # Try up to 3 times
                    ser.timeout = DISCOVERY_TIMEOUT # Set short timeout for this WHO attempt's readline
                    ser.reset_input_buffer() # Clear buffer before each attempt
                    
                    print(f"INFO: Port {port}: WHO Attempt {attempt}/3. Sending WHO command.")
                    ser.write(WHO_CMD)
                    time.sleep(0.05) # Small delay to ensure command is sent and Arduino has a moment
                    
                    print(f"INFO: Port {port}: WHO Attempt {attempt}/3. Listening for WHO reply (timeout: {DISCOVERY_TIMEOUT}s).")
                    reply_bytes = ser.readline()
                    print(f"DEBUG: Port {port}: WHO Attempt {attempt}/3. Raw reply_bytes: {reply_bytes}")

                    if reply_bytes:
                        decoded_reply = reply_bytes.decode("utf-8", "ignore").strip().upper()
                        if decoded_reply in RACKS:
                            if decoded_reply not in self.ports:
                                found_rack_id = decoded_reply
                                print(f"INFO: Port {port}: WHO Attempt {attempt}/3 successful. Received new rack ID '{found_rack_id}'.")
                                break # Successful discovery for this port, exit attempt loop
                            else:
                                print(f"⚠️ Port {port}: WHO Attempt {attempt}/3: Rack '{decoded_reply}' already discovered. This port will be closed.")
                                found_rack_id = None # Explicitly ensure this port isn't re-used for a duplicate rack
                                break # Stop attempts for this port, it's a duplicate
                        elif decoded_reply == OPTIONAL_MODULE_ID:
                            print(f"INFO: Port {port}: WHO Attempt {attempt}/3: Optional module detected.")
                            found_rack_id = decoded_reply
                            break
                        else:
                            print(f"⚠️ Port {port}: WHO Attempt {attempt}/3: Received unknown reply '{decoded_reply}'.")
                    else:
                        print(f"⚠️ Port {port}: WHO Attempt {attempt}/3: No reply to WHO command (timeout).")

                    if not found_rack_id and attempt < 3:
                        print(f"INFO: Port {port}: WHO Attempt {attempt}/3 failed. Pausing before next attempt.")
                        time.sleep(0.5) # Pause before next full send/listen attempt
                    elif found_rack_id and decoded_reply in self.ports: # Broke loop because it's a duplicate
                        pass # No further action needed here for duplicates, will be handled by found_rack_id being None for adding
                
                # After all attempts (or early exit on success/duplicate):
                ser.timeout = original_port_timeout # Restore original long timeout

                if found_rack_id: # A valid, non-duplicate rack ID was found
                    self.ports[found_rack_id] = {"ser": ser, "mutex": threading.Lock()}
                    print(f"🔌 Rack {found_rack_id} → {port}")
                else:
                    # If found_rack_id is still None, all attempts failed or it was a duplicate of an existing rack
                    print(f"INFO: Port {port}: Did not identify a valid new rack after 3 attempts or rack already mapped. Closing port.")
                    if ser and ser.is_open:
                        ser.close()

            except serial.SerialException as se:
                print(f"⚠️ {port}: Serial error during discovery: {se}")
                if ser and ser.is_open:
                    ser.close()
            except Exception as e:
                print(f"⚠️ {port}: Unexpected error during discovery: {e}")
                if ser and ser.is_open:
                    ser.close()

        missing = RACKS - self.ports.keys()
        if missing:
            print(f"⚠️ Missing racks: {', '.join(missing)}")

    # ──────────────────────────────
    def send(self, rack:str, code:str, wait_done=True, done_token=b"done", custom_max_echo_attempts: int = None):
        rack = rack.upper()
        if rack not in self.ports:
            raise RuntimeError(f"rack '{rack}' not mapped")
        entry = self.ports[rack]
        ser, mutex = entry["ser"], entry["mutex"]

        app_logger = None
        try:
            if current_app:
                app_logger = current_app.logger
        except RuntimeError:
            app_logger = None 

        log_prefix = f"SEND rack '{rack}', code '{code}'"
        
        active_max_echo_attempts = custom_max_echo_attempts if custom_max_echo_attempts is not None else DEFAULT_MAX_ECHO_ATTEMPTS
        echo_received_correctly = False
        
        # Initialize timing variables
        command_sent_time = None
        done_received_time = None

        with mutex:
            for attempt in range(1, active_max_echo_attempts + 1):
                ser.reset_input_buffer() # Reset buffer at the start of each command send attempt
                
                # Handle WHO command differently from numeric commands
                if code.upper() == "WHO":
                    ser.write(f"{code}\n".encode())
                else:
                    # Convert to integer and send as bytes
                    try:
                        cmd_int = int(code)
                        ser.write(f"{cmd_int}\n".encode())
                    except ValueError:
                        # If conversion fails, send as is
                        ser.write(f"{code}\n".encode())
                
                # Record exact time when command was sent to equipment
                command_sent_time = datetime.datetime.now().isoformat(timespec="microseconds")
                
                if app_logger:
                    app_logger.debug(f"{log_prefix} (Echo Attempt {attempt}/{active_max_echo_attempts}): Command sent at {command_sent_time}. Waiting for echo...")
                else:
                    print(f"INFO: {log_prefix} (Echo Attempt {attempt}/{active_max_echo_attempts}): Command sent at {command_sent_time}. Waiting for echo...")

                # 1. Wait for echo for this attempt
                echo_start_time = time.time()
                echo_buf = bytearray()
                # expected_echo = (code + "\r\n").encode() # Not used directly in this revised logic

                while time.time() - echo_start_time < ECHO_TIMEOUT:
                    if ser.in_waiting:
                        read_data = ser.read(ser.in_waiting)
                        echo_buf.extend(read_data)
                        if app_logger:
                            app_logger.debug(f"{log_prefix} (Echo Attempt {attempt}): Echo read data: {read_data}, Current echo_buf: {echo_buf}")
                        else:
                            print(f"DEBUG: {log_prefix} (Echo Attempt {attempt}): Echo read data: {read_data}, Current echo_buf: {echo_buf}")
                        
                        processed_echo_buf = echo_buf.decode(errors='ignore').strip()
                        if processed_echo_buf == code: # Exact match of the command string
                            echo_received_correctly = True
                            if app_logger:
                                app_logger.debug(f"{log_prefix} (Echo Attempt {attempt}): Correct echo '{code}' received.")
                            else:
                                print(f"INFO: {log_prefix} (Echo Attempt {attempt}): Correct echo '{code}' received.")
                            break # Break from inner echo-reading loop
                    time.sleep(0.05)
                
                if echo_received_correctly:
                    break # Break from outer command-sending attempt loop
                else:
                    if app_logger:
                        app_logger.warning(f"{log_prefix} (Echo Attempt {attempt}/{active_max_echo_attempts}): Failed to receive correct echo. Expected '{code}', Got buffer: {echo_buf}. Timeout: {ECHO_TIMEOUT}s")
                    else:
                        print(f"WARNING: {log_prefix} (Echo Attempt {attempt}/{active_max_echo_attempts}): Failed to receive correct echo. Expected '{code}', Got buffer: {echo_buf}. Timeout: {ECHO_TIMEOUT}s")
                    if attempt < active_max_echo_attempts:
                        time.sleep(0.5) # Pause before retrying command send
                        if app_logger:
                            app_logger.info(f"{log_prefix}: Retrying command send and echo wait (next attempt: {attempt+1})...")
                        else:
                            print(f"INFO: {log_prefix}: Retrying command send and echo wait (next attempt: {attempt+1})...")
            # End of echo attempt loop

            if not echo_received_correctly:
                # All attempts to get echo failed
                return {
                    "status": "echo_error_max_retries",
                    "command_sent_time": command_sent_time,
                    "done_received_time": None
                } 

            # If echo was successful, and we don't need to wait for "done", return status "sent_echo_confirmed"
            if not wait_done:
                return {
                    "status": "sent_echo_confirmed",
                    "command_sent_time": command_sent_time,
                    "done_received_time": None
                }

            # 2. Wait for "done" token (only if echo was successful)
            start_done_time = time.time()
            done_buf = bytearray() 
            
            if app_logger:
                app_logger.debug(f"{log_prefix}: Echo confirmed. Waiting for '{done_token}'")
            else:
                print(f"INFO: {log_prefix}: Echo confirmed. Waiting for '{done_token}'")

            while time.time() - start_done_time < TIMEOUT: 
                if ser.in_waiting:
                    read_data = ser.read(ser.in_waiting)
                    done_buf.extend(read_data)
                    if app_logger:
                        app_logger.debug(f"{log_prefix}: Done read data: {read_data}, Current done_buf: {done_buf}")
                    else:
                        print(f"DEBUG: {log_prefix}: Done read data: {read_data}, Current done_buf: {done_buf}")
                    
                    if done_token in done_buf.lower():
                        # Record exact time when "done" signal was received
                        done_received_time = datetime.datetime.now().isoformat(timespec="microseconds")
                        if app_logger:
                            app_logger.debug(f"{log_prefix}: Found '{done_token}' in done_buf at {done_received_time}.")
                        else:
                            print(f"DEBUG: {log_prefix}: Found '{done_token}' in done_buf at {done_received_time}.")
                        return {
                            "status": "done",
                            "command_sent_time": command_sent_time,
                            "done_received_time": done_received_time
                        }
                time.sleep(0.05)
            
            if app_logger:
                app_logger.warning(f"{log_prefix}: Timeout waiting for '{done_token}' after echo. Final done_buf: {done_buf}")
            else:
                print(f"WARNING: {log_prefix}: Timeout waiting for '{done_token}' after echo. Final done_buf: {done_buf}")
            return {
                "status": "timeout_after_echo",
                "command_sent_time": command_sent_time,
                "done_received_time": None
            }

    def _get_rack_logical_name(self, serial_instance, port_name):
        """
        Sends an identification command to the rack connected on serial_instance
        and attempts to read its logical name.

        Args:
            serial_instance (serial.Serial): An open serial port instance.
            port_name (str): The name of the port (e.g., /dev/ttyUSB0) for logging.

        Returns:
            str: The validated logical name (e.g., "A", "B", "C") or None if identification fails.
        """
        command = self.app_config.get('REPORT_LOGICAL_NAME_COMMAND', b'*WHO?\n')
        timeout = self.app_config.get('SERIAL_DISCOVERY_TIMEOUT_S', 2.0)
        expected_names = self.app_config.get('EXPECTED_RACK_NAMES', ["A", "B", "C"])
        response_prefix = self.app_config.get('RACK_NAME_RESPONSE_PREFIX', "NAME:") # e.g., "NAME:A"

        try:
            self.logger.debug(f"Port {port_name}: Sending command '{command.decode(errors='ignore').strip()}' to identify rack.")
            
            # Ensure port is clear before sending command
            if hasattr(serial_instance, 'reset_input_buffer'):
                serial_instance.reset_input_buffer()
            if hasattr(serial_instance, 'reset_output_buffer'):
                serial_instance.reset_output_buffer()

            serial_instance.write(command)
            
            # Temporarily set timeout for this read operation
            original_timeout = serial_instance.timeout
            serial_instance.timeout = timeout
            
            response_bytes = serial_instance.readline() # Read until newline
            
            # Restore original timeout
            serial_instance.timeout = original_timeout

            if not response_bytes:
                self.logger.warning(f"Port {port_name}: No response received from rack for ID command within {timeout}s.")
                return None

            response_str = response_bytes.decode('utf-8', errors='replace').strip()
            self.logger.info(f"Port {port_name}: Received ID response: '{response_str}'")

            # Example parsing: "NAME:A"
            if response_str.startswith(response_prefix):
                reported_name = response_str[len(response_prefix):].strip()
                if reported_name in expected_names:
                    self.logger.info(f"Port {port_name}: Successfully identified rack as '{reported_name}'.")
                    return reported_name
                else:
                    self.logger.warning(f"Port {port_name}: Rack reported an unexpected name '{reported_name}'. Expected one of {expected_names}.")
                    return None
            else:
                self.logger.warning(f"Port {port_name}: Rack response '{response_str}' did not match expected prefix '{response_prefix}'.")
                return None

        except serial.SerialTimeoutException:
            self.logger.warning(f"Port {port_name}: Timeout while waiting for rack ID response.")
            # Ensure original timeout is restored even on exception if it was changed
            if 'original_timeout' in locals() and serial_instance.isOpen():
                 serial_instance.timeout = original_timeout
            return None
        except Exception as e:
            self.logger.error(f"Port {port_name}: Error during rack identification: {e}", exc_info=True)
            # Ensure original timeout is restored
            if 'original_timeout' in locals() and serial_instance.isOpen():
                 serial_instance.timeout = original_timeout
            return None

    def reset_all_racks(self, reset_cmd_code="99", done_token_reset=b"done"):
        """Sends a reset command to all connected and discovered racks with increased echo retries.
           Uses print for logging as it runs during startup, potentially outside Flask app context.
        """
        if not self.enabled:
            print("INFO: SerialManager.reset_all_racks called but serial is DISABLED. Skipping reset.")
            return

        if not self.ports:
            print("INFO: SerialManager.reset_all_racks called but no racks are currently discovered/connected. Skipping reset.")
            return

        print(f"INFO: Attempting to reset all connected racks with command '{reset_cmd_code}' (echo attempts: {RESET_COMMAND_MAX_ECHO_ATTEMPTS})...")
        
        main_equipment_id = "M" # Define M equipment ID
        main_reset_done_token = b"fin" # M uses "fin" for reset completion
        
        for rack_id in self.ports.keys(): 
            print(f"INFO: Rack {rack_id}: Sending reset command '{reset_cmd_code}'...")
            
            current_done_token = done_token_reset # Default for A, B, C
            if rack_id == main_equipment_id:
                current_done_token = main_reset_done_token # Override for M
                print(f"INFO: Rack {rack_id} is Main equipment. Using '{main_reset_done_token.decode()}' as done token for reset.")

            try:
                result = self.send(
                    rack_id, 
                    reset_cmd_code,  # Send as string, encoding will be handled in send method
                    wait_done=True, 
                    done_token=current_done_token, # Use specific done token 
                    custom_max_echo_attempts=RESET_COMMAND_MAX_ECHO_ATTEMPTS
                )
                status = result.get("status")

                if status == "done": # "done" is the general success status from send() method
                    print(f"SUCCESS: Rack {rack_id}: Reset command '{reset_cmd_code}' COMPLETED. Arduino responded '{current_done_token.decode(errors='ignore')}'.")
                elif status == "echo_error_max_retries":
                    print(f"ERROR: Rack {rack_id}: Failed to get echo for reset command '{reset_cmd_code}' after {RESET_COMMAND_MAX_ECHO_ATTEMPTS} attempts.")
                elif status == "timeout_after_echo":
                    print(f"ERROR: Rack {rack_id}: Reset command '{reset_cmd_code}' echo OK, but TIMEOUT waiting for '{current_done_token.decode(errors='ignore')}'.")
                else: 
                    print(f"WARNING: Rack {rack_id}: Reset command '{reset_cmd_code}' resulted in unexpected status: '{status}'.")
            except RuntimeError as re:
                 print(f"ERROR: Rack {rack_id}: Runtime error during reset: {re} - rack might be disconnected.")
            except Exception as e:
                # Consider printing full traceback for unexpected errors during startup
                import traceback
                print(f"ERROR: Rack {rack_id}: Exception during reset command '{reset_cmd_code}': {e}")
                # traceback.print_exc() # Uncomment if more detail is needed here
        print("INFO: Finished attempting to reset all connected racks.")

    def check_optional_module_health(self):
        """Check if optional module is responding to WHO command.
        Returns True if module responds with 'X', False otherwise.
        Sends WHO command multiple times with retries like other equipment.
        """
        if not self.enabled:
            return False
            
        if OPTIONAL_MODULE_ID not in self.ports:
            return False
            
        try:
            entry = self.ports[OPTIONAL_MODULE_ID]
            ser, mutex = entry["ser"], entry["mutex"]
            
            with mutex:
                # Try multiple times like in discovery
                for attempt in range(1, 4):  # Try up to 3 times
                    ser.reset_input_buffer()  # Clear buffer before each attempt
                    ser.timeout = DISCOVERY_TIMEOUT  # Use short timeout for WHO
                    
                    print(f"INFO: Optional module health check attempt {attempt}/3. Sending WHO command.")
                    ser.write(WHO_CMD)
                    time.sleep(0.05)  # Small delay to ensure command is sent
                    
                    print(f"INFO: Optional module health check attempt {attempt}/3. Listening for WHO reply (timeout: {DISCOVERY_TIMEOUT}s).")
                    reply_bytes = ser.readline()
                    print(f"DEBUG: Optional module health check attempt {attempt}/3. Raw reply_bytes: {reply_bytes}")
                    
                    if reply_bytes:
                        decoded_reply = reply_bytes.decode("utf-8", "ignore").strip().upper()
                        if decoded_reply == OPTIONAL_MODULE_ID:
                            print(f"INFO: Optional module health check attempt {attempt}/3 successful. Received '{decoded_reply}'.")
                            return True
                        else:
                            print(f"⚠️ Optional module health check attempt {attempt}/3: Received unexpected reply '{decoded_reply}'.")
                    else:
                        print(f"⚠️ Optional module health check attempt {attempt}/3: No reply to WHO command (timeout).")
                    
                    if attempt < 3:
                        print(f"INFO: Optional module health check attempt {attempt}/3 failed. Pausing before next attempt.")
                        time.sleep(0.5)  # Pause before next attempt
                
                print(f"ERROR: Optional module health check failed after 3 attempts.")
                return False
                
        except Exception as e:
            print(f"ERROR: Optional module health check failed: {e}")
            return False
    
    def activate_optional_module(self):
        """Send activation command '1' to optional module.
        Returns True if command was sent successfully, False otherwise.
        """
        if not self.enabled:
            return False
            
        if OPTIONAL_MODULE_ID not in self.ports:
            return False
            
        try:
            result = self.send(OPTIONAL_MODULE_ID, "1", wait_done=False)
            return result.get("status") == "sent_echo_confirmed"
        except Exception as e:
            print(f"ERROR: Optional module activation failed: {e}")
            return False
    
    def is_optional_module_connected(self):
        """Check if optional module is discovered and connected."""
        return OPTIONAL_MODULE_ID in self.ports

# ───── 전역 인스턴스 (모듈 import 시 1번만 생성) ─────
serial_mgr = SerialManager()

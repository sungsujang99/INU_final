# serial_io.py
import serial, glob, time, threading, sys
from flask import current_app

BAUD = 9600
TIMEOUT = 120 # Increased timeout to 120 seconds (2 minutes)
DISCOVERY_TIMEOUT = 2 # Specific timeout for WHO command during discovery
WHO_CMD = b"WHO\n"
RACKS   = {"A", "B", "C"}

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
        candidates = []
        if platform.startswith('linux') or platform.startswith('cygwin'):
            candidates.extend(glob.glob("/dev/ttyACM*"))
            candidates.extend(glob.glob("/dev/ttyUSB*"))
        elif platform.startswith('darwin'):
            candidates.extend(glob.glob("/dev/tty.usbmodem*"))
            candidates.extend(glob.glob("/dev/tty.usbserial*"))
            candidates.extend(glob.glob("/dev/tty.SLAB_USBtoUART*"))
            candidates.extend(glob.glob("/dev/tty.wchusbserial*"))
            candidates.extend(glob.glob("/dev/ttyACM*"))
            candidates.extend(glob.glob("/dev/ttyUSB*"))
        elif platform.startswith('win'):
            candidates.extend(glob.glob("COM*"))
        
        if not candidates:
            candidates.extend(glob.glob("/dev/ttyACM*"))
            candidates.extend(glob.glob("/dev/ttyUSB*"))
            candidates.extend(glob.glob("/dev/tty.*"))

        candidates = sorted(list(set(candidates)))

        app_logger = None
        try:
            if current_app:
                app_logger = current_app.logger
        except RuntimeError:
            pass

        if app_logger:
            app_logger.debug(f"Serial port discovery: Platform '{platform}', Candidate ports: {candidates}")
        else:
            print(f"Serial port discovery: Platform '{platform}', Candidate ports: {candidates}")

        for port in candidates:
            ser = None # Initialize ser to None to handle potential errors before assignment
            try:
                # Initialize with the general long timeout. This will be the port's default.
                ser = serial.Serial(port, BAUD, timeout=TIMEOUT)
                time.sleep(2) # Allow device to settle after port opening
                ser.reset_input_buffer()

                # Temporarily set a shorter timeout for the WHO command
                original_port_timeout = ser.timeout
                ser.timeout = DISCOVERY_TIMEOUT
                
                ser.write(WHO_CMD)
                reply_bytes = ser.readline() # Read with the shorter discovery timeout

                # IMPORTANT: Restore the original long timeout for all subsequent operations on this port
                ser.timeout = original_port_timeout

                reply = reply_bytes.decode("utf-8", "ignore").strip().upper()

                if reply_bytes and reply in RACKS and reply not in self.ports:
                    self.ports[reply] = {"ser": ser, "mutex": threading.Lock()}
                    # The 'ser' object stored in self.ports now correctly has its timeout
                    # set back to the original TIMEOUT (120s) for future send() calls.
                    print(f"🔌 Rack {reply} → {port}")
                else:
                    # If WHO failed, timed out (reply_bytes is empty), or was invalid/duplicate, close the port.
                    if reply_bytes and reply not in RACKS:
                        print(f"⚠️ Port {port}: Received unknown reply '{reply}' to WHO command. Closing port.")
                    elif reply_bytes and reply in self.ports:
                        print(f"⚠️ Port {port}: Rack '{reply}' already discovered. Ignoring duplicate. Closing port.")
                    elif not reply_bytes:
                        print(f"⚠️ Port {port}: No reply to WHO command (timeout: {DISCOVERY_TIMEOUT}s). Closing port.")
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
    def send(self, rack:str, code:str, wait_done=True, done_token=b"done"):
        rack = rack.upper()
        if rack not in self.ports:
            raise RuntimeError(f"rack '{rack}' not mapped")
        entry = self.ports[rack]
        ser, mutex = entry["ser"], entry["mutex"]

        with mutex:
            ser.reset_input_buffer()
            ser.write((code + "\n").encode())
            if not wait_done:
                return {"status": "sent"}

            start = time.time()
            buf = bytearray()
            while time.time() - start < TIMEOUT:
                if ser.in_waiting:
                    buf.extend(ser.read(ser.in_waiting))
                    if done_token in buf.lower():
                        return {"status": "done"}
                time.sleep(0.01)
            return {"status": "timeout"}

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
        """Sends a reset command to all connected and discovered racks."""
        if not self.enabled:
            print("INFO: SerialManager.reset_all_racks called but serial is DISABLED. Skipping reset.")
            return

        if not self.ports:
            print("INFO: SerialManager.reset_all_racks called but no racks are currently discovered/connected. Skipping reset.")
            return

        print("INFO: Attempting to reset all connected racks (sending command twice per rack)...")
        for rack_id in self.ports.keys(): # Iterate over a copy of keys if modifying self.ports, but here it's just sending
            try:
                # First attempt
                print(f"INFO: Sending reset command '{reset_cmd_code}' to Rack {rack_id} (Attempt 1/2)...")
                result1 = self.send(rack_id, reset_cmd_code, wait_done=True, done_token=done_token_reset)
                if result1.get("status") == "done":
                    print(f"SUCCESS: Rack {rack_id} (Attempt 1/2) reset successfully and responded 'done'.")
                elif result1.get("status") == "timeout":
                    print(f"WARNING: Rack {rack_id} (Attempt 1/2) timed out after reset command. Did not receive 'done'.")
                else:
                    print(f"WARNING: Rack {rack_id} (Attempt 1/2) responded with status '{result1.get('status')}' after reset command.")

                # Second attempt
                print(f"INFO: Sending reset command '{reset_cmd_code}' to Rack {rack_id} (Attempt 2/2)...")
                result2 = self.send(rack_id, reset_cmd_code, wait_done=True, done_token=done_token_reset)
                if result2.get("status") == "done":
                    print(f"SUCCESS: Rack {rack_id} (Attempt 2/2) reset successfully and responded 'done'.")
                elif result2.get("status") == "timeout":
                    print(f"WARNING: Rack {rack_id} (Attempt 2/2) timed out after reset command. Did not receive 'done'.")
                else:
                    print(f"WARNING: Rack {rack_id} (Attempt 2/2) responded with status '{result2.get('status')}' after reset command.")

            except Exception as e:
                print(f"ERROR: Failed to send reset command sequence to Rack {rack_id}: {e}")
        print("INFO: Finished attempting to reset all connected racks.")

# ───── 전역 인스턴스 (모듈 import 시 1번만 생성) ─────
serial_mgr = SerialManager()

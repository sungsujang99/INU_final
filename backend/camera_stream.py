import io, threading, time, logging, sys, os
import lgpio
from picamera2 import Picamera2
import libcamera
from flask import Response, current_app
import cv2
import numpy as np

# Set Picamera2 logging to WARNING to suppress DEBUG output
logging.getLogger('picamera2').setLevel(logging.WARNING)

# Get a logger instance
logger = logging.getLogger(__name__)

def detect_cameras():
    """Detect available USB cameras and return the first working one"""
    logger.info("Detecting available cameras...")
    
    try:
        # Run v4l2-ctl to list devices
        import subprocess
        result = subprocess.run(['v4l2-ctl', '--list-devices'], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to list video devices: {result.stderr}")
            
        # Parse the output to find USB webcam devices
        lines = result.stdout.split('\n')
        usb_devices = []
        is_usb_section = False
        
        for line in lines:
            if 'Web Camera' in line or 'USB Camera' in line or 'Webcam' in line:
                is_usb_section = True
                continue
            elif line.strip() and not line.startswith('\t'):
                is_usb_section = False
            elif is_usb_section and line.startswith('\t'):
                # Extract device number from path
                device = line.strip()
                if device.startswith('/dev/video'):
                    try:
                        device_num = int(device.replace('/dev/video', ''))
                        usb_devices.append(device_num)
                    except ValueError:
                        continue
        
        logger.info(f"Found USB video devices: {usb_devices}")
        
        # Try each detected USB device
        for device_id in usb_devices:
            device_path = f"/dev/video{device_id}"
            try:
                logger.info(f"Testing camera at {device_path}...")
                cap = cv2.VideoCapture(device_path)
                
                if not cap.isOpened():
                    logger.info(f"Failed to open camera {device_path}")
                    continue
                
                # Try to read a frame
                ret, frame = cap.read()
                if not ret:
                    logger.info(f"Failed to read frame from camera {device_path}")
                    cap.release()
                    continue
                
                # Get camera properties
                width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                fps = cap.get(cv2.CAP_PROP_FPS)
                
                logger.info(f"Found working camera {device_path}:")
                logger.info(f"Resolution: {width}x{height}")
                logger.info(f"FPS: {fps}")
                
                cap.release()
                return device_id
                
            except Exception as e:
                logger.error(f"Error testing camera {device_path}: {e}")
                if 'cap' in locals():
                    cap.release()
        
        # If no camera found, raise error - we must have a working USB camera
        error_msg = "No working USB cameras found! Check if camera is connected and has correct permissions."
        logger.error(error_msg)
        raise RuntimeError(error_msg)
        
    except Exception as e:
        logger.error(f"Error during camera detection: {e}")
        raise

# Initialize GPIO for camera switching using lgpio (Pi 5 compatible)
try:
    gpio_chip = lgpio.gpiochip_open(0)  # Open GPIO chip 0
    # Setup GPIO pins as outputs (using BCM pin numbers)
    # BOARD pin 7 = BCM pin 4
    # BOARD pin 11 = BCM pin 17  
    # BOARD pin 12 = BCM pin 18
    lgpio.gpio_claim_output(gpio_chip, 4)   # Pin 7 (BOARD) = Pin 4 (BCM)
    lgpio.gpio_claim_output(gpio_chip, 17)  # Pin 11 (BOARD) = Pin 17 (BCM)
    lgpio.gpio_claim_output(gpio_chip, 18)  # Pin 12 (BOARD) = Pin 18 (BCM)
    logger.info("GPIO pins initialized successfully with lgpio")
except Exception as e:
    logger.error(f"GPIO initialization failed: {e}")
    gpio_chip = None

# Detect USB camera and configure camera settings
usb_camera_id = detect_cameras()
if usb_camera_id is not None:
    logger.info(f"Using USB camera at /dev/video{usb_camera_id}")
else:
    logger.warning("No USB camera detected, system may not work properly")
    usb_camera_id = 0  # Fallback to video0

# Camera switching configurations
CAMERA_CONFIGS = {
    0: {"type": "usb", "device": usb_camera_id, "name": "USB Camera"},  # USB webcam on detected device
    1: {"type": "arducam", "i2c_cmd": "i2cset -y 1 0x70 0x00 0x04", "gpio": (False, False, True), "name": "Camera A"},
    2: {"type": "arducam", "i2c_cmd": "i2cset -y 1 0x70 0x00 0x05", "gpio": (True, False, True), "name": "Camera B"},
    3: {"type": "arducam", "i2c_cmd": "i2cset -y 1 0x70 0x00 0x07", "gpio": (True, True, False), "name": "Camera C"}  # Using working configuration from test
}

def init_picamera():
    """Initialize Picamera2 with proper error handling"""
    try:
        # First, try to get camera info
        camera_list = Picamera2.global_camera_info()
        if not camera_list:
            logger.error("No cameras found by Picamera2")
            return None

        # Find the CSI camera (usually has 'imx219' in the name)
        csi_index = None
        for idx, cam in enumerate(camera_list):
            if 'imx219' in cam['Model'].lower():
                csi_index = idx
                break

        if csi_index is None:
            logger.error("No IMX219 camera found")
            return None

        # Initialize the camera
        picam = Picamera2(csi_index)
        
        # Create a simpler configuration that matches the IMX219 capabilities
        camera_config = picam.create_still_configuration(
            main={
                "size": (1920, 1080),
                "format": "RGB888"
            },
            raw={
                "size": picam.sensor_resolution
            },
            buffer_count=4,
            queue=True,
            controls={
                "ExposureTime": 20000,
                "AnalogueGain": 1.0
            }
        )

        # Apply the configuration
        picam.configure(camera_config)
        
        # Let the camera settle
        time.sleep(0.5)
        
        return picam
        
    except Exception as e:
        logger.error(f"Failed to initialize Picamera2: {e}")
        return None

class USBCamera:
    def __init__(self, device_id=0, width=640, height=480, fps=30):
        self.width = width
        self.height = height
        self.fps = fps
        self.device_id = device_id
        self.cap = None
        self.running = True
        self.frame = None
        self.camera_lock = threading.Lock()
        
        try:
            logger.info(f"Initializing USB camera (device {device_id})...")
            
            # Use direct device path
            device_path = f"/dev/video{device_id}"
            logger.info(f"Opening camera at {device_path}...")
            
            self.cap = cv2.VideoCapture(device_path)
            if not self.cap.isOpened():
                raise RuntimeError(f"Failed to open camera at {device_path}")
            
            # Configure camera settings
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.cap.set(cv2.CAP_PROP_FPS, fps)
            
            # Test capture
            ret, frame = self.cap.read()
            if not ret or frame is None:
                raise RuntimeError("Failed to capture test frame")
            
            # Verify camera settings
            actual_width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            logger.info(f"Camera settings - Requested: {width}x{height} @ {fps}fps")
            logger.info(f"Camera settings - Actual: {actual_width}x{actual_height} @ {actual_fps}fps")
            
            # Start capture thread
            self.capture_thread = threading.Thread(target=self._update, daemon=True)
            self.capture_thread.start()
            
        except Exception as e:
            logger.error(f"Error initializing USB camera: {e}")
            if self.cap is not None:
                self.cap.release()
            raise
            
    def _update(self):
        """Capture frames continuously"""
        logger.info("USB camera capture thread started")
        frame_count = 0
        last_log_time = time.time()
        
        while self.running:
            try:
                with self.camera_lock:
                    ret, frame = self.cap.read()
                    if ret and frame is not None:
                        # Convert BGR to RGB
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        # Encode to JPEG
                        ret, jpg = cv2.imencode(".jpg", frame_rgb, [cv2.IMWRITE_JPEG_QUALITY, 80])
                        if ret:
                            self.frame = jpg.tobytes()
                            frame_count += 1
                            
                            # Log frame rate every 5 seconds
                            current_time = time.time()
                            if current_time - last_log_time >= 5:
                                fps = frame_count / (current_time - last_log_time)
                                logger.info(f"USB Camera FPS: {fps:.2f}")
                                frame_count = 0
                                last_log_time = current_time
                        else:
                            logger.warning("Failed to encode frame to JPEG")
                    else:
                        logger.warning("Failed to capture frame from USB camera")
                
                time.sleep(1.0 / self.fps)
                        
            except Exception as e:
                logger.error(f"Error in USB camera capture loop: {e}")
                time.sleep(0.1)
                
    def stop(self):
        """Stop the camera"""
        logger.info("Stopping USB camera...")
        self.running = False
        if hasattr(self, 'capture_thread'):
            self.capture_thread.join(timeout=2.0)
        if self.cap:
            self.cap.release()
        logger.info("USB camera stopped")

def switch_camera(camera_num):
    """Switch to the specified camera using I2C and GPIO"""
    if camera_num not in CAMERA_CONFIGS:
        logger.error(f"Invalid camera number: {camera_num}")
        return False
    
    config = CAMERA_CONFIGS[camera_num]
    
    # If it's the USB camera, no switching needed
    if config["type"] == "usb":
        logger.info(f"Switching to {config['name']} (no hardware switch needed)")
        return True
    
    # For Arducam cameras, use GPIO switching
    if gpio_chip is None:
        logger.error("GPIO not available for Arducam switching")
        return False
        
    try:
        logger.info(f"Switching to {config['name']} (Camera {camera_num})...")
        
        # Execute I2C command
        os.system(config["i2c_cmd"])
        
        # Set GPIO pins using lgpio
        gpio_7, gpio_11, gpio_12 = config["gpio"]
        lgpio.gpio_write(gpio_chip, 4, 1 if gpio_7 else 0)
        lgpio.gpio_write(gpio_chip, 17, 1 if gpio_11 else 0)
        lgpio.gpio_write(gpio_chip, 18, 1 if gpio_12 else 0)
        
        # Wait for camera to stabilize
        time.sleep(1.0)
        
        logger.info(f"GPIO set: Pin 7={gpio_7}, Pin 11={gpio_11}, Pin 12={gpio_12}")
        return True
        
    except Exception as e:
        logger.error(f"Error switching to camera {camera_num}: {e}")
        return False

class MultiCamera:
    def __init__(self, width=640, height=480, fps=30):
        self.width = width
        self.height = height
        self.fps = fps
        self.current_camera = 0
        self.frame = None
        self.running = True
        self.camera_lock = threading.Lock()
        self.last_frame_time = time.time()
        self.error_count = 0
        self.last_recovery_attempt = 0
        self.RECOVERY_COOLDOWN = 10  # Wait 10 seconds between recovery attempts
        self.MAX_ERRORS = 3  # Number of errors before attempting recovery
        
        try:
            logger.info("Initializing multi-camera system...")
            self._init_cameras()
            
            # Start capture thread for Arducam cameras
            self.arducam_thread = threading.Thread(target=self._update, daemon=True)
            self.arducam_thread.start()
            
        except Exception as e:
            logger.error(f"Error initializing multi-camera system: {e}")
            self.cleanup()
            raise

    def _init_cameras(self):
        """Initialize cameras with error handling"""
        # Initialize USB camera for main camera (camera 0)
        logger.info("Setting up USB camera...")
        self.usb_camera = USBCamera(
            device_id=CAMERA_CONFIGS[0]["device"],
            width=self.width,
            height=self.height,
            fps=self.fps
        )
        
        # Initialize Picamera2 for Arducam cameras
        logger.info("Setting up Arducam cameras...")
        switch_camera(1)  # Start with first Arducam camera
        self.picam = init_picamera()
        if self.picam:
            logger.info("Picamera2 initialized successfully")
            self.picam.start()
            time.sleep(1)  # Wait for camera to stabilize
        else:
            logger.error("Failed to initialize Picamera2")

    def _attempt_camera_recovery(self):
        """Attempt to recover failed camera"""
        current_time = time.time()
        if current_time - self.last_recovery_attempt < self.RECOVERY_COOLDOWN:
            return False

        logger.info("Attempting camera recovery...")
        self.last_recovery_attempt = current_time
        
        try:
            # Stop and cleanup existing camera
            if hasattr(self, 'picam'):
                try:
                    self.picam.stop()
                    self.picam.close()
                except:
                    pass
                delattr(self, 'picam')

            # Reset GPIO pins
            if gpio_chip is not None:
                try:
                    lgpio.gpio_write(gpio_chip, 4, 0)
                    lgpio.gpio_write(gpio_chip, 17, 0)
                    lgpio.gpio_write(gpio_chip, 18, 1)
                    time.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error resetting GPIO: {e}")

            # Reinitialize camera
            if self.current_camera != 0:  # Only if not USB camera
                switch_camera(self.current_camera)
                self.picam = init_picamera()
                if self.picam:
                    self.picam.start()
                    time.sleep(1)
                    # Test capture
                    test_frame = self.picam.capture_array()
                    if test_frame is not None and test_frame.size > 0:
                        logger.info("Camera recovery successful")
                        self.error_count = 0
                        return True

            logger.error("Camera recovery failed")
            return False

        except Exception as e:
            logger.error(f"Error during camera recovery: {e}")
            return False

    def cleanup(self):
        """Clean up resources"""
        try:
            if hasattr(self, 'usb_camera'):
                self.usb_camera.stop()
            if hasattr(self, 'picam'):
                try:
                    self.picam.stop()
                    self.picam.close()
                except:
                    pass
            # Reset GPIO to default state
            if gpio_chip is not None:
                lgpio.gpio_write(gpio_chip, 4, 0)
                lgpio.gpio_write(gpio_chip, 17, 0)
                lgpio.gpio_write(gpio_chip, 18, 1)
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def set_camera(self, camera_num):
        """Switch to a specific camera"""
        if camera_num == self.current_camera:
            return True
            
        with self.camera_lock:
            try:
                logger.info(f"Switching from camera {self.current_camera} to camera {camera_num}")
                
                config = CAMERA_CONFIGS[camera_num]
                current_config = CAMERA_CONFIGS[self.current_camera]
                
                # Handle switching from USB to Arducam
                if current_config["type"] == "usb" and config["type"] == "arducam":
                    logger.info("Switching from USB to Arducam camera")
                    try:
                        # Initialize Picamera if needed
                        if not hasattr(self, 'picam'):
                            logger.info("Initializing Picamera2")
                            self.picam = init_picamera()
                            config = self.picam.create_preview_configuration(
                                main={"size": (self.width, self.height), "format": "RGB888"}
                            )
                            self.picam.configure(config)
                        
                        # Switch Arducam hardware first
                        if switch_camera(camera_num):
                            # Then start Picamera with error checking
                            try:
                                self.picam.start()
                                time.sleep(1)  # Wait for camera to start
                                
                                # Test capture to verify camera is working
                                test_frame = None
                                try:
                                    test_frame = self.picam.capture_array()
                                except Exception as capture_error:
                                    logger.error(f"Failed to capture test frame: {capture_error}")
                                    raise
                                
                                if test_frame is None or test_frame.size == 0:
                                    raise RuntimeError("Test capture returned empty frame")
                                
                                self.current_camera = camera_num
                                logger.info(f"Successfully switched to Arducam camera {camera_num}")
                                return True
                                
                            except Exception as start_error:
                                logger.error(f"Failed to start Arducam camera: {start_error}")
                                # Fallback to USB camera
                                logger.warning("Falling back to USB camera")
                                if hasattr(self, 'picam'):
                                    try:
                                        self.picam.stop()
                                        self.picam.close()
                                    except:
                                        pass
                                self.current_camera = 0  # USB camera
                                return True
                    except Exception as e:
                        logger.error(f"Error initializing Arducam camera: {e}")
                        # Fallback to USB camera
                        logger.warning("Falling back to USB camera")
                        if hasattr(self, 'picam'):
                            try:
                                self.picam.stop()
                                self.picam.close()
                            except:
                                pass
                        self.current_camera = 0  # USB camera
                        return True
                
                # Handle switching from Arducam to USB
                elif current_config["type"] == "arducam" and config["type"] == "usb":
                    logger.info("Switching from Arducam to USB camera")
                    # Stop and cleanup Picamera
                    if hasattr(self, 'picam'):
                        try:
                            self.picam.stop()
                            self.picam.close()
                        except Exception as e:
                            logger.error(f"Error stopping Picamera: {e}")
                    self.current_camera = camera_num
                    logger.info("Successfully switched to USB camera")
                    return True
                
                # Handle switching between Arducam cameras
                elif current_config["type"] == "arducam" and config["type"] == "arducam":
                    logger.info("Switching between Arducam cameras")
                    try:
                        # Stop current camera
                        if hasattr(self, 'picam'):
                            self.picam.stop()
                        
                        # Switch hardware
                        if switch_camera(camera_num):
                            # Restart camera with error handling
                            try:
                                self.picam.start()
                                time.sleep(1)  # Wait for camera to start
                                
                                # Test capture to verify camera is working
                                test_frame = None
                                try:
                                    test_frame = self.picam.capture_array()
                                except Exception as capture_error:
                                    logger.error(f"Failed to capture test frame: {capture_error}")
                                    raise
                                
                                if test_frame is None or test_frame.size == 0:
                                    raise RuntimeError("Test capture returned empty frame")
                                
                                self.current_camera = camera_num
                                logger.info(f"Successfully switched to camera {camera_num}")
                                return True
                                
                            except Exception as start_error:
                                logger.error(f"Error starting camera after switch: {start_error}")
                                # Fallback to USB camera
                                logger.warning("Falling back to USB camera")
                                if hasattr(self, 'picam'):
                                    try:
                                        self.picam.stop()
                                        self.picam.close()
                                    except:
                                        pass
                                self.current_camera = 0  # USB camera
                                return True
                    except Exception as e:
                        logger.error(f"Error during Arducam camera switch: {e}")
                        # Fallback to USB camera
                        logger.warning("Falling back to USB camera")
                        if hasattr(self, 'picam'):
                            try:
                                self.picam.stop()
                                self.picam.close()
                            except:
                                pass
                        self.current_camera = 0  # USB camera
                        return True
                
                # Handle switching between USB cameras (if we add more in the future)
                else:
                    self.current_camera = camera_num
                    logger.info(f"Switched to USB camera {camera_num}")
                    return True
                    
            except Exception as e:
                logger.error(f"Error switching to camera {camera_num}: {e}")
                # Fallback to USB camera
                logger.warning("Falling back to USB camera")
                if hasattr(self, 'picam'):
                    try:
                        self.picam.stop()
                        self.picam.close()
                    except:
                        pass
                self.current_camera = 0  # USB camera
                return True

    def _update(self):
        """Capture frames continuously with error recovery"""
        logger.info("Camera capture thread started")
        frame_count = 0
        last_log_time = time.time()
        
        while self.running:
            try:
                with self.camera_lock:
                    if self.current_camera == 0:
                        # USB camera
                        self.frame = self.usb_camera.frame
                        if self.frame is None:
                            self.error_count += 1
                            logger.warning(f"No frame from USB camera (error count: {self.error_count})")
                    else:
                        # Arducam camera
                        if not hasattr(self, 'picam'):
                            self.error_count += 1
                            logger.error(f"Picamera2 not initialized (error count: {self.error_count})")
                        else:
                            try:
                                arr = self.picam.capture_array()
                                if arr is not None:
                                    ret, jpg = cv2.imencode(".jpg", arr, [cv2.IMWRITE_JPEG_QUALITY, 80])
                                    if ret:
                                        self.frame = jpg.tobytes()
                                        frame_count += 1
                                        self.error_count = 0  # Reset error count on successful capture
                                        self.last_frame_time = time.time()
                                    else:
                                        self.error_count += 1
                                        logger.warning(f"Failed to encode Arducam frame (error count: {self.error_count})")
                                else:
                                    self.error_count += 1
                                    logger.warning(f"No frame from Arducam (error count: {self.error_count})")
                            except Exception as e:
                                self.error_count += 1
                                logger.error(f"Error capturing from Arducam: {e} (error count: {self.error_count})")

                    # Check if we need to attempt recovery
                    if self.error_count >= self.MAX_ERRORS:
                        if self._attempt_camera_recovery():
                            self.error_count = 0
                        else:
                            # If recovery failed and not USB camera, fall back to USB
                            if self.current_camera != 0:
                                logger.warning("Falling back to USB camera after failed recovery")
                                self.current_camera = 0
                                self.error_count = 0

                # Log frame rate every 5 seconds for Arducam
                if self.current_camera != 0:
                    current_time = time.time()
                    if current_time - last_log_time >= 5:
                        fps = frame_count / (current_time - last_log_time)
                        logger.info(f"Arducam Camera {self.current_camera} FPS: {fps:.2f}")
                        frame_count = 0
                        last_log_time = current_time

                time.sleep(1.0 / self.fps)
                        
            except Exception as e:
                logger.error(f"Error in capture loop: {e}")
                self.error_count += 1
                time.sleep(0.1)

    def get_generator(self, camera_num=None):
        """Get frame generator for specified camera"""
        if camera_num is not None and camera_num != self.current_camera:
            self.set_camera(camera_num)
            
        logger.info(f"Frame generator requested for camera {self.current_camera}")
        
        while True:
            try:
                frame = None
                with self.camera_lock:
                    frame = self.frame
                    # Check if frame is too old (more than 5 seconds)
                    if frame and time.time() - self.last_frame_time > 5:
                        logger.warning("Frame is too old, attempting recovery")
                        self._attempt_camera_recovery()
                        frame = None
                
                if frame:
                    yield b'--frame\r\n'
                    yield b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
                else:
                    logger.warning(f"No frame available for camera {self.current_camera}")
                    # If no frame available, send a blank frame or error image
                    blank_frame = self._generate_blank_frame()
                    yield b'--frame\r\n'
                    yield b'Content-Type: image/jpeg\r\n\r\n' + blank_frame + b'\r\n'
                time.sleep(1.0 / self.fps)
            except Exception as e:
                logger.error(f"Error in frame generator: {e}")
                break

    def _generate_blank_frame(self):
        """Generate a blank frame with error message"""
        height, width = 480, 640
        blank = np.zeros((height, width, 3), np.uint8)
        blank.fill(200)  # Light gray background
        
        # Add error message
        font = cv2.FONT_HERSHEY_SIMPLEX
        text = f"Camera {self.current_camera} Reconnecting..."
        textsize = cv2.getTextSize(text, font, 1, 2)[0]
        text_x = (width - textsize[0]) // 2
        text_y = (height + textsize[1]) // 2
        
        cv2.putText(blank, text, (text_x, text_y), font, 1, (0, 0, 0), 2)
        
        ret, jpg = cv2.imencode('.jpg', blank)
        if ret:
            return jpg.tobytes()
        return b''

    def stop(self):
        """Stop the camera system"""
        logger.info("Stopping multi-camera system...")
        self.running = False
        self.cleanup()

class CameraManager:
    def __init__(self):
        self.multi_camera = None
        self.available_cameras = [0, 1, 2, 3]  # USB webcam and three Arducam cameras
        self.initialize_camera()
    
    def initialize_camera(self):
        """Initialize the multi-camera system"""
        try:
            logger.info("Initializing camera manager with multi-camera adapter...")
            self.multi_camera = MultiCamera()
            logger.info("Camera manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize camera manager: {e}")
            self.multi_camera = None
    
    def get_available_cameras(self):
        """Get list of available camera numbers"""
        return self.available_cameras if self.multi_camera else []
    
    def get_camera_feed(self, camera_num):
        """Get MJPEG feed for a specific camera"""
        if not self.multi_camera:
            return Response(
                "Camera system not available",
                status=503,
                mimetype='text/plain'
            )
        
        if camera_num not in self.available_cameras:
            return Response(
                f"Camera {camera_num} not available",
                status=404,
                mimetype='text/plain'
            )
        
        return Response(
            self.multi_camera.get_generator(camera_num),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )
    
    def stop_all_cameras(self):
        """Stop the camera system"""
        if self.multi_camera:
            self.multi_camera.stop()

# Initialize camera manager
camera_manager = CameraManager()

def mjpeg_feed(camera_num=0):
    """Get MJPEG feed for specified camera"""
    logger.info(f"MJPEG feed requested for camera {camera_num}")
    return camera_manager.get_camera_feed(camera_num)

def get_available_cameras():
    """Get list of available cameras"""
    return camera_manager.get_available_cameras()

# Cleanup function for graceful shutdown
def cleanup_gpio():
    """Cleanup GPIO on shutdown"""
    try:
        lgpio.gpio_write(gpio_chip, 4, 0)
        lgpio.gpio_write(gpio_chip, 17, 0)
        lgpio.gpio_write(gpio_chip, 18, 1)
        lgpio.gpio_close(gpio_chip)
    except:
        pass

import atexit
atexit.register(cleanup_gpio)

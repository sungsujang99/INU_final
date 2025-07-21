import io, threading, time, logging, sys, os
import lgpio
from picamera2 import Picamera2
from libcamera import controls
from flask import Response, current_app
import cv2

# Set Picamera2 logging to WARNING to suppress DEBUG output
logging.getLogger('picamera2').setLevel(logging.WARNING)

# Get a logger instance
logger = logging.getLogger(__name__)

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

# Camera switching configurations
CAMERA_CONFIGS = {
    0: {"type": "usb", "device": 1, "name": "USB Camera"},  # USB webcam on /dev/video1
    1: {"type": "arducam", "i2c_cmd": "i2cset -y 1 0x70 0x00 0x05", "gpio": (True, False, True), "name": "Camera B"},
    2: {"type": "arducam", "i2c_cmd": "i2cset -y 1 0x70 0x00 0x06", "gpio": (False, True, False), "name": "Camera C"},
    3: {"type": "arducam", "i2c_cmd": "i2cset -y 1 0x70 0x00 0x07", "gpio": (True, True, False), "name": "Camera D"}
}

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
            
            # Try different methods to open the camera
            methods = [
                (lambda: cv2.VideoCapture(device_id), "index"),
                (lambda: cv2.VideoCapture(f"/dev/video{device_id}"), "device path"),
                (lambda: cv2.VideoCapture(f"v4l2:///dev/video{device_id}"), "v4l2 path")
            ]
            
            success = False
            error_messages = []
            
            for open_method, method_name in methods:
                try:
                    logger.info(f"Trying to open camera using {method_name}...")
                    self.cap = open_method()
                    
                    if self.cap is None:
                        error_messages.append(f"Method {method_name}: VideoCapture returned None")
                        continue
                        
                    if not self.cap.isOpened():
                        error_messages.append(f"Method {method_name}: Camera failed to open")
                        self.cap.release()
                        self.cap = None
                        continue
                    
                    # Try to read a test frame
                    ret, frame = self.cap.read()
                    if not ret or frame is None:
                        error_messages.append(f"Method {method_name}: Could not read test frame")
                        self.cap.release()
                        self.cap = None
                        continue
                    
                    # If we got here, the camera is working
                    logger.info(f"Successfully opened camera using {method_name}")
                    success = True
                    break
                    
                except Exception as e:
                    error_messages.append(f"Method {method_name}: {str(e)}")
                    if self.cap is not None:
                        self.cap.release()
                        self.cap = None
            
            if not success:
                error_msg = "Failed to open USB camera. Tried:\n" + "\n".join(error_messages)
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            # Configure camera settings
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.cap.set(cv2.CAP_PROP_FPS, fps)
            
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
    """Switch to the specified camera using I2C and GPIO (from working demo)"""
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
        
        # Delay for camera switching (same as demo)
        time.sleep(1)
        
        logger.info(f"GPIO set: Pin 7={gpio_7}, Pin 11={gpio_11}, Pin 12={gpio_12}")
        return True
        
    except Exception as e:
        logger.error(f"Error switching to camera {camera_num}: {e}")
        return False

class MultiCamera:
    def __init__(self, width=640, height=480, fps=30):  # Updated default resolution and fps
        self.width = width
        self.height = height
        self.fps = fps
        self.current_camera = 0
        self.frame = None
        self.running = True
        self.camera_lock = threading.Lock()
        
        try:
            logger.info("Initializing multi-camera system...")
            
            # Initialize USB camera for main camera (camera 0)
            logger.info("Setting up USB camera...")
            self.usb_camera = USBCamera(
                device_id=CAMERA_CONFIGS[0]["device"],
                width=width,
                height=height,
                fps=fps
            )
            
            # Initialize Picamera2 for Arducam cameras
            logger.info("Setting up Arducam cameras...")
            switch_camera(1)  # Start with first Arducam camera
            self.picam = Picamera2(0)
            config = self.picam.create_preview_configuration(
                main={"size": (width, height), "format": "RGB888"}
            )
            self.picam.configure(config)
            self.picam.start()
            time.sleep(2)
            
            logger.info("Multi-camera system initialized successfully")
            
            # Start capture thread for Arducam cameras
            self.arducam_thread = threading.Thread(target=self._update, daemon=True)
            self.arducam_thread.start()
            
        except Exception as e:
            logger.error(f"Error initializing multi-camera system: {e}")
            self.cleanup()
            raise

    def cleanup(self):
        """Clean up resources"""
        try:
            if hasattr(self, 'usb_camera'):
                self.usb_camera.stop()
            if hasattr(self, 'picam'):
                self.picam.stop()
                self.picam.close()
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
                            self.picam = Picamera2(0)
                            config = self.picam.create_preview_configuration(
                                main={"size": (self.width, self.height), "format": "RGB888"}
                            )
                            self.picam.configure(config)
                        
                        # Switch Arducam hardware first
                        if switch_camera(camera_num):
                            # Then start Picamera
                            self.picam.start()
                            time.sleep(2)  # Allow camera to settle
                            self.current_camera = camera_num
                            logger.info(f"Successfully switched to Arducam camera {camera_num}")
                            return True
                    except Exception as e:
                        logger.error(f"Error initializing Arducam camera: {e}")
                        # Try to reinitialize Picamera
                        try:
                            if hasattr(self, 'picam'):
                                self.picam.close()
                                del self.picam
                            self.picam = Picamera2(0)
                            config = self.picam.create_preview_configuration(
                                main={"size": (self.width, self.height), "format": "RGB888"}
                            )
                            self.picam.configure(config)
                            if switch_camera(camera_num):
                                self.picam.start()
                                time.sleep(2)
                                self.current_camera = camera_num
                                logger.info("Successfully reinitialized Arducam camera")
                                return True
                        except Exception as reinit_error:
                            logger.error(f"Failed to reinitialize Arducam camera: {reinit_error}")
                    return False
                
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
                                time.sleep(2)  # Allow camera to settle
                                self.current_camera = camera_num
                                logger.info(f"Successfully switched to camera {camera_num}")
                                return True
                            except Exception as start_error:
                                logger.error(f"Error starting camera after switch: {start_error}")
                                # Try to reinitialize Picamera
                                try:
                                    self.picam.close()
                                    self.picam = Picamera2(0)
                                    config = self.picam.create_preview_configuration(
                                        main={"size": (self.width, self.height), "format": "RGB888"}
                                    )
                                    self.picam.configure(config)
                                    self.picam.start()
                                    time.sleep(2)
                                    self.current_camera = camera_num
                                    logger.info("Successfully reinitialized camera after error")
                                    return True
                                except Exception as reinit_error:
                                    logger.error(f"Failed to reinitialize camera: {reinit_error}")
                    except Exception as e:
                        logger.error(f"Error during Arducam camera switch: {e}")
                    
                    # If we get here, something went wrong
                    logger.error(f"Failed to switch to camera {camera_num}, attempting to restore camera {self.current_camera}")
                    try:
                        if switch_camera(self.current_camera):
                            if hasattr(self, 'picam'):
                                self.picam.start()
                            logger.info(f"Restored camera {self.current_camera}")
                        else:
                            logger.error("Failed to restore previous camera")
                    except Exception as restore_error:
                        logger.error(f"Error restoring previous camera: {restore_error}")
                    return False
                
                # Handle switching between USB cameras (if we add more in the future)
                else:
                    self.current_camera = camera_num
                    logger.info(f"Switched to USB camera {camera_num}")
                    return True
                    
            except Exception as e:
                logger.error(f"Error switching to camera {camera_num}: {e}")
                # Try to restore previous state
                try:
                    if CAMERA_CONFIGS[self.current_camera]["type"] == "arducam":
                        switch_camera(self.current_camera)
                        if hasattr(self, 'picam'):
                            self.picam.start()
                except Exception as restore_error:
                    logger.error(f"Error restoring previous camera state: {restore_error}")
                return False

    def _update(self):
        """Capture frames continuously from Arducam cameras"""
        logger.info("Arducam capture thread started")
        frame_count = 0
        last_log_time = time.time()
        
        while self.running:
            try:
                with self.camera_lock:
                    # Only capture from Picamera2 if current camera is not USB
                    if self.current_camera != 0:
                        try:
                            arr = self.picam.capture_array()
                            if arr is not None:
                                ret, jpg = cv2.imencode(".jpg", arr, [cv2.IMWRITE_JPEG_QUALITY, 80])
                                if ret:
                                    self.frame = jpg.tobytes()
                                    frame_count += 1
                                else:
                                    logger.warning("Failed to encode Arducam frame to JPEG")
                            else:
                                logger.warning("Failed to capture Arducam frame")
                        except Exception as e:
                            logger.warning(f"Capture error on camera {self.current_camera}: {e}")
                    else:
                        # For USB camera, use its frame
                        self.frame = self.usb_camera.frame
                        if self.frame is None:
                            logger.warning("No frame available from USB camera")
                
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
                
                if frame:
                    yield b'--frame\r\n'
                    yield b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
                else:
                    logger.warning(f"No frame available for camera {self.current_camera}")
                time.sleep(1.0 / self.fps)
            except Exception as e:
                logger.error(f"Error in frame generator: {e}")
                break

    def stop(self):
        """Stop the camera system"""
        logger.info("Stopping multi-camera system...")
        self.running = False
        self.cleanup()

class CameraManager:
    def __init__(self):
        self.multi_camera = None
        self.available_cameras = [0, 1, 2, 3]  # All 4 cameras available with adapter
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

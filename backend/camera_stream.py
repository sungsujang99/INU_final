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

# Camera switching configurations (same as working demo)
CAMERA_CONFIGS = {
    0: {"type": "usb", "device": 0, "name": "USB Camera"},  # Main camera is now USB
    1: {"type": "arducam", "i2c_cmd": "i2cset -y 1 0x70 0x00 0x05", "gpio": (True, False, True), "name": "Camera B"},
    2: {"type": "arducam", "i2c_cmd": "i2cset -y 1 0x70 0x00 0x06", "gpio": (False, True, False), "name": "Camera C"},
    3: {"type": "arducam", "i2c_cmd": "i2cset -y 1 0x70 0x00 0x07", "gpio": (True, True, False), "name": "Camera D"}
}

class USBCamera:
    def __init__(self, device_id=0, width=320, height=240, fps=15):
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
            self.cap = cv2.VideoCapture(device_id)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.cap.set(cv2.CAP_PROP_FPS, fps)
            
            if not self.cap.isOpened():
                raise RuntimeError(f"Failed to open USB camera {device_id}")
                
            logger.info("USB camera initialized successfully")
            
            # Start capture thread
            threading.Thread(target=self._update, daemon=True).start()
            
        except Exception as e:
            logger.error(f"Error initializing USB camera: {e}")
            raise
            
    def _update(self):
        """Capture frames continuously"""
        logger.info("USB camera capture thread started")
        
        while self.running:
            try:
                with self.camera_lock:
                    ret, frame = self.cap.read()
                    if ret:
                        # Convert BGR to RGB
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        # Encode to JPEG
                        ret, jpg = cv2.imencode(".jpg", frame_rgb, [cv2.IMWRITE_JPEG_QUALITY, 80])
                        if ret:
                            self.frame = jpg.tobytes()
                            
                time.sleep(1.0 / self.fps)
                        
            except Exception as e:
                logger.error(f"Error in USB camera capture loop: {e}")
                time.sleep(0.1)
                
    def stop(self):
        """Stop the camera"""
        self.running = False
        if self.cap:
            self.cap.release()

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
    def __init__(self, width=320, height=240, fps=15):
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
            self.usb_camera = USBCamera(
                device_id=CAMERA_CONFIGS[0]["device"],
                width=width,
                height=height,
                fps=fps
            )
            
            # Initialize Picamera2 for Arducam cameras
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
            threading.Thread(target=self._update, daemon=True).start()
            
        except Exception as e:
            logger.error(f"Error initializing multi-camera system: {e}")
            raise

    def set_camera(self, camera_num):
        """Switch to a specific camera"""
        if camera_num == self.current_camera:
            return True
            
        with self.camera_lock:
            try:
                logger.info(f"Switching from camera {self.current_camera} to camera {camera_num}")
                
                config = CAMERA_CONFIGS[camera_num]
                
                if config["type"] == "usb":
                    # Stop Picamera if it's running
                    if hasattr(self, 'picam'):
                        self.picam.stop()
                    self.current_camera = camera_num
                    logger.info(f"Switched to USB camera")
                    return True
                else:
                    # Stop current camera if it's USB
                    if self.current_camera == 0:
                        self.picam.start()
                    
                    # Switch Arducam hardware
                    if switch_camera(camera_num):
                        self.current_camera = camera_num
                        logger.info(f"Successfully switched to camera {camera_num}")
                        return True
                    else:
                        # If switch failed, try to restore previous camera
                        switch_camera(self.current_camera)
                        logger.error(f"Failed to switch to camera {camera_num}, restored camera {self.current_camera}")
                        return False
                    
            except Exception as e:
                logger.error(f"Error switching to camera {camera_num}: {e}")
                return False

    def _update(self):
        """Capture frames continuously from Arducam cameras"""
        logger.info("Arducam capture thread started")
        
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
                        except Exception as e:
                            logger.warning(f"Capture error on camera {self.current_camera}: {e}")
                    else:
                        # For USB camera, use its frame
                        self.frame = self.usb_camera.frame
                
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
                if self.frame:
                    yield b'--frame\r\n'
                    yield b'Content-Type: image/jpeg\r\n\r\n' + self.frame + b'\r\n'
                time.sleep(1.0 / self.fps)
            except Exception as e:
                logger.error(f"Error in frame generator: {e}")
                break

    def stop(self):
        """Stop the camera system"""
        self.running = False
        try:
            self.usb_camera.stop()
            if hasattr(self, 'picam'):
                self.picam.stop()
                self.picam.close()
            # Reset GPIO to default state
            lgpio.gpio_write(gpio_chip, 4, 0)
            lgpio.gpio_write(gpio_chip, 17, 0)
            lgpio.gpio_write(gpio_chip, 18, 1)
        except Exception as e:
            logger.error(f"Error stopping camera system: {e}")

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

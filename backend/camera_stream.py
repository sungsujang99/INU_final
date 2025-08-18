import cv2
import numpy as np
import logging
import time
import threading
from picamera2 import Picamera2
import lgpio
import os
from typing import Optional, Dict, Union
from flask import Response

# Set Picamera2 logging to WARNING to suppress DEBUG output
logging.getLogger('picamera2').setLevel(logging.WARNING)

# Get a logger instance
logger = logging.getLogger(__name__)

# Camera configurations
CAMERA_CONFIG = {
    'M': {
        'type': 'usb',
        'device': '/dev/video1',
        'name': 'Main Camera'
    },
    'A': {
        'type': 'usb',
        'device': '/dev/video3',
        'name': 'Rack A Camera'
    },
    'B': {
        'type': 'usb',
        'device': '/dev/video5',
        'name': 'Rack B Camera'
    },
    'C': {
        'type': 'usb',
        'device': '/dev/video7',
        'name': 'Rack C Camera'
    }
}

class USBCamera:
    def __init__(self, device_path: str, name: str):
        self.device_path = device_path
        self.name = name
        self.cap = None
        self.frame = None
        self.last_frame_time = 0
        self.lock = threading.Lock()
        self.running = True
        
    def start(self):
        """Start the camera"""
        logger.info(f"Starting {self.name} at {self.device_path}")
        self.running = True
        return self._init_camera()
        
    def _init_camera(self) -> bool:
        """Initialize the camera"""
        try:
            # Try different backends for better compatibility
            backends = [cv2.CAP_V4L2, cv2.CAP_ANY]
            
            for backend in backends:
                try:
                    self.cap = cv2.VideoCapture(self.device_path, backend)
                    if not self.cap.isOpened():
                        continue
                        
                    # Set basic properties
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    self.cap.set(cv2.CAP_PROP_FPS, 30)
                    
                    # Wait a moment for camera to stabilize
                    time.sleep(0.5)
                    
                    # Test capture multiple times
                    for attempt in range(3):
                        ret, frame = self.cap.read()
                        if ret and frame is not None:
                            with self.lock:
                                self.frame = frame
                                self.last_frame_time = time.time()
                            logger.info(f"Successfully initialized {self.name} with backend {backend}")
                            return True
                        time.sleep(0.2)
                    
                    # If we get here, capture failed
                    self.cap.release()
                    self.cap = None
                    
                except Exception as e:
                    logger.debug(f"Backend {backend} failed for {self.name}: {e}")
                    if self.cap:
                        try:
                            self.cap.release()
                        except:
                            pass
                        self.cap = None
                    continue
            
            logger.error(f"Failed to initialize {self.name} at {self.device_path} with any backend")
            return False
            
        except Exception as e:
            logger.error(f"Error initializing {self.name}: {e}")
            return False
            
    def get_frame(self) -> Optional[np.ndarray]:
        """Get the latest frame"""
        try:
            if not self.cap or not self.cap.isOpened():
                if not self._init_camera():
                    return None
                    
            ret, frame = self.cap.read()
            if ret and frame is not None:
                with self.lock:
                    self.frame = frame
                    self.last_frame_time = time.time()
                return frame
            return None
        except Exception as e:
            logger.error(f"Error capturing frame from {self.name}: {e}")
            return None
            
    def stop(self):
        """Stop the camera"""
        self.running = False
        if self.cap:
            self.cap.release()
            self.cap = None

class ArducamMultiCamera:
    picam2 = None
    gpio_chip = None
    current_camera = None
    
    def __init__(self, name: str, i2c_cmd: str, gpio_sta: list):
        self.name = name
        self.i2c_cmd = i2c_cmd
        self.gpio_sta = gpio_sta
        self.frame = None
        self.last_frame_time = 0
        self.lock = threading.Lock()
        self.running = True
        
        # Initialize GPIO exactly like test code
        if not self.__class__.gpio_chip:
            try:
                self.__class__.gpio_chip = lgpio.gpiochip_open(0)
                # Setup GPIO pins as outputs (using BCM pin numbers)
                lgpio.gpio_claim_output(self.__class__.gpio_chip, 4)   # Pin 7 (BOARD) = Pin 4 (BCM)
                lgpio.gpio_claim_output(self.__class__.gpio_chip, 17)  # Pin 11 (BOARD) = Pin 17 (BCM)
                lgpio.gpio_claim_output(self.__class__.gpio_chip, 18)  # Pin 12 (BOARD) = Pin 18 (BCM)
                logger.info("GPIO initialized successfully")
            except Exception as e:
                logger.error(f"GPIO initialization failed: {e}")
                self.__class__.gpio_chip = None
                raise
                
        # Initialize camera if not already initialized
        if not self.__class__.picam2:
            try:
                self.__class__.picam2 = Picamera2(0)
                config = self.__class__.picam2.create_preview_configuration(
                    main={"size": (640, 480), "format": "RGB888"}
                )
                self.__class__.picam2.configure(config)
                self.__class__.picam2.start()
                time.sleep(2)  # Wait for camera to initialize
                logger.info("Camera system initialized")
            except Exception as e:
                logger.error(f"Camera initialization failed: {e}")
                self.__class__.picam2 = None
                raise

    def select_channel(self):
        """Set GPIO pins exactly like test code"""
        try:
            # Only change GPIO if we're switching to a different camera
            if self.__class__.current_camera != self:
                logger.info(f"Switching to camera: {self.name}")
                
                # Reset all pins first
                lgpio.gpio_write(self.__class__.gpio_chip, 4, 0)    # Pin 7
                lgpio.gpio_write(self.__class__.gpio_chip, 17, 0)  # Pin 11
                lgpio.gpio_write(self.__class__.gpio_chip, 18, 0)  # Pin 12
                time.sleep(0.1)  # Brief wait for pins to settle
                
                # Set new pin states
                lgpio.gpio_write(self.__class__.gpio_chip, 4, 1 if self.gpio_sta[0] else 0)    # Pin 7
                lgpio.gpio_write(self.__class__.gpio_chip, 17, 1 if self.gpio_sta[1] else 0)  # Pin 11
                lgpio.gpio_write(self.__class__.gpio_chip, 18, 1 if self.gpio_sta[2] else 0)  # Pin 12
                time.sleep(0.1)  # Brief wait for pins to settle
                logger.info(f"GPIO set: Pin 7={self.gpio_sta[0]}, Pin 11={self.gpio_sta[1]}, Pin 12={self.gpio_sta[2]}")
                
                # Execute I2C command after GPIO change
                self.init_i2c()
                
                # Update current camera
                self.__class__.current_camera = self
                
                # Wait for camera to settle after switching
                time.sleep(0.2)
        except Exception as e:
            logger.error(f"Error setting GPIO: {e}")
            raise
        
    def init_i2c(self):
        """Execute I2C command"""
        result = os.system(self.i2c_cmd)
        if result != 0:
            logger.error(f"I2C command failed with code {result}")
            raise RuntimeError(f"I2C command failed: {self.i2c_cmd}")
        
    def start(self):
        logger.info(f"Starting {self.name}")
        self.running = True
        
    def get_frame(self):
        try:
            with self.lock:  # Use lock to prevent concurrent camera access
                # Set GPIO pins for this camera
                self.select_channel()
                
                # Try to capture a frame
                if self.__class__.picam2:
                    array = self.__class__.picam2.capture_array()
                    if array is not None:
                        self.frame = array
                        self.last_frame_time = time.time()
                        return array
                    
                return self._generate_blank_frame(f"No frame from {self.name}")
                
        except Exception as e:
            logger.error(f"Error capturing frame from {self.name}: {e}")
            return self._generate_blank_frame(f"Error: {str(e)}")
            
    def _generate_blank_frame(self, message: str) -> np.ndarray:
        """Generate a blank frame with error message"""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame.fill(32)
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        thickness = 2
        text_size = cv2.getTextSize(message, font, font_scale, thickness)[0]
        text_x = (frame.shape[1] - text_size[0]) // 2
        text_y = (frame.shape[0] + text_size[1]) // 2
        cv2.putText(frame, message, (text_x, text_y), font, font_scale, (255, 255, 255), thickness)
        return frame
            
    def stop(self):
        self.running = False
        # Reset GPIO pins to default state only if this camera was the current one
        if self.__class__.current_camera == self:
            if self.__class__.gpio_chip:
                try:
                    lgpio.gpio_write(self.__class__.gpio_chip, 4, 0)    # Pin 7
                    lgpio.gpio_write(self.__class__.gpio_chip, 17, 0)  # Pin 11
                    lgpio.gpio_write(self.__class__.gpio_chip, 18, 1)  # Pin 12
                    self.__class__.current_camera = None
                except:
                    pass

class CameraManager:
    def __init__(self):
        self.cameras: Dict[str, Union[USBCamera, ArducamMultiCamera]] = {}
        
    def _init_camera(self, rack_id: str) -> bool:
        """Initialize a specific camera"""
        if rack_id in self.cameras:
            return True
            
        config = CAMERA_CONFIG.get(rack_id)
        if not config:
            return False
            
        try:
            if config['type'] == 'usb':
                camera = USBCamera(config['device'], config['name'])
            else:  # arducam
                camera = ArducamMultiCamera(
                    config['name'],
                    config['i2c_cmd'],
                    config['gpio_sta']
                )
            
            if camera.start():
                self.cameras[rack_id] = camera
                logger.info(f"Successfully initialized camera {rack_id}")
                return True
            else:
                logger.error(f"Failed to start camera {rack_id}")
                return False
        except Exception as e:
            logger.error(f"Error initializing camera {rack_id}: {e}")
            return False
            
    def get_frame(self, rack_id: str) -> Optional[np.ndarray]:
        """Get frame from specific camera"""
        # Initialize camera on first access
        if rack_id not in self.cameras:
            if not self._init_camera(rack_id):
                return None
                
        camera = self.cameras.get(rack_id)
        if camera:
            return camera.get_frame()
        return None
        
    def get_generator(self, rack_id: str):
        """Generate MJPEG stream for a specific camera"""
        frame_interval = 0.2  # 200ms between frames (5 FPS)
        last_frame_time = 0
        
        while True:
            try:
                current_time = time.time()
                if current_time - last_frame_time >= frame_interval:
                    frame = self.get_frame(rack_id)
                    if frame is not None:
                        ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                        if ret:
                            yield (b'--frame\r\n'
                                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
                            last_frame_time = current_time
                time.sleep(0.05)  # Sleep to prevent busy waiting
            except Exception as e:
                logger.error(f"Error in frame generator for {rack_id}: {e}")
                time.sleep(0.5)
        
    def get_available_cameras(self) -> list:
        """Get list of available cameras"""
        return list(self.cameras.keys())
        
    def stop(self):
        """Stop all cameras"""
        for camera in self.cameras.values():
            camera.stop()
        # Stop the shared camera instance
        if ArducamMultiCamera.picam2:
            try:
                ArducamMultiCamera.picam2.stop()
                ArducamMultiCamera.picam2.close()
            except:
                pass
            ArducamMultiCamera.picam2 = None
        if ArducamMultiCamera.gpio_chip:
            lgpio.gpio_close(ArducamMultiCamera.gpio_chip)

# Global camera manager instance
camera_manager = CameraManager()

def mjpeg_feed(rack_id: str = 'M'):
    """Get MJPEG feed for specified rack"""
    logger.info(f"MJPEG feed requested for rack {rack_id}")
    return Response(
        camera_manager.get_generator(rack_id),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

def get_available_cameras():
    """Get list of available cameras"""
    try:
        return camera_manager.get_available_cameras()
    except Exception as e:
        logger.error(f"Error getting available cameras: {e}")
        return []

import cv2
import numpy as np
import logging
import time
import threading
from picamera2 import Picamera2
from gpiozero import DigitalOutputDevice
import os
from typing import Optional, Dict, Union
from flask import Response

# Set Picamera2 logging to WARNING to suppress DEBUG output
logging.getLogger('picamera2').setLevel(logging.WARNING)

# Get a logger instance
logger = logging.getLogger(__name__)

# Camera configurations for Arducam Multi-Camera Adapter v2.2
CAMERA_CONFIG = {
    'M': {
        'type': 'usb',
        'device': '/dev/video8',
        'name': 'Main Camera'
    },
    'A': {
        'type': 'arducam',
        'name': 'Rack A Camera',
        'i2c_cmd': 'i2cset -y 10 0x70 0x00 0x04',
        'gpio_sta': [0, 0, 1]  # GPIO 7, 11, 12 states
    },
    'B': {
        'type': 'arducam',
        'name': 'Rack B Camera',
        'i2c_cmd': 'i2cset -y 10 0x70 0x00 0x05',
        'gpio_sta': [1, 0, 1]
    },
    'C': {
        'type': 'arducam',
        'name': 'Rack C Camera',
        'i2c_cmd': 'i2cset -y 10 0x70 0x00 0x06',
        'gpio_sta': [0, 1, 0]
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
        self.recovery_in_progress = False
        self.last_recovery_attempt = 0
        self.RECOVERY_COOLDOWN = 2.0
        
    def start(self):
        """Start the camera"""
        logger.info(f"Starting {self.name} at {self.device_path}")
        self.running = True
        self._init_camera()
        
    def _init_camera(self) -> bool:
        """Initialize the camera"""
        try:
            if self.cap:
                self.cap.release()
                
            self.cap = cv2.VideoCapture(self.device_path)
            if not self.cap.isOpened():
                logger.error(f"Failed to open {self.name} at {self.device_path}")
                return False
                
            # Set camera properties
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            
            # Test capture
            ret, frame = self.cap.read()
            if not ret or frame is None:
                logger.error(f"Failed to capture test frame from {self.name}")
                return False
                
            with self.lock:
                self.frame = frame
                self.last_frame_time = time.time()
                
            logger.info(f"Successfully initialized {self.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing {self.name}: {e}")
            return False
            
    def get_frame(self) -> Optional[np.ndarray]:
        """Get the latest frame"""
        if not self.cap or not self.cap.isOpened():
            if not self._init_camera():
                return None
                
        try:
            ret, frame = self.cap.read()
            if ret and frame is not None:
                with self.lock:
                    self.frame = frame
                    self.last_frame_time = time.time()
                return frame
            else:
                self._init_camera()
                return None
        except Exception as e:
            logger.error(f"Error capturing frame from {self.name}: {e}")
            self._init_camera()
            return None
            
    def stop(self):
        """Stop the camera"""
        self.running = False
        if self.cap:
            self.cap.release()
            self.cap = None

class ArducamMultiCamera:
    picam2 = None  # Shared Picamera2 instance
    gpio_pins = None  # Shared GPIO pins
    
    @classmethod
    def init_gpio(cls):
        """Initialize GPIO pins once for all instances"""
        if cls.gpio_pins is None:
            try:
                # Using BCM pin numbers (4=GPIO7, 17=GPIO11, 18=GPIO12)
                cls.gpio_pins = {
                    'gpio7': DigitalOutputDevice(4),
                    'gpio11': DigitalOutputDevice(17),
                    'gpio12': DigitalOutputDevice(18)
                }
                logger.info("GPIO pins initialized successfully")
            except Exception as e:
                logger.error(f"GPIO initialization failed: {e}")
                cls.gpio_pins = None
    
    def __init__(self, name: str, i2c_cmd: str, gpio_states: list):
        self.name = name
        self.i2c_cmd = i2c_cmd
        self.gpio_states = gpio_states
        self.frame = None
        self.last_frame_time = 0
        self.lock = threading.Lock()
        self.running = True
        
        # Initialize shared GPIO
        self.__class__.init_gpio()
        
    def _switch_camera(self) -> bool:
        """Switch to this camera using I2C and GPIO"""
        try:
            if not self.__class__.gpio_pins:
                logger.error(f"{self.name}: GPIO not initialized")
                return False
                
            # Execute I2C command
            logger.info(f"Switching to {self.name} using I2C command: {self.i2c_cmd}")
            os.system(self.i2c_cmd)
            
            # Set GPIO pins
            self.__class__.gpio_pins['gpio7'].value = self.gpio_states[0]
            self.__class__.gpio_pins['gpio11'].value = self.gpio_states[1]
            self.__class__.gpio_pins['gpio12'].value = self.gpio_states[2]
            
            # Wait for camera to stabilize
            time.sleep(0.02)  # 20ms delay from demo code
            return True
            
        except Exception as e:
            logger.error(f"Error switching to {self.name}: {e}")
            return False
            
    def start(self):
        """Start the camera"""
        logger.info(f"Starting {self.name}")
        self.running = True
        self._init_camera()
        
    def _init_camera(self) -> bool:
        """Initialize the camera"""
        try:
            # Initialize shared Picamera2 instance if needed
            if not self.__class__.picam2:
                self.__class__.picam2 = Picamera2()
                self.__class__.picam2.configure(
                    self.__class__.picam2.create_still_configuration(
                        main={"size": (1920, 1080), "format": "BGR888"},
                        buffer_count=2
                    )
                )
                self.__class__.picam2.start()
                time.sleep(2)  # Wait for camera to initialize
                
            # Switch to this camera
            if not self._switch_camera():
                return False
                
            # Test capture
            test_frame = self.__class__.picam2.capture_array()
            if test_frame is None:
                logger.error(f"Failed to capture test frame from {self.name}")
                return False
                
            with self.lock:
                self.frame = test_frame
                self.last_frame_time = time.time()
                
            logger.info(f"Successfully initialized {self.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing {self.name}: {e}")
            return False
            
    def get_frame(self) -> Optional[np.ndarray]:
        """Get the latest frame"""
        try:
            # Switch to this camera
            if not self._switch_camera():
                return None
                
            # Capture twice as in demo code (first frame might be from previous camera)
            self.__class__.picam2.capture_array()
            frame = self.__class__.picam2.capture_array()
            
            if frame is not None:
                with self.lock:
                    self.frame = frame
                    self.last_frame_time = time.time()
                return frame
            else:
                self._init_camera()
                return None
        except Exception as e:
            logger.error(f"Error capturing frame from {self.name}: {e}")
            self._init_camera()
            return None
            
    def stop(self):
        """Stop the camera"""
        self.running = False

class CameraManager:
    def __init__(self):
        self.cameras: Dict[str, Union[USBCamera, ArducamMultiCamera]] = {}
        self._init_cameras()
        
    def _init_cameras(self):
        """Initialize all cameras"""
        for rack_id, config in CAMERA_CONFIG.items():
            if config['type'] == 'usb':
                camera = USBCamera(config['device'], config['name'])
            else:  # arducam
                camera = ArducamMultiCamera(
                    config['name'],
                    config['i2c_cmd'],
                    config['gpio_sta']
                )
            camera.start()
            self.cameras[rack_id] = camera
            
    def get_frame(self, rack_id: str) -> Optional[np.ndarray]:
        """Get frame from specific camera"""
        camera = self.cameras.get(rack_id)
        if camera:
            frame = camera.get_frame()
            if frame is None:
                return self._generate_blank_frame(f"Reconnecting to {camera.name}...")
            return frame
        return self._generate_blank_frame("Camera not found")
        
    def _generate_blank_frame(self, message: str) -> np.ndarray:
        """Generate a blank frame with error message"""
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        frame.fill(32)  # Dark gray background
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1.5
        thickness = 2
        text_size = cv2.getTextSize(message, font, font_scale, thickness)[0]
        text_x = (frame.shape[1] - text_size[0]) // 2
        text_y = (frame.shape[0] + text_size[1]) // 2
        cv2.putText(frame, message, (text_x, text_y), font, font_scale, (0, 0, 0), thickness + 2)
        cv2.putText(frame, message, (text_x, text_y), font, font_scale, (255, 255, 255), thickness)
        return frame
        
    def get_generator(self, rack_id: str):
        """Generate MJPEG stream for a specific camera"""
        while True:
            try:
                frame = self.get_frame(rack_id)
                if frame is not None:
                    ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if ret:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
                time.sleep(0.033)  # ~30fps
            except Exception as e:
                logger.error(f"Error in frame generator for {rack_id}: {e}")
                blank = self._generate_blank_frame(f"Error: {str(e)}")
                ret, jpeg = cv2.imencode('.jpg', blank, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
                time.sleep(0.5)
        
    def get_available_cameras(self) -> list:
        """Get list of available cameras"""
        return list(self.cameras.keys())
        
    def stop(self):
        """Stop all cameras"""
        for camera in self.cameras.values():
            camera.stop()
        if ArducamMultiCamera.picam2:
            ArducamMultiCamera.picam2.close()
            ArducamMultiCamera.picam2 = None

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

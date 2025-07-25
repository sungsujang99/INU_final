import cv2
import numpy as np
import logging
import time
import threading
from picamera2 import Picamera2
import RPi.GPIO as gp
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
        'device': '/dev/video8',
        'name': 'Main Camera'
    },
    'A': {
        'type': 'arducam',
        'name': 'Rack A Camera',
        'i2c_cmd': 'i2cset -y 1 0x70 0x00 0x04',
        'gpio_sta': [False, False, True]
    },
    'B': {
        'type': 'arducam',
        'name': 'Rack B Camera',
        'i2c_cmd': 'i2cset -y 1 0x70 0x00 0x05',
        'gpio_sta': [True, False, True]
    },
    'C': {
        'type': 'arducam',
        'name': 'Rack C Camera',
        'i2c_cmd': 'i2cset -y 1 0x70 0x00 0x06',
        'gpio_sta': [False, True, False]
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
    picam2 = None
    
    def __init__(self, name: str, i2c_cmd: str, gpio_sta: list):
        self.name = name
        self.i2c_cmd = i2c_cmd
        self.gpio_sta = gpio_sta
        self.frame = None
        self.last_frame_time = 0
        self.lock = threading.Lock()
        self.running = True
        
        # Initialize GPIO exactly as in demo
        gp.setwarnings(False)
        gp.setmode(gp.BOARD)
        gp.setup(7, gp.OUT)
        gp.setup(11, gp.OUT)
        gp.setup(12, gp.OUT)
        
    def select_channel(self):
        gp.output(7, self.gpio_sta[0])
        gp.output(11, self.gpio_sta[1])
        gp.output(12, self.gpio_sta[2])
        
    def init_i2c(self):
        os.system(self.i2c_cmd)
        
    def start(self):
        logger.info(f"Starting {self.name}")
        self.running = True
        self._init_camera()
        
    def _init_camera(self):
        try:
            self.select_channel()
            self.init_i2c()
            time.sleep(0.5)
            
            if not self.__class__.picam2:
                self.__class__.picam2 = Picamera2()
                self.__class__.picam2.configure(
                    self.__class__.picam2.create_still_configuration(
                        main={"size": (640, 480), "format": "RGB888"},
                        buffer_count=2
                    )
                )
                self.__class__.picam2.start()
                time.sleep(2)
                
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
            
    def get_frame(self):
        try:
            self.select_channel()
            time.sleep(0.02)
            
            # Capture twice as in demo code
            self.__class__.picam2.capture_array()
            frame = self.__class__.picam2.capture_array()
            
            if frame is not None:
                with self.lock:
                    self.frame = frame
                    self.last_frame_time = time.time()
                return frame
            return None
        except Exception as e:
            logger.error(f"Error capturing frame from {self.name}: {e}")
            return None
            
    def stop(self):
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
        frame = np.zeros((480, 640, 3), dtype=np.uint8)  # Match test resolution
        frame.fill(32)
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        thickness = 2
        text_size = cv2.getTextSize(message, font, font_scale, thickness)[0]
        text_x = (frame.shape[1] - text_size[0]) // 2
        text_y = (frame.shape[0] + text_size[1]) // 2
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

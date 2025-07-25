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
        'device': '/dev/video8',
        'name': 'Main Camera'
    },
    'A': {
        'type': 'arducam',
        'name': 'Rack A Camera',
        'i2c_cmd': 'i2cset -y 1 0x70 0x00 0x04',
        'gpio_sta': [False, False, True]  # Original working config
    },
    'B': {
        'type': 'arducam',
        'name': 'Rack B Camera',
        'i2c_cmd': 'i2cset -y 1 0x70 0x00 0x05',
        'gpio_sta': [True, False, True]  # Original working config
    },
    'C': {
        'type': 'arducam',
        'name': 'Rack C Camera',
        'i2c_cmd': 'i2cset -y 1 0x70 0x00 0x06',  # Changed back to 0x06
        'gpio_sta': [False, True, False]  # Original working config
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
        self.frame_cache = None
        self.last_capture_time = 0
        self.CACHE_DURATION = 0.2  # Cache frames for 200ms
        self.MIN_FRAME_INTERVAL = 0.2  # Minimum time between frame captures (5 FPS)
        
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

    @classmethod
    def _reinit_camera(cls):
        """Reinitialize the camera with fresh state"""
        try:
            # Cleanup existing camera
            if cls.picam2:
                try:
                    cls.picam2.stop_preview()  # Stop preview first
                    cls.picam2.stop()
                    cls.picam2.close()
                except:
                    pass
                cls.picam2 = None
                time.sleep(1.0)  # Wait longer for camera to fully close
            
            # Initialize new camera instance
            cls.picam2 = Picamera2(0)
            
            # Create and apply configuration before starting
            config = cls.picam2.create_preview_configuration(
                main={"size": (640, 480), "format": "RGB888"},
                buffer_count=4  # Use more buffers for stability
            )
            cls.picam2.configure(config)
            
            # Wait for configuration to settle
            time.sleep(0.5)
            
            try:
                cls.picam2.start()
                # Wait for camera to fully start
                time.sleep(1.0)
                
                # Test capture to verify camera is working
                test_frame = cls.picam2.capture_array()
                if test_frame is None:
                    raise RuntimeError("Test capture failed")
                    
                logger.info("Camera system reinitialized successfully")
                return True
            except Exception as e:
                logger.error(f"Camera start failed: {e}")
                try:
                    cls.picam2.close()
                except:
                    pass
                cls.picam2 = None
                return False
                
        except Exception as e:
            logger.error(f"Camera reinitialization failed: {e}")
            if cls.picam2:
                try:
                    cls.picam2.close()
                except:
                    pass
                cls.picam2 = None
            return False

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
                time.sleep(0.5)  # Longer wait for pins to settle
                
                # Set new pin states
                lgpio.gpio_write(self.__class__.gpio_chip, 4, 1 if self.gpio_sta[0] else 0)    # Pin 7
                lgpio.gpio_write(self.__class__.gpio_chip, 17, 1 if self.gpio_sta[1] else 0)  # Pin 11
                lgpio.gpio_write(self.__class__.gpio_chip, 18, 1 if self.gpio_sta[2] else 0)  # Pin 12
                time.sleep(0.5)  # Longer wait for pins to settle
                logger.info(f"GPIO set: Pin 7={self.gpio_sta[0]}, Pin 11={self.gpio_sta[1]}, Pin 12={self.gpio_sta[2]}")
                
                # Execute I2C command after GPIO change
                self.init_i2c()
                time.sleep(0.5)  # Wait for I2C to settle
                
                # Reinitialize camera when switching
                retry_count = 3
                while retry_count > 0:
                    if self._reinit_camera():
                        break
                    retry_count -= 1
                    time.sleep(1.0)  # Wait between retries
                    
                if retry_count == 0:
                    raise RuntimeError("Failed to reinitialize camera after retries")
                
                # Update current camera
                self.__class__.current_camera = self
                
                # Clear frame cache after switch
                self.frame_cache = None
                self.last_capture_time = 0
                
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
        current_time = time.time()
        
        # Return cached frame if it's still fresh
        if (self.frame_cache is not None and 
            current_time - self.last_capture_time < self.CACHE_DURATION):
            return self.frame_cache.copy()
            
        # Rate limit frame captures
        if current_time - self.last_capture_time < self.MIN_FRAME_INTERVAL:
            if self.frame_cache is not None:
                return self.frame_cache.copy()
            return self._generate_blank_frame("Initializing camera...")
            
        try:
            with self.lock:  # Use lock to prevent concurrent camera access
                # Set GPIO pins for this camera
                self.select_channel()
                
                # Try to capture a frame
                if self.__class__.picam2:
                    array = self.__class__.picam2.capture_array()
                    if array is not None:
                        self.frame = array
                        self.last_frame_time = current_time
                        # Update cache
                        self.frame_cache = array.copy()
                        self.last_capture_time = current_time
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

import io, threading, time, logging, sys, os
import lgpio
from picamera2 import Picamera2
import libcamera
from flask import Response, current_app
import cv2
import numpy as np
import logging
import time
import threading
from picamera2 import Picamera2
import libcamera
import subprocess
from typing import Optional, Dict, List, Tuple

# Set Picamera2 logging to WARNING to suppress DEBUG output
logging.getLogger('picamera2').setLevel(logging.WARNING)

# Get a logger instance
logger = logging.getLogger(__name__)

def detect_cameras():
    """Detect available USB cameras and keep retrying until one is found"""
    logger.info("Detecting available cameras...")
    
    while True:  # Keep trying until we find a camera
        try:
            # Run v4l2-ctl to list devices
            result = subprocess.run(['v4l2-ctl', '--list-devices'], capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Failed to list video devices: {result.stderr}")
                time.sleep(1)
                continue
                
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
            
            if not usb_devices:
                logger.warning("No USB cameras found in v4l2-ctl output, retrying...")
                time.sleep(1)
                continue
            
            logger.info(f"Found USB video devices: {usb_devices}")
            
            # Try each detected USB device
            for device_id in usb_devices:
                device_path = f"/dev/video{device_id}"
                try:
                    logger.info(f"Testing camera at {device_path}...")
                    cap = cv2.VideoCapture(device_path)
                    
                    if not cap.isOpened():
                        logger.warning(f"Failed to open camera {device_path}, trying next...")
                        continue
                    
                    # Try to read a frame
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        logger.warning(f"Failed to read frame from camera {device_path}, trying next...")
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
            
            logger.warning("No working USB cameras found, retrying...")
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Error during camera detection: {e}")
            time.sleep(1)

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

def init_picamera(camera_id: int = 0) -> Optional[Picamera2]:
    """Initialize a Picamera2 instance with retries"""
    while True:  # Keep trying until we succeed
        try:
            # Check if camera exists using libcamera
            result = subprocess.run(['libcamera-hello', '--list-cameras'], capture_output=True, text=True)
            cameras = result.stdout.strip().split('\n')
            
            if not any(f'Camera {camera_id}' in cam for cam in cameras):
                logger.warning(f"CSI Camera {camera_id} not found in libcamera list, retrying...")
                time.sleep(1)
                continue
                
            picam = Picamera2(camera_id)
            
            # Get sensor information
            sensor_modes = picam.sensor_modes
            if not sensor_modes:
                logger.warning(f"No sensor modes available for camera {camera_id}, retrying...")
                time.sleep(1)
                continue
                
            logger.info(f"Available sensor modes for camera {camera_id}: {sensor_modes}")
            
            # Configure for optimal streaming
            config = picam.create_video_configuration(
                main={"size": (1920, 1080), "format": "RGB888"},
                controls={
                    "ExposureTime": 20000,
                    "AnalogueGain": 1.0,
                    "AeEnable": True,
                    "AwbEnable": True
                },
                buffer_count=4
            )
            
            picam.configure(config)
            
            # Try to start the camera
            picam.start()
            
            # Verify camera is working with a test capture
            test_frame = picam.capture_array()
            if test_frame is None or test_frame.size == 0:
                logger.warning("Test capture failed, retrying...")
                picam.stop()
                picam.close()
                time.sleep(1)
                continue
                
            logger.info(f"Successfully initialized CSI camera {camera_id}")
            return picam
            
        except Exception as e:
            logger.error(f"Failed to initialize CSI camera {camera_id}: {e}")
            time.sleep(1)

class MultiCamera:
    def __init__(self):
        self.picam = None
        self.usb_camera = None
        self.usb_device_id = None
        self.current_camera = None
        self.lock = threading.Lock()
        self.running = True
        self.update_thread = None
        self.last_frame = None
        self.last_frame_time = 0
        self.error_count = 0
        self.MAX_ERRORS = 3
        self.frame_timeout = 5.0  # Consider frame stale after 5 seconds
        
    def _init_cameras(self):
        """Initialize all available cameras"""
        logger.info("Initializing cameras...")
        
        # First try to initialize CSI camera
        self.picam = init_picamera()
        if self.picam:
            self.current_camera = 'csi'
            logger.info("Successfully initialized CSI camera")
        
        # Then initialize USB camera
        while True:  # Keep trying until we get a camera
            try:
                self.usb_device_id = detect_cameras()  # This uses our robust USB detection
                if self.usb_device_id is not None:
                    self.usb_camera = cv2.VideoCapture(f"/dev/video{self.usb_device_id}")
                    if not self.usb_camera.isOpened():
                        logger.warning("Failed to open USB camera, retrying...")
                        time.sleep(1)
                        continue
                    if not self.current_camera:
                        self.current_camera = 'usb'
                    logger.info("Successfully initialized USB camera")
                    break
            except Exception as e:
                logger.error(f"Failed to initialize USB camera: {e}")
                time.sleep(1)
            
        if not self.current_camera:
            raise RuntimeError("No cameras available!")
            
    def _attempt_camera_recovery(self):
        """Attempt to recover from camera failures"""
        logger.info("Attempting camera recovery")
        
        try:
            if self.current_camera == 'usb':
                # Try to reinitialize USB camera
                if self.usb_camera:
                    self.usb_camera.release()
                self.usb_device_id = detect_cameras()
                self.usb_camera = cv2.VideoCapture(f"/dev/video{self.usb_device_id}")
                if not self.usb_camera.isOpened():
                    raise RuntimeError("Failed to recover USB camera")
            else:
                # Try to recover CSI camera
                if self.picam:
                    self.picam.stop()
                    self.picam.close()
                time.sleep(2)  # Give hardware time to reset
                self.picam = init_picamera()
                if not self.picam:
                    raise RuntimeError("Failed to recover CSI camera")
                    
            logger.info("Camera recovery successful")
            self.error_count = 0
            
        except Exception as e:
            logger.error(f"Camera recovery failed: {e}")
            # If CSI camera recovery failed, try falling back to USB
            if self.current_camera == 'csi' and self.usb_camera:
                logger.info("Falling back to USB camera")
                self.current_camera = 'usb'
                
    def _update(self):
        """Update thread to continuously capture frames"""
        while self.running:
            try:
                frame = None
                if self.current_camera == 'usb':
                    if self.usb_camera and self.usb_camera.isOpened():
                        ret, frame = self.usb_camera.read()
                        if not ret or frame is None:
                            raise RuntimeError("Failed to read USB camera frame")
                else:
                    if self.picam:
                        frame = self.picam.capture_array()
                        if frame is None or frame.size == 0:
                            raise RuntimeError("Failed to capture CSI camera frame")
                        
                if frame is not None:
                    with self.lock:
                        self.last_frame = frame
                        self.last_frame_time = time.time()
                        self.error_count = 0
                else:
                    self.error_count += 1
                    if self.error_count >= self.MAX_ERRORS:
                        logger.warning(f"Too many errors ({self.error_count}), attempting recovery")
                        self._attempt_camera_recovery()
                        
            except Exception as e:
                logger.error(f"Error in camera update thread: {e}")
                self.error_count += 1
                if self.error_count >= self.MAX_ERRORS:
                    self._attempt_camera_recovery()
                
            time.sleep(0.033)  # ~30fps
            
    def start(self):
        """Start the camera system"""
        self._init_cameras()
        self.update_thread = threading.Thread(target=self._update)
        self.update_thread.daemon = True
        self.update_thread.start()
        
    def stop(self):
        """Stop all cameras safely"""
        self.running = False
        if self.update_thread:
            self.update_thread.join()
            
        if self.picam:
            try:
                self.picam.stop()
                self.picam.close()
            except Exception as e:
                logger.error(f"Error stopping CSI camera: {e}")
                
        if self.usb_camera:
            self.usb_camera.release()
            
    def switch_camera(self, camera_id: str) -> bool:
        """Switch to a different camera"""
        if camera_id not in ['csi', 'usb']:
            return False
            
        with self.lock:
            if camera_id == 'csi' and not self.picam:
                return False
            if camera_id == 'usb' and not self.usb_camera:
                return False
            self.current_camera = camera_id
            return True
            
    def get_frame(self) -> Optional[np.ndarray]:
        """Get the latest frame from the current camera"""
        with self.lock:
            if time.time() - self.last_frame_time > self.frame_timeout:
                return self._generate_blank_frame("Camera not responding...")
            return self.last_frame
            
    def _generate_blank_frame(self, message: str) -> np.ndarray:
        """Generate a blank frame with error message"""
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        cv2.putText(frame, message, (int(frame.shape[1]/4), int(frame.shape[0]/2)),
                   cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)
        return frame

    def get_generator(self):
        """Generate MJPEG stream from current camera"""
        while True:
            try:
                frame = self.get_frame()
                if frame is not None:
                    # Convert frame to JPEG
                    ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if ret:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
                time.sleep(0.033)  # ~30fps
            except Exception as e:
                logger.error(f"Error in frame generator: {e}")
                # Generate blank frame on error
                blank = self._generate_blank_frame("Camera error, reconnecting...")
                ret, jpeg = cv2.imencode('.jpg', blank, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
                time.sleep(0.5)  # Wait a bit longer on error

class CameraManager:
    def __init__(self):
        self.multi_camera = MultiCamera()
        self.multi_camera.start()

    def __del__(self):
        self.multi_camera.stop()

    def mjpeg_feed(self, camera_num=None):
        """Get MJPEG stream from camera"""
        if camera_num is not None:
            self.multi_camera.switch_camera('csi' if camera_num > 0 else 'usb')
        return Response(
            self.multi_camera.get_generator(),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )

    def get_available_cameras(self):
        """Get list of available camera indices"""
        cameras = []
        
        # USB camera is always index 0
        if self.multi_camera.usb_camera and self.multi_camera.usb_camera.isOpened():
            cameras.append(0)
            
        # CSI camera is index 1
        if self.multi_camera.picam:
            cameras.append(1)
            
        return cameras
    
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
            self.multi_camera.get_frame(), # Changed to get_frame
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )
    
    def stop_all_cameras(self):
        """Stop the camera system"""
        if self.multi_camera:
            self.multi_camera.stop()

# Initialize camera manager
camera_manager = CameraManager()

def mjpeg_feed(camera_num=None):
    """Get MJPEG feed for specified camera"""
    logger.info(f"MJPEG feed requested for camera {camera_num}")
    return camera_manager.mjpeg_feed(camera_num)

def get_available_cameras():
    """Get list of available cameras"""
    try:
        return camera_manager.get_available_cameras()
    except Exception as e:
        logger.error(f"Error getting available cameras: {e}")
        return []

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

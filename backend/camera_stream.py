import io, threading, time, logging, sys, os
import RPi.GPIO as gp
from picamera2 import Picamera2
from libcamera import controls
from flask import Response, current_app

# Set Picamera2 logging to WARNING to suppress DEBUG output
logging.getLogger('picamera2').setLevel(logging.WARNING)

# Get a logger instance
logger = logging.getLogger(__name__)

# Initialize GPIO for camera switching
gp.setwarnings(False)
gp.setmode(gp.BOARD)
gp.setup(7, gp.OUT)
gp.setup(11, gp.OUT)
gp.setup(12, gp.OUT)

# Camera switching configurations
CAMERA_CONFIGS = {
    0: {"i2c_cmd": "i2cset -y 1 0x70 0x00 0x04", "gpio": (False, False, True)},   # Camera A
    1: {"i2c_cmd": "i2cset -y 1 0x70 0x00 0x05", "gpio": (True, False, True)},   # Camera B  
    2: {"i2c_cmd": "i2cset -y 1 0x70 0x00 0x06", "gpio": (False, True, False)},  # Camera C
    3: {"i2c_cmd": "i2cset -y 1 0x70 0x00 0x07", "gpio": (True, True, False)}    # Camera D
}

def switch_camera(camera_num):
    """Switch to the specified camera using I2C and GPIO"""
    if camera_num not in CAMERA_CONFIGS:
        logger.error(f"Invalid camera number: {camera_num}")
        return False
        
    try:
        config = CAMERA_CONFIGS[camera_num]
        
        # Execute I2C command
        os.system(config["i2c_cmd"])
        
        # Set GPIO pins
        gpio_7, gpio_11, gpio_12 = config["gpio"]
        gp.output(7, gpio_7)
        gp.output(11, gpio_11)
        gp.output(12, gpio_12)
        
        # Small delay for camera switching
        time.sleep(0.5)
        
        logger.info(f"Switched to camera {camera_num}")
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
        self._update_counter = 0
        self.last_capture_time = 0
        self.capture_errors = 0
        self.camera_lock = threading.Lock()
        
        try:
            logger.info("Initializing multi-camera system...")
            
            # Initialize with camera 0
            switch_camera(0)
            
            # Initialize Picamera2 (using camera index 0 since we switch via hardware)
            self.picam = Picamera2(0)
            
            # Create configuration
            config = self.picam.create_preview_configuration(
                main={"size": (width, height), "format": "RGB888"},
                buffer_count=4,
                controls={
                    "FrameDurationLimits": (int(1/fps * 1000000), int(1/fps * 1000000)),
                    "NoiseReductionMode": controls.draft.NoiseReductionModeEnum.Fast
                }
            )
            
            self.picam.configure(config)
            self.picam.start()
            
            # Wait for camera to settle
            time.sleep(2)
            
            logger.info("Multi-camera system initialized successfully")
            
            # Start capture thread
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
                
                # Stop current camera
                if hasattr(self, 'picam'):
                    self.picam.stop()
                
                # Switch hardware to new camera
                if switch_camera(camera_num):
                    # Restart camera
                    self.picam.start()
                    time.sleep(1)  # Allow camera to settle
                    
                    self.current_camera = camera_num
                    self.capture_errors = 0  # Reset error counter
                    logger.info(f"Successfully switched to camera {camera_num}")
                    return True
                else:
                    # If switch failed, try to restore previous camera
                    switch_camera(self.current_camera)
                    self.picam.start()
                    logger.error(f"Failed to switch to camera {camera_num}, restored camera {self.current_camera}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error switching to camera {camera_num}: {e}")
                # Try to restore previous camera
                try:
                    switch_camera(self.current_camera)
                    self.picam.start()
                except:
                    pass
                return False

    def _update(self):
        """Capture frames continuously"""
        logger.info("Multi-camera capture thread started")
        frame_interval = 1.0 / self.fps if self.fps > 0 else 0.1
        
        while self.running:
            try:
                current_time = time.time()
                if current_time - self.last_capture_time < frame_interval:
                    time.sleep(0.001)
                    continue
                
                with self.camera_lock:
                    try:
                        arr = self.picam.capture_array()
                        if arr is not None:
                            # Save test frame for first capture of each camera
                            if self._update_counter == 0:
                                import cv2
                                cv2.imwrite(f"test_frame_multicam_{self.current_camera}.jpg", arr)
                            
                            # Encode to JPEG
                            import cv2
                            ret, jpg = cv2.imencode(".jpg", arr, [cv2.IMWRITE_JPEG_QUALITY, 80])
                            
                            if ret:
                                self.frame = jpg.tobytes()
                                self._update_counter += 1
                                self.capture_errors = 0
                                self.last_capture_time = time.time()
                            else:
                                self.capture_errors += 1
                        else:
                            self.capture_errors += 1
                            
                    except Exception as e:
                        self.capture_errors += 1
                        if self.capture_errors % 10 == 0:  # Log every 10 errors
                            logger.warning(f"Capture error on camera {self.current_camera}: {e}")
                
                # Reset camera if too many errors
                if self.capture_errors >= 10:
                    logger.warning(f"Too many capture errors on camera {self.current_camera}, attempting reset...")
                    try:
                        with self.camera_lock:
                            self.picam.stop()
                            time.sleep(1)
                            switch_camera(self.current_camera)
                            self.picam.start()
                            time.sleep(2)
                            self.capture_errors = 0
                    except Exception as e:
                        logger.error(f"Camera reset failed: {e}")
                        
            except Exception as e:
                logger.error(f"Error in capture loop: {e}")
                time.sleep(0.1)

    def get_generator(self, camera_num=None):
        """Get frame generator for specified camera"""
        if camera_num is not None and camera_num != self.current_camera:
            self.set_camera(camera_num)
            
        logger.info(f"Frame generator requested for camera {self.current_camera}")
        boundary = b'--frame'
        
        while True:
            try:
                if self.frame:
                    yield boundary + b'\r\n'
                    yield b'Content-Type: image/jpeg\r\n\r\n' + self.frame + b'\r\n'
                time.sleep(1.0 / self.fps)
            except Exception as e:
                logger.error(f"Error in frame generator: {e}")
                break

    def stop(self):
        """Stop the camera system"""
        self.running = False
        try:
            if hasattr(self, 'picam'):
                self.picam.stop()
                self.picam.close()
            # Reset GPIO to default state
            gp.output(7, False)
            gp.output(11, False)
            gp.output(12, True)
        except Exception as e:
            logger.error(f"Error stopping camera system: {e}")

class CameraManager:
    def __init__(self):
        self.multi_camera = None
        self.available_cameras = [0, 1, 2, 3]  # All 4 cameras should be available with the adapter
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
        gp.output(7, False)
        gp.output(11, False)
        gp.output(12, True)
        gp.cleanup()
    except:
        pass

import atexit
atexit.register(cleanup_gpio)

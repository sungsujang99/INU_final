import io, threading, time, cv2, logging, sys
from PIL import Image
from flask import Response, current_app

# Set Picamera2 logging to WARNING to suppress DEBUG output
logging.getLogger('picamera2').setLevel(logging.WARNING)

# Get a logger instance
logger = logging.getLogger(__name__)

class CameraStream:
    def __init__(self):
        self.active = False
        self.lock = threading.Lock()
        self.camera = None
        self.frame = None
        
    def start(self):
        """Start the camera stream"""
        try:
            if self.active:
                return
            
            # Initialize camera (try different indices if 0 doesn't work)
            self.camera = cv2.VideoCapture(0)
            if not self.camera.isOpened():
                raise RuntimeError("Could not start camera.")
            
            self.active = True
            # Start frame capture thread
            self.thread = threading.Thread(target=self._capture_loop)
            self.thread.daemon = True
            self.thread.start()
            logger.info("Camera stream started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start camera: {str(e)}")
            self.stop()
            raise

    def stop(self):
        """Stop the camera stream"""
        self.active = False
        if self.camera is not None:
            self.camera.release()
            self.camera = None
        logger.info("Camera stream stopped")

    def _capture_loop(self):
        """Continuous capture loop running in separate thread"""
        while self.active:
            try:
                ret, frame = self.camera.read()
                if not ret:
                    logger.warning("Failed to capture frame")
                    continue
                    
                with self.lock:
                    self.frame = frame
                    
                time.sleep(0.03)  # Limit to ~30 fps
                
            except Exception as e:
                logger.error(f"Error in capture loop: {str(e)}")
                break
                
        self.stop()

    def get_frame(self):
        """Get the latest frame as JPEG bytes"""
        try:
            with self.lock:
                if self.frame is None:
                    return None
                    
                # Encode frame as JPEG
                ret, jpeg = cv2.imencode('.jpg', self.frame)
                if not ret:
                    return None
                    
                return jpeg.tobytes()
                
        except Exception as e:
            logger.error(f"Error getting frame: {str(e)}")
            return None

    def generate_frames(self):
        """Generator function for streaming frames"""
        while True:
            try:
                frame = self.get_frame()
                if frame is not None:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                time.sleep(0.03)
                
            except Exception as e:
                logger.error(f"Error generating frames: {str(e)}")
                break

# Global camera instance
camera = CameraStream()

def get_camera_stream():
    """Get the camera stream response for Flask"""
    return Response(
        camera.generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

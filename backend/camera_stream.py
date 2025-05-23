import io, threading, time, cv2, logging, sys
from PIL import Image
from flask import Response, current_app

# Get a logger instance
logger = logging.getLogger(__name__)

class Camera:
    def __init__(self, width=320, height=240, fps=15):  # Reduced resolution
        try:
            print("[CAM_INIT_DEBUG] Entering Camera __init__ try block.", file=sys.stderr)
            logger.info("[CAM_INIT] Attempting to initialize Picamera2...")
            
            print("[CAM_INIT_DEBUG] About to import picamera2.", file=sys.stderr)
            from picamera2 import Picamera2
            from libcamera import controls  # Import libcamera controls
            print("[CAM_INIT_DEBUG] picamera2 imported successfully.", file=sys.stderr)

            print("[CAM_INIT_DEBUG] Initializing picamera2.Picamera2().", file=sys.stderr)
            self.picam = Picamera2()
            print("[CAM_INIT_DEBUG] picamera2.Picamera2() initialized.", file=sys.stderr)
            
            # Use preview configuration for continuous capture
            print("[CAM_INIT_DEBUG] Creating preview configuration.", file=sys.stderr)
            config = self.picam.create_preview_configuration(
                main={"size": (width, height), "format": "RGB888"},
                buffer_count=4,
                controls={
                    "FrameDurationLimits": (int(1/fps * 1000000), int(1/fps * 1000000)),
                    "NoiseReductionMode": controls.draft.NoiseReductionModeEnum.Fast
                }
            )

            print(f"[CAM_INIT_DEBUG] Preview configuration created: {config}", file=sys.stderr)
            logger.info(f"[CAM_INIT] Picamera2 raw configuration: {config}")
            
            print("[CAM_INIT_DEBUG] Configuring picam.", file=sys.stderr)
            self.picam.configure(config)
            print("[CAM_INIT_DEBUG] Picam configured.", file=sys.stderr)
            
            print("[CAM_INIT_DEBUG] Starting picam.", file=sys.stderr)
            self.picam.start()
            print("[CAM_INIT_DEBUG] Picam started.", file=sys.stderr)
            
            print("[CAM_INIT_DEBUG] Waiting 2 seconds for camera to settle after start...", file=sys.stderr)
            time.sleep(2) # Allow camera to settle
            print("[CAM_INIT_DEBUG] Finished 2-second settle time.", file=sys.stderr)
            
            logger.info("[CAM_INIT] Picamera2 started successfully.")
            self.frame = None
            self.running = True
            self._update_counter = 0
            self.fps = fps
            self.last_capture_time = 0
            self.capture_errors = 0  # Track consecutive capture errors
            print("[CAM_INIT_DEBUG] Starting _update thread.", file=sys.stderr)
            threading.Thread(target=self._update, daemon=True).start()
            logger.info("[CAM_INIT] Camera _update thread started.")
            print("[CAM_INIT_DEBUG] Camera __init__ completed successfully.", file=sys.stderr)
        except Exception as e:
            print(f"[CAM_INIT_DEBUG] Exception in Camera __init__: {e}", file=sys.stderr)
            logger.error(f"[CAM_INIT_ERROR] Error during Camera __init__: {e}", exc_info=True)
            raise

    def _update(self):
        print("[CAM_UPDATE_DEBUG] _update thread has started.", file=sys.stderr)
        logger.info("[CAM_UPDATE] Camera _update thread loop started.")
        frame_interval = 1.0 / self.fps if self.fps > 0 else 0.1
        
        while self.running:
            try:
                current_time = time.time()
                if current_time - self.last_capture_time < frame_interval:
                    time.sleep(0.001)  # Small sleep to prevent CPU spinning
                    continue
                
                print("[CAM_UPDATE_DEBUG] Attempting capture...", file=sys.stderr)
                start_capture = time.time()
                
                try:
                    # Capture directly from the camera stream
                    arr = self.picam.capture_array()
                    if arr is not None:
                        print(f"[CAM_UPDATE_DEBUG] Array captured. Shape: {arr.shape}, Type: {arr.dtype}", file=sys.stderr)
                        
                        # Convert RGB to BGR for OpenCV
                        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
                        ret, jpg = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
                        
                        if ret:
                            self.frame = jpg.tobytes()
                            self._update_counter += 1
                            capture_time = time.time() - start_capture
                            if self._update_counter % (self.fps * 2) == 0:
                                print(f"[CAM_UPDATE_DEBUG] Frame {self._update_counter} captured and encoded in {capture_time:.3f}s, size: {len(self.frame)} bytes", file=sys.stderr)
                            
                            self.capture_errors = 0  # Reset error counter on successful capture
                            self.last_capture_time = time.time()
                        else:
                            print("[CAM_UPDATE_DEBUG] Failed to encode frame", file=sys.stderr)
                            self.capture_errors += 1
                    else:
                        print("[CAM_UPDATE_DEBUG] Capture returned None frame", file=sys.stderr)
                        self.capture_errors += 1
                
                except Exception as e:
                    print(f"[CAM_UPDATE_DEBUG] Capture error: {e}", file=sys.stderr)
                    self.capture_errors += 1
                    
                if self.capture_errors >= 5:  # Reset camera after 5 consecutive errors
                    print("[CAM_UPDATE_DEBUG] Too many capture errors, attempting camera reset...", file=sys.stderr)
                    try:
                        self.picam.stop()
                        time.sleep(1)
                        self.picam.start()
                        time.sleep(2)
                        self.capture_errors = 0
                    except Exception as e:
                        print(f"[CAM_UPDATE_DEBUG] Camera reset failed: {e}", file=sys.stderr)
                
            except Exception as e:
                print(f"[CAM_UPDATE_DEBUG_ERROR] Exception in _update: {e}", file=sys.stderr)
                logger.error(f"[CAM_UPDATE_ERROR] Error in Camera _update loop: {e}", exc_info=True)
                time.sleep(0.1)  # Brief pause on error

    def get_generator(self):
        print("[CAM_GEN_DEBUG] get_generator called.", file=sys.stderr)
        logger.info("[CAM_GEN] Camera get_generator called by a client.")
        boundary = b'--frame'
        frames_yielded_count = 0
        
        while True:
            try:
                if self.frame:
                    yield boundary + b'\r\n'
                    yield b'Content-Type: image/jpeg\r\n\r\n' + self.frame + b'\r\n'
                    frames_yielded_count += 1
                    if frames_yielded_count % (self.fps * 2) == 0:
                        print(f"[CAM_GEN_DEBUG] Frame yielded (total {frames_yielded_count})", file=sys.stderr)
                time.sleep(1.0 / self.fps)  # Control frame rate
            except Exception as e:
                print(f"[CAM_GEN_DEBUG_ERROR] Exception in get_generator: {e}", file=sys.stderr)
                logger.error(f"[CAM_GEN_ERROR] Error in Camera get_generator loop: {e}", exc_info=True)
                break

camera_singleton = Camera() # Default FPS is 15
def mjpeg_feed():
    logger.info("[MJPEG_FEED] mjpeg_feed accessed.")
    return Response(
        camera_singleton.get_generator(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

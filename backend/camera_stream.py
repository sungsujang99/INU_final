import io, threading, time, cv2, logging, sys
from PIL import Image
from flask import Response, current_app

# Get a logger instance
logger = logging.getLogger(__name__)

class Camera:
    def __init__(self, width=640, height=480, fps=15):
        try:
            print("[CAM_INIT_DEBUG] Entering Camera __init__ try block.", file=sys.stderr)
            logger.info("[CAM_INIT] Attempting to initialize Picamera2...")
            
            print("[CAM_INIT_DEBUG] About to import picamera2.", file=sys.stderr)
            from picamera2 import Picamera2
            print("[CAM_INIT_DEBUG] picamera2 imported successfully.", file=sys.stderr)

            print("[CAM_INIT_DEBUG] Initializing picamera2.Picamera2().", file=sys.stderr)
            self.picam = Picamera2()
            print("[CAM_INIT_DEBUG] picamera2.Picamera2() initialized.", file=sys.stderr)
            
            # Use still configuration which has been proven to work
            print("[CAM_INIT_DEBUG] Creating still configuration.", file=sys.stderr)
            config = self.picam.create_still_configuration(
                main={"size": (width, height)},
                lores={"size": (320, 240)},
                display="lores"
            )

            print(f"[CAM_INIT_DEBUG] Still configuration created: {config}", file=sys.stderr)
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
        last_capture_time = 0
        
        while self.running:
            try:
                current_time = time.time()
                if current_time - last_capture_time < frame_interval:
                    time.sleep(0.001)  # Small sleep to prevent CPU spinning
                    continue
                    
                print("[CAM_UPDATE_DEBUG] Attempting picam.capture_array('main')...", file=sys.stderr)
                arr = self.picam.capture_array("main")
                last_capture_time = time.time()
                
                print(f"[CAM_UPDATE_DEBUG] Capture complete. Array shape: {arr.shape if arr is not None else 'None'}", file=sys.stderr)
                
                if arr is None:
                    print("[CAM_UPDATE_DEBUG_WARN] capture_array returned None. Skipping encode.", file=sys.stderr)
                    continue

                print("[CAM_UPDATE_DEBUG] Attempting cv2.imencode...", file=sys.stderr)
                ret, jpg = cv2.imencode(".jpg", arr, [cv2.IMWRITE_JPEG_QUALITY, 80])
                print(f"[CAM_UPDATE_DEBUG] cv2.imencode complete. Success: {ret}", file=sys.stderr)
                
                if ret:
                    self.frame = jpg.tobytes()
                    self._update_counter += 1
                    if self._update_counter % (self.fps * 2) == 0:
                        print(f"[CAM_UPDATE_DEBUG] Frame {self._update_counter} captured and encoded, size: {len(self.frame)} bytes", file=sys.stderr)
                else:
                    logger.warning("[CAM_UPDATE_WARN] cv2.imencode failed.")
                    print("[CAM_UPDATE_DEBUG_ERROR] cv2.imencode failed.", file=sys.stderr)
                    
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

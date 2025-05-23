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
            import picamera2                  # Bookworm용
            print("[CAM_INIT_DEBUG] picamera2 imported successfully.", file=sys.stderr)

            self.picam = picamera2.Picamera2()
            config = self.picam.create_video_configuration(
                main={"size": (width, height)},
                controls={"FrameRate": fps}
            )
            logger.info(f"[CAM_INIT] Picamera2 raw configuration: {config}")
            self.picam.configure(config)
            self.picam.start()
            logger.info("[CAM_INIT] Picamera2 started successfully.")
            self.frame = None
            self.running = True
            threading.Thread(target=self._update, daemon=True).start()
            logger.info("[CAM_INIT] Camera _update thread started.")
        except Exception as e:
            print(f"[CAM_INIT_DEBUG] Exception in Camera __init__: {e}", file=sys.stderr)
            logger.error(f"[CAM_INIT_ERROR] Error during Camera __init__: {e}", exc_info=True)
            raise # Re-raise the exception to make it visible

    def _update(self):
        logger.info("[CAM_UPDATE] Camera _update thread loop started.")
        while self.running:
            try:
                # logger.debug("Attempting to capture frame...")
                arr = self.picam.capture_array("main")
                # logger.debug(f"Frame captured, shape: {arr.shape if arr is not None else 'None'}")
                
                # BGR(OpenCV) → JPG
                ret, jpg = cv2.imencode(".jpg", arr, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ret:
                    self.frame = jpg.tobytes()
                    # logger.debug(f"Frame encoded to JPEG, size: {len(self.frame) if self.frame else 0} bytes")
                else:
                    logger.warning("[CAM_UPDATE_WARN] cv2.imencode failed.")
                    self.frame = None # Explicitly set to None if encoding fails
                
                time.sleep(1/30) # Reduced sleep time slightly for potentially faster updates
            except Exception as e:
                logger.error(f"[CAM_UPDATE_ERROR] Error in Camera _update loop: {e}", exc_info=True)
                # If an error occurs, stop the loop to prevent continuous error logging
                # Or add a short sleep to avoid tight loop errors
                time.sleep(1) 

    def get_generator(self):
        logger.info("[CAM_GEN] Camera get_generator called by a client.")
        boundary = b'--frame'
        frames_sent_count = 0
        while True:
            try:
                if self.frame:
                    # logger.debug(f"Yielding frame {frames_sent_count}...")
                    yield boundary + b'\r\n'
                    yield b'Content-Type: image/jpeg\r\n\r\n' + self.frame + b'\r\n'
                    frames_sent_count += 1
                else:
                    # logger.debug("No frame available to yield, sleeping.")
                    pass
                time.sleep(1 / 15)            # fps 와 동일
            except Exception as e:
                logger.error(f"[CAM_GEN_ERROR] Error in Camera get_generator loop: {e}", exc_info=True)
                # Optionally, break the loop or handle the error in a way that makes sense
                break # Stop sending frames if an error occurs

camera_singleton = Camera()
def mjpeg_feed():
    logger.info("[MJPEG_FEED] mjpeg_feed accessed.")
    return Response(
        camera_singleton.get_generator(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

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
            import picamera2
            print("[CAM_INIT_DEBUG] picamera2 imported successfully.", file=sys.stderr)

            print("[CAM_INIT_DEBUG] Initializing picamera2.Picamera2().", file=sys.stderr)
            self.picam = picamera2.Picamera2()
            print("[CAM_INIT_DEBUG] picamera2.Picamera2() initialized.", file=sys.stderr)
            
            # TEST: Use create_still_configuration to see if capture_array unblocks
            print("[CAM_INIT_DEBUG] Creating STILL configuration for test.", file=sys.stderr)
            # config = self.picam.create_video_configuration(
            #     main={"size": (width, height)},
            #     controls={"FrameRate": fps}
            # )
            config = self.picam.create_still_configuration()
            # To keep the size somewhat reasonable for this test, let's try to adjust the still config's main stream if possible
            # This might not be the standard way, but for a test:
            if 'main' not in config: config['main'] = {}
            config['main']['size'] = (width, height) # Try to force the size
            # config['main']['format'] = 'BGR888' # Match working format from test, though still config might override

            print(f"[CAM_INIT_DEBUG] Video configuration created (using still_config basis): {config}", file=sys.stderr)
            logger.info(f"[CAM_INIT] Picamera2 raw configuration (using still_config basis): {config}")
            
            print("[CAM_INIT_DEBUG] Configuring picam.", file=sys.stderr)
            self.picam.configure(config)
            print("[CAM_INIT_DEBUG] Picam configured.", file=sys.stderr)
            
            print("[CAM_INIT_DEBUG] Starting picam.", file=sys.stderr)
            self.picam.start()
            print("[CAM_INIT_DEBUG] Picam started.", file=sys.stderr)
            
            logger.info("[CAM_INIT] Picamera2 started successfully.")
            self.frame = None
            self.running = True
            self._update_counter = 0
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
        while self.running:
            try:
                print("[CAM_UPDATE_DEBUG] Attempting picam.capture_array...", file=sys.stderr)
                arr = self.picam.capture_array("main")
                print(f"[CAM_UPDATE_DEBUG] picam.capture_array done. arr is None: {arr is None}", file=sys.stderr)
                
                if arr is None:
                    print("[CAM_UPDATE_DEBUG_WARN] capture_array returned None. Skipping encode.", file=sys.stderr)
                    self.frame = None
                    time.sleep(0.1) # Brief pause if capture fails
                    continue

                print("[CAM_UPDATE_DEBUG] Attempting cv2.imencode...", file=sys.stderr)
                ret, jpg = cv2.imencode(".jpg", arr, [cv2.IMWRITE_JPEG_QUALITY, 80])
                print(f"[CAM_UPDATE_DEBUG] cv2.imencode done. ret: {ret}", file=sys.stderr)
                
                if ret:
                    self.frame = jpg.tobytes()
                    self._update_counter += 1
                    if self._update_counter % 30 == 0: # Print every 30 frames (approx every 2 secs at 15fps)
                        print(f"[CAM_UPDATE_DEBUG] Frame captured and encoded, size: {len(self.frame) if self.frame else 0} bytes", file=sys.stderr)
                else:
                    logger.warning("[CAM_UPDATE_WARN] cv2.imencode failed.")
                    print("[CAM_UPDATE_DEBUG] cv2.imencode failed.", file=sys.stderr) # also print this
                    self.frame = None
                time.sleep(1/30) # Keep this sleep
            except Exception as e:
                print(f"[CAM_UPDATE_DEBUG_ERROR] Exception in _update: {e}", file=sys.stderr)
                logger.error(f"[CAM_UPDATE_ERROR] Error in Camera _update loop: {e}", exc_info=True)
                # If picam methods are problematic, this could be a tight loop of errors.
                # Consider stopping self.running = False or a longer sleep.
                time.sleep(1)

    def get_generator(self):
        print("[CAM_GEN_DEBUG] get_generator called.", file=sys.stderr)
        logger.info("[CAM_GEN] Camera get_generator called by a client.")
        boundary = b'--frame'
        frames_yielded_count = 0 # Add counter for periodic print
        while True:
            try:
                if self.frame:
                    yield boundary + b'\r\n'
                    yield b'Content-Type: image/jpeg\r\n\r\n' + self.frame + b'\r\n'
                    frames_yielded_count += 1
                    if frames_yielded_count % 30 == 0: # Print every 30 frames
                        print(f"[CAM_GEN_DEBUG] Frame yielded (total {frames_yielded_count})", file=sys.stderr)
                else:
                    # Optional: print if no frame is available, but can be noisy
                    # print("[CAM_GEN_DEBUG] No frame available to yield, sleeping.", file=sys.stderr)
                    pass
                time.sleep(1 / 15) # Keep this sleep, matches configured FPS
            except Exception as e:
                print(f"[CAM_GEN_DEBUG_ERROR] Exception in get_generator: {e}", file=sys.stderr)
                logger.error(f"[CAM_GEN_ERROR] Error in Camera get_generator loop: {e}", exc_info=True)
                break

camera_singleton = Camera()
def mjpeg_feed():
    logger.info("[MJPEG_FEED] mjpeg_feed accessed.")
    return Response(
        camera_singleton.get_generator(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

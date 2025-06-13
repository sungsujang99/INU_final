import io, threading, time, logging, sys
from flask import Response, current_app

# Set Picamera2 logging to WARNING to suppress DEBUG output
logging.getLogger('picamera2').setLevel(logging.WARNING)

# Get a logger instance
logger = logging.getLogger(__name__)

class Camera:
    def __init__(self, width=320, height=240, fps=15):  # Reduced resolution
        try:
            print("[CAM_INIT_DEBUG] Entering Camera __init__ try block.", file=sys.stderr)
            logger.info("[CAM_INIT] Attempting to initialize Picamera2...")
            
            # Import picamera2 only when needed
            try:
                from picamera2 import Picamera2
                from libcamera import controls
            except ImportError as e:
                print(f"[CAM_INIT_DEBUG] Failed to import picamera2: {e}", file=sys.stderr)
                logger.error(f"[CAM_INIT_ERROR] picamera2 not available: {e}")
                raise Exception("Camera hardware not available")
            
            print("[CAM_INIT_DEBUG] About to import picamera2.", file=sys.stderr)
            print("[CAM_INIT_DEBUG] picamera2 imported successfully.", file=sys.stderr)

            print("[CAM_INIT_DEBUG] Initializing picamera2.Picamera2().", file=sys.stderr)
            
            # Check if cameras are available before initializing
            try:
                available_cameras = Picamera2.global_camera_info()
                if not available_cameras:
                    raise Exception("No cameras detected on the system")
                print(f"[CAM_INIT_DEBUG] Found {len(available_cameras)} camera(s)", file=sys.stderr)
            except Exception as e:
                print(f"[CAM_INIT_DEBUG] Camera detection failed: {e}", file=sys.stderr)
                raise Exception("No cameras available")
            
            self.picam = Picamera2()
            print("[CAM_INIT_DEBUG] picamera2.Picamera2() initialized.", file=sys.stderr)
            
            # Use preview configuration for continuous capture, with RGB888 format
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
            self.camera_available = True
            
            print("[CAM_INIT_DEBUG] Starting _update thread.", file=sys.stderr)
            threading.Thread(target=self._update, daemon=True).start()
            logger.info("[CAM_INIT] Camera _update thread started.")
            print("[CAM_INIT_DEBUG] Camera __init__ completed successfully.", file=sys.stderr)
            
        except Exception as e:
            print(f"[CAM_INIT_DEBUG] Exception in Camera __init__: {e}", file=sys.stderr)
            logger.error(f"[CAM_INIT_ERROR] Error during Camera __init__: {e}", exc_info=True)
            # Instead of raising, mark camera as unavailable
            self.camera_available = False
            self.frame = None
            self.running = False
            logger.warning("[CAM_INIT] Camera initialization failed, running without camera support")

    def _update(self):
        if not self.camera_available:
            return
            
        # print("[CAM_UPDATE_DEBUG] _update thread has started.", file=sys.stderr)
        logger.info("[CAM_UPDATE] Camera _update thread loop started.")
        frame_interval = 1.0 / self.fps if self.fps > 0 else 0.1
        
        while self.running:
            try:
                current_time = time.time()
                if current_time - self.last_capture_time < frame_interval:
                    time.sleep(0.001)  # Small sleep to prevent CPU spinning
                    continue
                    
                # print("[CAM_UPDATE_DEBUG] About to call capture_array()...", file=sys.stderr)
                start_capture = time.time()
                
                try:
                    # Import cv2 only when needed
                    import cv2
                    
                    # print("[CAM_UPDATE_DEBUG] Calling self.picam.capture_array()", file=sys.stderr)
                    arr = self.picam.capture_array()
                    # print(f"[CAM_UPDATE_DEBUG] capture_array() returned. Type: {type(arr)}, Value: {repr(arr)[:200]}", file=sys.stderr)
                    if arr is not None:
                        # Save a test frame to disk for inspection (only once)
                        if self._update_counter == 0:
                            cv2.imwrite("test_frame.jpg", arr)
                        # Directly encode RGB888 to JPEG
                        ret, jpg = cv2.imencode(".jpg", arr, [cv2.IMWRITE_JPEG_QUALITY, 80])
                        
                        if ret:
                            self.frame = jpg.tobytes()
                            self._update_counter += 1
                            capture_time = time.time() - start_capture
                            # if self._update_counter % (self.fps * 2) == 0:
                            #     print(f"[CAM_UPDATE_DEBUG] Frame {self._update_counter} captured and encoded in {capture_time:.3f}s, size: {len(self.frame)} bytes", file=sys.stderr)
                            
                            self.capture_errors = 0  # Reset error counter on successful capture
                            self.last_capture_time = time.time()
                        else:
                            # print("[CAM_UPDATE_DEBUG] Failed to encode frame", file=sys.stderr)
                            self.capture_errors += 1
                    else:
                        # print("[CAM_UPDATE_DEBUG] Capture returned None frame", file=sys.stderr)
                        self.capture_errors += 1
                
                except Exception as e:
                    # print(f"[CAM_UPDATE_DEBUG] Capture error: {e}", file=sys.stderr)
                    self.capture_errors += 1
                    
                if self.capture_errors >= 5:  # Reset camera after 5 consecutive errors
                    # print("[CAM_UPDATE_DEBUG] Too many capture errors, attempting camera reset...", file=sys.stderr)
                    try:
                        self.picam.stop()
                        time.sleep(1)
                        self.picam.start()
                        time.sleep(2)
                        self.capture_errors = 0
                    except Exception as e:
                        # print(f"[CAM_UPDATE_DEBUG] Camera reset failed: {e}", file=sys.stderr)
                        pass
                
            except Exception as e:
                print(f"[CAM_UPDATE_DEBUG_ERROR] Exception in _update: {e}", file=sys.stderr)
                logger.error(f"[CAM_UPDATE_ERROR] Error in Camera _update loop: {e}", exc_info=True)
                time.sleep(0.1)  # Brief pause on error

    def get_generator(self):
        if not self.camera_available:
            # Return a placeholder image or error message
            placeholder_frame = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x11\x08\x00\xf0\x01@\x03\x01"\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00\xaa\xff\xd9'
            
            boundary = b'--frame'
            while True:
                yield boundary + b'\r\n'
                yield b'Content-Type: image/jpeg\r\n\r\n' + placeholder_frame + b'\r\n'
                time.sleep(1.0)  # Slow refresh for placeholder
        
        # print("[CAM_GEN_DEBUG] get_generator called.", file=sys.stderr)
        logger.info("[CAM_GEN] Camera get_generator called by a client.")
        boundary = b'--frame'
        frames_yielded_count = 0
        
        while True:
            try:
                if self.frame:
                    # print(f"[CAM_GEN_DEBUG] Yielding frame {frames_yielded_count+1}", file=sys.stderr)
                    yield boundary + b'\r\n'
                    yield b'Content-Type: image/jpeg\r\n\r\n' + self.frame + b'\r\n'
                    frames_yielded_count += 1
                    # if frames_yielded_count % (self.fps * 2) == 0:
                    #     print(f"[CAM_GEN_DEBUG] Frame yielded (total {frames_yielded_count})", file=sys.stderr)
                else:
                    # print("[CAM_GEN_DEBUG] Waiting for frame (self.frame is None)", file=sys.stderr)
                    pass
                time.sleep(1.0 / self.fps)  # Control frame rate
            except Exception as e:
                print(f"[CAM_GEN_DEBUG_ERROR] Exception in get_generator: {e}", file=sys.stderr)
                logger.error(f"[CAM_GEN_ERROR] Error in Camera get_generator loop: {e}", exc_info=True)
                break

# Initialize camera singleton, but don't fail if camera is not available
camera_singleton = None

def get_camera():
    global camera_singleton
    if camera_singleton is None:
        try:
            camera_singleton = Camera()  # Default FPS is 15
        except Exception as e:
            logger.error(f"Failed to initialize camera: {e}")
            # Create a dummy camera object
            camera_singleton = Camera.__new__(Camera)
            camera_singleton.camera_available = False
            camera_singleton.frame = None
            camera_singleton.running = False
    return camera_singleton

def mjpeg_feed():
    logger.info("[MJPEG_FEED] mjpeg_feed accessed.")
    camera = get_camera()
    return Response(
        camera.get_generator(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

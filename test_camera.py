import time
import sys # For printing to stderr
from picamera2 import Picamera2 # Preview is not strictly needed for array capture

print("Attempting to initialize Picamera2...")
picam2 = None # Initialize to None for finally block
try:
    picam2 = Picamera2()
    print("Picamera2 initialized.")

    width, height = 640, 480
    print(f"Attempting to use create_still_configuration() with main size {width}x{height}.")
    
    # Use a still configuration but try to set the main stream size
    config = picam2.create_still_configuration()
    if 'main' not in config: config['main'] = {}
    config['main']['size'] = (width, height)
    # Optionally, set a format if needed, e.g., BGR888 which worked before
    # config['main']['format'] = 'BGR888' 
    
    print(f"Configuration to be applied: {config}")
    picam2.configure(config)
    print("Picamera2 configured.")

    print("Starting camera...")
    picam2.start()
    print("Camera started. Waiting 2 seconds for sensor to settle...")
    time.sleep(2)

    num_frames_to_capture = 10
    print(f"Attempting to capture {num_frames_to_capture} frames in a loop...")

    for i in range(num_frames_to_capture):
        print(f"Loop {i+1}/{num_frames_to_capture}: Attempting capture_array('main')...", file=sys.stderr)
        try:
            start_capture_time = time.monotonic()
            array = picam2.capture_array("main")
            end_capture_time = time.monotonic()
            capture_duration = end_capture_time - start_capture_time
            
            if array is not None:
                print(f"Loop {i+1}: capture_array() successful. Shape: {array.shape}, dtype: {array.dtype}. Capture time: {capture_duration:.4f}s", file=sys.stderr)
            else:
                print(f"Loop {i+1}: capture_array() returned None.", file=sys.stderr)
        except Exception as e_capture:
            print(f"Loop {i+1}: Exception during capture_array(): {e_capture}", file=sys.stderr)
            break # Stop if one capture fails
        
        time.sleep(0.1) # Small delay between captures

except Exception as e:
    print(f"An error occurred in the main script: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
finally:
    if picam2 is not None:
        if picam2.started:
            print("Stopping camera...", file=sys.stderr)
            picam2.stop()
            print("Camera stopped.", file=sys.stderr)
        print("Closing Picamera2 object...", file=sys.stderr)
        picam2.close()
        print("Picamera2 object closed.", file=sys.stderr)
print("Test script finished.") 
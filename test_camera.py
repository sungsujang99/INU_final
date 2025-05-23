import time
from picamera2 import Picamera2, Preview

print("Attempting to initialize Picamera2...")
try:
    picam2 = Picamera2()
    print("Picamera2 initialized.")

    # Basic configuration
    # config = picam2.create_preview_configuration() # For preview
    config = picam2.create_still_configuration() # For still image
    print(f"Configuration created: {config}")
    picam2.configure(config)
    print("Picamera2 configured.")

    # If you have a display connected and want to see a preview (optional):
    # print("Starting preview (qtgl)...")
    # picam2.start_preview(Preview.QTGL) 
    # print("Preview started. Sleeping for 5 seconds...")
    # time.sleep(5) # Preview for 5 seconds
    # picam2.stop_preview()
    # print("Preview stopped.")

    print("Starting camera...")
    picam2.start()
    print("Camera started. Waiting 2 seconds for sensor to settle...")
    time.sleep(2)  # Give sensor time to settle

    image_path = "test_image.jpg"
    print(f"Attempting to capture image to {image_path}...")
    # metadata = picam2.capture_file(image_path)
    
    # Let's try capture_array first as it's used in the app
    try:
        print("Attempting capture_array()...")
        array = picam2.capture_array()
        print(f"capture_array() successful. Array shape: {array.shape}, dtype: {array.dtype}")
        
        # If capture_array works, try to save it using OpenCV (optional, but good test)
        try:
            import cv2
            print("Attempting to save array with cv2.imwrite...")
            # Picamera2 by default gives RGB, OpenCV imwrite expects BGR
            # Convert RGB to BGR
            # bgr_array = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
            # cv2.imwrite("test_image_from_array_cv2.jpg", bgr_array)

            # Or, more directly, if main format is XBGR8888 (which is BGRA essentially)
            # and if imencode in your app uses this directly, let's simulate that
            # For XBGR8888, it's BGRA, so we might need to slice off Alpha or ensure cv2 handles it.
            # Let's assume it's BGR for a simple test with imwrite if XBGR8888 is used.
            # If your stream format is XBGR8888, capture_array() on that stream should give BGRA.
            # OpenCV's imwrite expects BGR.
            # Let's try to save the raw array with picam2's method first which is simpler.
            print(f"Attempting to save array with picam2.helpers.save()...")
            from picamera2.helpers import save
            # Create a dummy request object for capture_array
            request = picam2.capture_request()
            save(request, {"main": array}, image_path) # Save the 'main' stream's array
            request.release() # Release the request
            print(f"Image saved from array to {image_path} using picamera2.helpers.save")

        except Exception as e_cv2:
            print(f"Error saving array with OpenCV or picamera2.helpers.save: {e_cv2}")

    except Exception as e_capture:
        print(f"Error during capture_array: {e_capture}")

    print("Stopping camera...")
    picam2.stop()
    print("Camera stopped.")

except Exception as e:
    print(f"An error occurred: {e}")

print("Test script finished.") 
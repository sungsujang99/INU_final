#!/usr/bin/env python3
"""
Test script to check available cameras with multi-camera adapter
"""

import sys
import time
import os
import RPi.GPIO as gp
from picamera2 import Picamera2

# Initialize GPIO for camera switching
gp.setwarnings(False)
gp.setmode(gp.BOARD)
gp.setup(7, gp.OUT)
gp.setup(11, gp.OUT)
gp.setup(12, gp.OUT)

# Camera switching configurations (same as in camera_stream.py)
CAMERA_CONFIGS = {
    0: {"i2c_cmd": "i2cset -y 1 0x70 0x00 0x04", "gpio": (False, False, True), "name": "Camera A"},
    1: {"i2c_cmd": "i2cset -y 1 0x70 0x00 0x05", "gpio": (True, False, True), "name": "Camera B"},
    2: {"i2c_cmd": "i2cset -y 1 0x70 0x00 0x06", "gpio": (False, True, False), "name": "Camera C"},
    3: {"i2c_cmd": "i2cset -y 1 0x70 0x00 0x07", "gpio": (True, True, False), "name": "Camera D"}
}

def switch_camera(camera_num):
    """Switch to the specified camera using I2C and GPIO"""
    if camera_num not in CAMERA_CONFIGS:
        print(f"Invalid camera number: {camera_num}")
        return False
        
    try:
        config = CAMERA_CONFIGS[camera_num]
        
        print(f"Switching to {config['name']} (Camera {camera_num})...")
        
        # Execute I2C command
        os.system(config["i2c_cmd"])
        
        # Set GPIO pins
        gpio_7, gpio_11, gpio_12 = config["gpio"]
        gp.output(7, gpio_7)
        gp.output(11, gpio_11)
        gp.output(12, gpio_12)
        
        # Delay for camera switching
        time.sleep(1)
        
        print(f"GPIO set: Pin 7={gpio_7}, Pin 11={gpio_11}, Pin 12={gpio_12}")
        return True
        
    except Exception as e:
        print(f"Error switching to camera {camera_num}: {e}")
        return False

def test_camera_capture(camera_num):
    """Test capturing with libcamera-still (like the demo)"""
    try:
        print(f"Testing capture with libcamera-still...")
        cmd = f"libcamera-still -o test_capture_{camera_num}.jpg --timeout 2000"
        result = os.system(cmd)
        
        if result == 0:
            print(f"✓ libcamera-still capture successful")
            return True
        else:
            print(f"✗ libcamera-still capture failed (exit code: {result})")
            return False
            
    except Exception as e:
        print(f"✗ libcamera-still capture error: {e}")
        return False

def test_picamera2_capture(camera_num):
    """Test capturing with Picamera2"""
    try:
        print(f"Testing capture with Picamera2...")
        
        # Initialize Picamera2 (always use index 0 since we switch via hardware)
        picam = Picamera2(0)
        
        # Create simple configuration
        config = picam.create_preview_configuration(
            main={"size": (320, 240), "format": "RGB888"}
        )
        
        picam.configure(config)
        picam.start()
        
        # Wait for camera to settle
        time.sleep(2)
        
        # Capture frame
        array = picam.capture_array()
        
        if array is not None:
            print(f"✓ Picamera2 capture successful (shape: {array.shape})")
            
            # Save test image
            import cv2
            cv2.imwrite(f"test_picamera2_{camera_num}.jpg", array)
            print(f"  Test image saved as test_picamera2_{camera_num}.jpg")
            
            picam.stop()
            picam.close()
            return True
        else:
            print(f"✗ Picamera2 capture failed - no data")
            picam.stop()
            picam.close()
            return False
            
    except Exception as e:
        print(f"✗ Picamera2 capture error: {e}")
        try:
            picam.stop()
            picam.close()
        except:
            pass
        return False

def test_cameras():
    """Test all available cameras with the multi-camera adapter"""
    print("=== Multi-Camera Adapter Test ===")
    print("Testing camera availability with GPIO/I2C switching...")
    
    working_cameras = []
    
    for camera_num in range(4):
        config = CAMERA_CONFIGS[camera_num]
        print(f"\n--- Testing {config['name']} (Camera {camera_num}) ---")
        
        # Switch to this camera
        if not switch_camera(camera_num):
            print(f"✗ Failed to switch to camera {camera_num}")
            continue
        
        # Test with libcamera-still first (simpler)
        libcamera_works = test_camera_capture(camera_num)
        
        # Test with Picamera2 (what our app uses)
        picamera2_works = test_picamera2_capture(camera_num)
        
        if libcamera_works or picamera2_works:
            working_cameras.append(camera_num)
            status = "✓ WORKING"
            if libcamera_works and picamera2_works:
                method = "(both libcamera-still and Picamera2)"
            elif libcamera_works:
                method = "(libcamera-still only)"
            else:
                method = "(Picamera2 only)"
        else:
            status = "✗ NOT WORKING"
            method = ""
        
        print(f"Camera {camera_num} ({config['name']}): {status} {method}")
    
    # Reset to default camera (Camera A)
    print(f"\nResetting to default camera (Camera A)...")
    switch_camera(0)
    
    print(f"\n=== Summary ===")
    print(f"Working cameras: {working_cameras}")
    print(f"Total working cameras: {len(working_cameras)} out of 4")
    
    if len(working_cameras) > 0:
        print(f"\n✓ Success! Multi-camera adapter is working.")
        print(f"Available cameras for the web interface: {working_cameras}")
    else:
        print(f"\n✗ No working cameras found!")
        print(f"Check connections and ensure i2c-tools is installed:")
        print(f"  sudo apt install i2c-tools")
        print(f"  sudo i2cdetect -y 1")
    
    return working_cameras

def cleanup():
    """Cleanup GPIO"""
    try:
        print("\nCleaning up GPIO...")
        gp.output(7, False)
        gp.output(11, False)
        gp.output(12, True)
        gp.cleanup()
    except:
        pass

if __name__ == "__main__":
    try:
        cameras = test_cameras()
        cleanup()
        
        if cameras:
            print(f"\nReady for production! Found {len(cameras)} working cameras.")
            sys.exit(0)
        else:
            print(f"\nSetup incomplete - no working cameras found.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print(f"\nTest interrupted by user.")
        cleanup()
        sys.exit(1)
    except Exception as e:
        print(f"Error during camera testing: {e}")
        cleanup()
        sys.exit(1) 
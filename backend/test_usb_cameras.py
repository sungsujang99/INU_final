#!/usr/bin/env python3
"""
Test script to detect and check USB cameras
"""

import cv2
import subprocess
import time
import json
import sys

def get_v4l2_devices():
    """Get list of Video4Linux2 devices"""
    try:
        # Run v4l2-ctl --list-devices
        result = subprocess.run(["v4l2-ctl", "--list-devices"], 
                              capture_output=True, 
                              text=True)
        
        if result.returncode == 0:
            print("\n=== V4L2 Devices ===")
            print(result.stdout)
            return True
    except FileNotFoundError:
        print("v4l2-ctl not found. Installing v4l-utils might help:")
        print("sudo apt install v4l-utils")
    except Exception as e:
        print(f"Error getting V4L2 devices: {e}")
    
    return False

def get_device_capabilities(device_path):
    """Get capabilities of a V4L2 device"""
    try:
        # Run v4l2-ctl --device=<dev> --all
        result = subprocess.run(["v4l2-ctl", "--device", device_path, "--all"],
                              capture_output=True,
                              text=True)
        
        if result.returncode == 0:
            print(f"\n=== Capabilities for {device_path} ===")
            print(result.stdout)
            return True
    except Exception as e:
        print(f"Error getting device capabilities: {e}")
    
    return False

def test_camera_capture(device_id):
    """Test capturing frames from a camera"""
    print(f"\nTesting camera device {device_id}...")
    
    try:
        # Open camera
        cap = cv2.VideoCapture(device_id)
        
        if not cap.isOpened():
            print(f"Failed to open camera {device_id}")
            return False
        
        # Get camera properties
        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        print(f"Camera opened successfully:")
        print(f"- Resolution: {width}x{height}")
        print(f"- FPS: {fps}")
        
        # Try to capture a frame
        print("Attempting to capture a frame...")
        ret, frame = cap.read()
        
        if ret:
            print("✓ Frame captured successfully")
            print(f"- Frame size: {frame.shape}")
            
            # Save test image
            filename = f"test_camera_{device_id}.jpg"
            cv2.imwrite(filename, frame)
            print(f"- Test image saved as {filename}")
            
            cap.release()
            return True
        else:
            print("✗ Failed to capture frame")
            cap.release()
            return False
            
    except Exception as e:
        print(f"Error testing camera: {e}")
        try:
            cap.release()
        except:
            pass
        return False

def main():
    print("=== USB Camera Detection and Test ===\n")
    
    # First, list all V4L2 devices
    v4l2_available = get_v4l2_devices()
    
    if not v4l2_available:
        print("\nProceeding with OpenCV device detection...")
    
    # Test cameras using OpenCV
    print("\nScanning for available cameras...")
    available_cameras = []
    
    # Try more device numbers, including the USB webcam devices
    for i in [0, 1, 2, 3, 4, 8, 9]:  # Added 8 and 9 for USB webcam
        try:
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available_cameras.append(i)
            cap.release()
        except Exception as e:
            print(f"Error trying device {i}: {e}")
    
    if not available_cameras:
        print("No cameras found!")
        return False
    
    print(f"\nFound {len(available_cameras)} camera(s): {available_cameras}")
    
    # Test each available camera
    working_cameras = []
    for device_id in available_cameras:
        if test_camera_capture(device_id):
            working_cameras.append(device_id)
            
        # If v4l2-ctl is available, get device capabilities
        if v4l2_available:
            get_device_capabilities(f"/dev/video{device_id}")
    
    print("\n=== Summary ===")
    print(f"Total cameras found: {len(available_cameras)}")
    print(f"Working cameras: {working_cameras}")
    
    if working_cameras:
        print("\n✓ USB camera detection complete!")
        print("You can use these device IDs in the camera configuration.")
        return True
    else:
        print("\n✗ No working cameras found.")
        print("Please check your camera connections and permissions.")
        print("\nTroubleshooting steps:")
        print("1. Check USB camera is properly connected")
        print("2. Try running with sudo to rule out permission issues:")
        print("   sudo ./test_usb_cameras.py")
        print("3. Check if the camera works with other tools:")
        print("   sudo apt install cheese")
        print("   cheese")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error during testing: {e}")
        sys.exit(1) 
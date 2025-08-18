#!/usr/bin/env python3
import cv2
import sys

def test_camera(device_path):
    """Test if a camera device can be opened and capture frames"""
    print(f"Testing {device_path}...")
    try:
        cap = cv2.VideoCapture(device_path)
        if not cap.isOpened():
            print(f"  ✗ Failed to open {device_path}")
            return False
        
        # Try to capture a frame
        ret, frame = cap.read()
        if not ret or frame is None:
            print(f"  ✗ Failed to capture frame from {device_path}")
            cap.release()
            return False
        
        # Get camera properties
        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        print(f"  ✓ {device_path} works! Resolution: {int(width)}x{int(height)}, FPS: {fps}")
        cap.release()
        return True
        
    except Exception as e:
        print(f"  ✗ Error testing {device_path}: {e}")
        return False

def main():
    print("Testing USB cameras...")
    working_devices = []
    
    # Test video devices 0-10
    for i in range(11):
        device_path = f"/dev/video{i}"
        if test_camera(device_path):
            working_devices.append(device_path)
    
    print(f"\nSummary:")
    print(f"Working devices: {working_devices}")
    print(f"Total working cameras: {len(working_devices)}")
    
    if len(working_devices) >= 4:
        print(f"\nSuggested camera configuration:")
        print(f"Main Camera (M): {working_devices[0]}")
        print(f"Rack A Camera: {working_devices[1]}")
        print(f"Rack B Camera: {working_devices[2]}")
        print(f"Rack C Camera: {working_devices[3]}")

if __name__ == "__main__":
    main() 
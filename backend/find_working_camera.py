#!/usr/bin/env python3
import cv2
import time
import subprocess

def test_camera(device_id, device_path):
    """Test if a camera works by trying to read frames"""
    print(f"\nTesting {device_path} (index {device_id})...")
    
    cap = cv2.VideoCapture(device_path)
    if not cap.isOpened():
        print(f"❌ Could not open {device_path}")
        cap.release()
        return False
        
    # Try to get camera properties
    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    print(f"Resolution: {width}x{height}")
    print(f"FPS: {fps}")
    
    # Try to read 5 frames
    frames_read = 0
    start_time = time.time()
    
    for _ in range(5):
        ret, frame = cap.read()
        if ret and frame is not None:
            frames_read += 1
            print(f"Frame {frames_read}: {frame.shape}")
        time.sleep(0.1)
    
    cap.release()
    
    if frames_read > 0:
        print(f"✅ Successfully read {frames_read} frames from {device_path}")
        return True
    else:
        print(f"❌ Could not read any frames from {device_path}")
        return False

def main():
    print("=== USB Camera Detection ===")
    
    # First, list all video devices
    try:
        result = subprocess.run(["v4l2-ctl", "--list-devices"], 
                              capture_output=True, 
                              text=True)
        if result.returncode == 0:
            print("\nFound video devices:")
            print(result.stdout)
    except:
        print("Could not run v4l2-ctl")
    
    # Test each potential video device
    working_devices = []
    
    # Try both direct index and device path
    for i in range(12):  # Try first 12 possible devices
        # Try by index
        if test_camera(i, i):
            working_devices.append(f"index:{i}")
            
        # Try by device path
        device_path = f"/dev/video{i}"
        if test_camera(i, device_path):
            working_devices.append(device_path)
    
    print("\n=== Results ===")
    if working_devices:
        print("Working camera devices:")
        for device in working_devices:
            print(f"- {device}")
    else:
        print("No working camera devices found!")
        
    print("\nRecommended configuration:")
    if working_devices:
        # Prefer device path over index
        device = next((d for d in working_devices if d.startswith("/dev")), working_devices[0])
        if device.startswith("/dev"):
            device_num = int(device.replace("/dev/video", ""))
        else:
            device_num = int(device.replace("index:", ""))
            
        print(f"""
In camera_stream.py, use:
CAMERA_CONFIGS = {{
    0: {{"type": "usb", "device": {device_num}, "name": "USB Camera"}},
    ...
}}""")
    
if __name__ == "__main__":
    main() 
import cv2
import time

def test_camera(device_id):
    print(f"\nTesting camera at /dev/video{device_id}...")
    cap = cv2.VideoCapture(device_id)
    
    if not cap.isOpened():
        print(f"Failed to open camera {device_id}")
        return False
    
    # Try to read a frame
    ret, frame = cap.read()
    if not ret:
        print(f"Failed to read frame from camera {device_id}")
        cap.release()
        return False
    
    # Get camera properties
    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    print(f"Camera {device_id} is working:")
    print(f"Resolution: {width}x{height}")
    print(f"FPS: {fps}")
    
    cap.release()
    return True

def main():
    print("USB Camera Test Script")
    print("=====================")
    
    # Test first few video devices
    working_cameras = []
    for i in range(10):  # Test video0 through video9
        if test_camera(i):
            working_cameras.append(i)
            
    if working_cameras:
        print("\nWorking cameras found:", working_cameras)
        print("\nRecommended configuration:")
        print('CAMERA_CONFIGS = {')
        print(f'    0: {{"type": "usb", "device": {working_cameras[0]}, "name": "USB Camera"}},')
        print('    1: {"type": "arducam", "i2c_cmd": "i2cset -y 1 0x70 0x00 0x04", "gpio": (False, False, True), "name": "Camera A"},')
        print('    2: {"type": "arducam", "i2c_cmd": "i2cset -y 1 0x70 0x00 0x05", "gpio": (True, False, True), "name": "Camera B"},')
        print('    3: {"type": "arducam", "i2c_cmd": "i2cset -y 1 0x70 0x00 0x07", "gpio": (True, True, False), "name": "Camera C"}')
        print('}')
    else:
        print("\nNo working cameras found!")

if __name__ == "__main__":
    main() 
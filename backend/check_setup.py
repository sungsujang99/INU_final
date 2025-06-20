#!/usr/bin/env python3
"""
Setup verification script for multi-camera system
"""

import sys
import subprocess
import os

def check_command(cmd, description):
    """Check if a command is available"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ {description}: Available")
            return True
        else:
            print(f"✗ {description}: Not working (exit code: {result.returncode})")
            return False
    except Exception as e:
        print(f"✗ {description}: Error - {e}")
        return False

def check_python_module(module_name, description):
    """Check if a Python module can be imported"""
    try:
        __import__(module_name)
        print(f"✓ {description}: Available")
        return True
    except ImportError as e:
        print(f"✗ {description}: Not available - {e}")
        return False

def check_i2c_device():
    """Check if I2C device is detected"""
    try:
        result = subprocess.run("i2cdetect -y 1", shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            output = result.stdout
            if "70" in output:  # Look for the camera adapter at address 0x70
                print(f"✓ I2C Camera Adapter: Detected at address 0x70")
                return True
            else:
                print(f"✗ I2C Camera Adapter: Not detected at address 0x70")
                print(f"I2C scan output:\n{output}")
                return False
        else:
            print(f"✗ I2C scan failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ I2C check error: {e}")
        return False

def check_gpio_permissions():
    """Check if we can access GPIO"""
    try:
        import RPi.GPIO as gp
        gp.setwarnings(False)
        gp.setmode(gp.BOARD)
        gp.setup(7, gp.OUT)
        gp.cleanup()
        print(f"✓ GPIO Access: Available")
        return True
    except Exception as e:
        print(f"✗ GPIO Access: Error - {e}")
        return False

def main():
    print("=== Multi-Camera System Setup Verification ===\n")
    
    issues = []
    
    print("1. Checking system commands...")
    if not check_command("libcamera-hello --version", "libcamera-hello"):
        issues.append("Install libcamera: sudo apt install libcamera-apps")
    
    if not check_command("i2cdetect -V", "i2c-tools"):
        issues.append("Install i2c-tools: sudo apt install i2c-tools")
    
    print("\n2. Checking Python modules...")
    if not check_python_module("picamera2", "Picamera2"):
        issues.append("Install Picamera2: pip install picamera2")
    
    if not check_python_module("RPi.GPIO", "RPi.GPIO"):
        issues.append("Install RPi.GPIO: pip install RPi.GPIO")
    
    if not check_python_module("cv2", "OpenCV"):
        issues.append("Install OpenCV: pip install opencv-python")
    
    print("\n3. Checking hardware access...")
    if not check_gpio_permissions():
        issues.append("Run as root or add user to gpio group: sudo usermod -a -G gpio $USER")
    
    print("\n4. Checking I2C hardware...")
    if not check_i2c_device():
        issues.append("Check camera adapter connections and enable I2C: sudo raspi-config")
    
    print("\n5. Checking camera interface...")
    if not check_command("vcgencmd get_camera", "Camera interface"):
        issues.append("Enable camera interface: sudo raspi-config -> Interface Options -> Camera")
    
    print("\n" + "="*50)
    
    if not issues:
        print("✓ ALL CHECKS PASSED!")
        print("Your system is ready for the multi-camera setup.")
        print("\nNext steps:")
        print("1. Run: python test_cameras.py")
        print("2. Start the application: python app.py")
        return True
    else:
        print("✗ ISSUES FOUND:")
        for i, issue in enumerate(issues, 1):
            print(f"{i}. {issue}")
        
        print(f"\nPlease fix the above issues and run this script again.")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Setup check failed: {e}")
        sys.exit(1) 
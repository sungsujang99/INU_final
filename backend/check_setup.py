#!/usr/bin/env python3
"""
Setup verification: USB webcams (V4L2) match camera_config.CAMERA_CONFIG.

Optional I2C / Picamera2 checks: python check_setup.py --legacy-i2c
"""

import argparse
import os
import subprocess
import sys

# Running as: python check_setup.py from backend/
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from camera_config import CAMERA_CONFIG  # noqa: E402


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
    """Check if I2C multi-camera adapter is detected"""
    try:
        result = subprocess.run("i2cdetect -y 1", shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            output = result.stdout
            if "70" in output:
                print("✓ I2C Camera Adapter: Detected at address 0x70")
                return True
            print("✗ I2C Camera Adapter: Not detected at address 0x70")
            print(f"I2C scan output:\n{output}")
            return False
        print(f"✗ I2C scan failed: {result.stderr}")
        return False
    except Exception as e:
        print(f"✗ I2C check error: {e}")
        return False


def check_gpio_permissions():
    """Check if we can access GPIO (legacy adapter)"""
    try:
        import RPi.GPIO as gp

        gp.setwarnings(False)
        gp.setmode(gp.BOARD)
        gp.setup(7, gp.OUT)
        gp.cleanup()
        print("✓ GPIO Access: Available")
        return True
    except Exception as e:
        print(f"✗ GPIO Access: Error - {e}")
        return False


def _print_by_path_listing():
    by_path = "/dev/v4l/by-path"
    if not os.path.isdir(by_path):
        print(f"  (no {by_path} directory — not Linux V4L or no USB cameras yet)")
        return
    try:
        names = sorted(os.listdir(by_path))
        video = [n for n in names if "video-index0" in n]
        if not video:
            print(f"  {by_path}: (no *video-index0 nodes)")
            return
        print(f"  Nodes under {by_path} (*video-index0):")
        for n in video:
            print(f"    {n}")
    except OSError as e:
        print(f"  Could not list {by_path}: {e}")


def check_webcam_setup(issues):
    """Verify OpenCV + configured V4L by-path symlinks (see camera_config.py)."""
    print("=== USB Webcam (V4L2) Setup Verification ===\n")

    print("1. Checking V4L helpers...")
    if not check_command("v4l2-ctl --version", "v4l2-ctl (v4l-utils)"):
        issues.append("Install: sudo apt install v4l-utils  (recommended for listing USB cameras)")

    print("\n2. Checking Python (OpenCV)...")
    if not check_python_module("cv2", "OpenCV (cv2)"):
        issues.append("Install OpenCV: pip install opencv-python")

    print("\n3. Checking device paths from camera_config.CAMERA_CONFIG...")
    missing = []
    for rack_id in sorted(CAMERA_CONFIG.keys()):
        cfg = CAMERA_CONFIG[rack_id]
        dev = cfg["device"]
        label = cfg.get("name", rack_id)
        if os.path.exists(dev):
            print(f"✓ [{rack_id}] {label}: {dev}")
        else:
            print(f"✗ [{rack_id}] {label}: missing\n    {dev}")
            missing.append(rack_id)

    if missing:
        issues.append(
            "USB paths missing — on the Pi run: python list_usb_v4l_paths.py "
            "then set camera_config.CAMERA_CONFIG to each *-video-index0 symlink."
        )
        print("\n  Hint: topology differs per hub/port; run python list_usb_v4l_paths.py on the Pi.")
        _print_by_path_listing()

    print("\n4. Video device access...")
    sample = next(
        (CAMERA_CONFIG[r]["device"] for r in CAMERA_CONFIG if os.path.exists(CAMERA_CONFIG[r]["device"])),
        None,
    )
    if sample and not os.access(sample, os.R_OK | os.W_OK):
        print(f"✗ Cannot read/write {sample} — add user to group 'video' and re-login")
        issues.append("sudo usermod -a -G video $USER  (then log out and back in)")
    elif sample:
        print(f"✓ Sample device readable/writable: {sample}")
    elif not missing:
        pass
    else:
        print("  (skipped — no existing device nodes)")

    return issues


def check_legacy_i2c(issues):
    """Optional: I2C adapter + Picamera2 + GPIO + libcamera listing."""
    print("\n=== Legacy I2C / CSI multi-camera adapter (--legacy-i2c) ===\n")

    print("A. System commands...")
    if not check_command("libcamera-hello --version", "libcamera-hello"):
        issues.append("Install libcamera: sudo apt install libcamera-apps")

    if not check_command("i2cdetect -V", "i2c-tools"):
        issues.append("Install i2c-tools: sudo apt install i2c-tools")

    print("\nB. Python modules...")
    if not check_python_module("picamera2", "Picamera2"):
        issues.append("Install Picamera2: pip install picamera2")
    if not check_python_module("RPi.GPIO", "RPi.GPIO"):
        issues.append("Install RPi.GPIO: pip install RPi.GPIO")

    print("\nC. GPIO...")
    if not check_gpio_permissions():
        issues.append("GPIO: sudo usermod -a -G gpio $USER  or install RPi.GPIO")

    print("\nD. I2C hardware...")
    if not check_i2c_device():
        issues.append("Check camera adapter connections and enable I2C: sudo raspi-config")

    print("\nE. libcamera listing...")
    libcam_list = subprocess.run(
        "libcamera-hello --list-cameras",
        shell=True,
        capture_output=True,
        text=True,
    )
    if libcam_list.returncode == 0:
        print("✓ Camera interface: libcamera (list-cameras OK)")
    elif check_command("vcgencmd get_camera", "Camera interface (legacy vcgencmd)"):
        pass
    else:
        issues.append(
            "Camera stack: ensure libcamera works (sudo apt install libcamera-apps) "
            "or legacy camera in raspi-config on older OS"
        )


def main():
    parser = argparse.ArgumentParser(description="Verify INU camera / backend setup")
    parser.add_argument(
        "--legacy-i2c",
        action="store_true",
        help="Also run I2C + Picamera2 + GPIO checks (old multi-adapter stack)",
    )
    args = parser.parse_args()

    issues = []
    check_webcam_setup(issues)

    if args.legacy_i2c:
        check_legacy_i2c(issues)

    print("\n" + "=" * 50)

    if not issues:
        print("✓ ALL CHECKS PASSED!")
        print("\nNext steps:")
        print("  python list_usb_v4l_paths.py  # map USB ports -> /dev/v4l/by-path/")
        print("  python test_usb_cameras.py    # OpenCV capture test")
        print("  python app.py")
        return True

    print("✗ ISSUES FOUND:")
    for i, issue in enumerate(issues, 1):
        print(f"  {i}. {issue}")
    print("\nFix the above and run this script again.")
    print("  (CSI/I2C adapter only: python check_setup.py --legacy-i2c)")
    return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Setup check failed: {e}")
        sys.exit(1)

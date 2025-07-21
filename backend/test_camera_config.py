#!/usr/bin/env python3
import time
import os
import lgpio
import cv2
from picamera2 import Picamera2
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize GPIO
try:
    gpio_chip = lgpio.gpiochip_open(0)
    # Setup GPIO pins as outputs (using BCM pin numbers)
    lgpio.gpio_claim_output(gpio_chip, 4)   # Pin 7 (BOARD) = Pin 4 (BCM)
    lgpio.gpio_claim_output(gpio_chip, 17)  # Pin 11 (BOARD) = Pin 17 (BCM)
    lgpio.gpio_claim_output(gpio_chip, 18)  # Pin 12 (BOARD) = Pin 18 (BCM)
    logger.info("GPIO initialized successfully")
except Exception as e:
    logger.error(f"GPIO initialization failed: {e}")
    gpio_chip = None
    exit(1)

def set_gpio(pin7, pin11, pin12):
    """Set GPIO pins"""
    try:
        lgpio.gpio_write(gpio_chip, 4, 1 if pin7 else 0)    # Pin 7
        lgpio.gpio_write(gpio_chip, 17, 1 if pin11 else 0)  # Pin 11
        lgpio.gpio_write(gpio_chip, 18, 1 if pin12 else 0)  # Pin 12
        logger.info(f"GPIO set: Pin 7={pin7}, Pin 11={pin11}, Pin 12={pin12}")
        return True
    except Exception as e:
        logger.error(f"Error setting GPIO: {e}")
        return False

def test_camera_config(i2c_cmd, gpio_config, name):
    """Test a specific camera configuration"""
    logger.info(f"\nTesting {name}")
    logger.info(f"I2C command: {i2c_cmd}")
    logger.info(f"GPIO config: {gpio_config}")
    
    # Set GPIO pins
    if not set_gpio(*gpio_config):
        return False
    
    # Execute I2C command
    result = os.system(i2c_cmd)
    if result != 0:
        logger.error(f"I2C command failed with code {result}")
        return False
    
    # Wait for camera to settle
    time.sleep(2)
    
    try:
        # Try to capture with Picamera2
        picam = Picamera2(0)
        config = picam.create_preview_configuration(
            main={"size": (640, 480), "format": "RGB888"}
        )
        picam.configure(config)
        picam.start()
        time.sleep(2)
        
        # Try to capture a frame
        array = picam.capture_array()
        if array is not None:
            logger.info(f"✓ Successfully captured frame: {array.shape}")
            # Save test image
            cv2.imwrite(f"test_{name.lower().replace(' ', '_')}.jpg", array)
            logger.info(f"Saved test image as test_{name.lower().replace(' ', '_')}.jpg")
            picam.stop()
            picam.close()
            return True
        else:
            logger.error("Failed to capture frame")
            picam.stop()
            picam.close()
            return False
            
    except Exception as e:
        logger.error(f"Error testing camera: {e}")
        try:
            picam.stop()
            picam.close()
        except:
            pass
        return False

def main():
    logger.info("=== Camera Configuration Test ===")
    
    # Test configurations
    configs = [
        # Original configurations
        {
            "i2c": "i2cset -y 1 0x70 0x00 0x04",
            "gpio": (False, False, True),
            "name": "Camera A (Original)"
        },
        {
            "i2c": "i2cset -y 1 0x70 0x00 0x05",
            "gpio": (True, False, True),
            "name": "Camera B (Original)"
        },
        {
            "i2c": "i2cset -y 1 0x70 0x00 0x06",
            "gpio": (False, True, False),
            "name": "Camera C (Original)"
        },
        {
            "i2c": "i2cset -y 1 0x70 0x00 0x07",
            "gpio": (True, True, False),
            "name": "Camera D (Original)"
        },
        # Alternative configurations
        {
            "i2c": "i2cset -y 1 0x70 0x00 0x01",
            "gpio": (False, False, True),
            "name": "Camera Alt 1"
        },
        {
            "i2c": "i2cset -y 1 0x70 0x00 0x02",
            "gpio": (True, False, True),
            "name": "Camera Alt 2"
        },
        {
            "i2c": "i2cset -y 1 0x70 0x00 0x03",
            "gpio": (False, True, False),
            "name": "Camera Alt 3"
        }
    ]
    
    working_configs = []
    
    for config in configs:
        if test_camera_config(config["i2c"], config["gpio"], config["name"]):
            working_configs.append(config)
            logger.info(f"✓ {config['name']} configuration WORKS")
        else:
            logger.info(f"✗ {config['name']} configuration FAILED")
        
        # Reset GPIO to default state between tests
        set_gpio(False, False, True)
        time.sleep(2)
    
    logger.info("\n=== Results ===")
    if working_configs:
        logger.info("Working configurations:")
        for config in working_configs:
            logger.info(f"\n{config['name']}:")
            logger.info(f"I2C: {config['i2c']}")
            logger.info(f"GPIO: {config['gpio']}")
    else:
        logger.info("No working configurations found!")
    
    # Cleanup
    set_gpio(False, False, True)
    lgpio.gpio_close(gpio_chip)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
        # Cleanup
        set_gpio(False, False, True)
        lgpio.gpio_close(gpio_chip)
    except Exception as e:
        logger.error(f"Error during testing: {e}")
        # Cleanup
        set_gpio(False, False, True)
        lgpio.gpio_close(gpio_chip) 
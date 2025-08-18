#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
INU Logistics Camera Stream
- Uses stable /dev/v4l/by-path/*-video-index0 device nodes
- Forces MJPEG, sets low-latency buffers, and streams on-demand
"""

import os
import cv2
import time
import logging
import threading
import numpy as np
from typing import Optional, Dict
from flask import Response

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Camera configurations with stable device paths
CAMERA_CONFIG = {
    'M': {
        'device': '/dev/v4l/by-path/platform-xhci-hcd.0-usb-0:1.4.4.1:1.0-video-index0',
        'name': 'Main Camera'
    },
    'A': {
        'device': '/dev/v4l/by-path/platform-xhci-hcd.0-usb-0:1.4.4.2:1.0-video-index0',
        'name': 'Rack A Camera'
    },
    'B': {
        'device': '/dev/v4l/by-path/platform-xhci-hcd.0-usb-0:1.4.4.3:1.0-video-index0',
        'name': 'Rack B Camera'
    },
    'C': {
        'device': '/dev/v4l/by-path/platform-xhci-hcd.0-usb-0:1.4.4.4:1.0-video-index0',
        'name': 'Rack C Camera'
    }
}

DEFAULT_WIDTH = 640   # Camera resolution width
DEFAULT_HEIGHT = 480  # Camera resolution height
DEFAULT_FPS = 30      # Camera frame rate
DEFAULT_JPEG_Q = 80   # JPEG encoding quality

class USBCamera:
    def __init__(self, device_path: str, name: str,
                 width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT, fps: int = DEFAULT_FPS):
        self.device_path = device_path
        self.name = name
        self.width = width
        self.height = height
        self.fps = fps

        self.cap: Optional[cv2.VideoCapture] = None
        self.frame: Optional[np.ndarray] = None
        self.last_frame_time = 0.0
        self.lock = threading.Lock()
        self.running = False

    def start(self) -> bool:
        logger.info(f"Starting {self.name} at {self.device_path}")
        self.running = True
        return self._init_camera()

    def _init_camera(self) -> bool:
        try:
            # Prefer V4L2 backend
            cap = cv2.VideoCapture(self.device_path, cv2.CAP_V4L2)
            if not cap.isOpened():
                cap = cv2.VideoCapture(self.device_path)
            if not cap.isOpened():
                logger.error(f"[{self.name}] Failed to open {self.device_path}")
                return False

            # Force MJPEG first, then resolution/fps, then minimal buffering
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            cap.set(cv2.CAP_PROP_FPS, self.fps)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            time.sleep(0.3)

            # Multiple capture attempts
            ok = False
            last = None
            for _ in range(8):
                ret, frame = cap.read()
                if ret and frame is not None:
                    ok = True
                    last = frame
                    break
                time.sleep(0.1)

            if not ok:
                logger.error(f"[{self.name}] Failed to capture test frame")
                cap.release()
                return False

            # Assign once proven working
            self.cap = cap
            with self.lock:
                self.frame = last
                self.last_frame_time = time.time()

            logger.info(f"[{self.name}] Initialized ({self.width}x{self.height}@{self.fps} MJPEG)")
            return True

        except Exception as e:
            logger.exception(f"[{self.name}] Error initializing: {e}")
            try:
                cap.release()
            except Exception:
                pass
            return False

    def get_frame(self) -> Optional[np.ndarray]:
        """Capture a fresh frame. Reopen the device once if needed."""
        try:
            if not self.cap or not self.cap.isOpened():
                logger.warning(f"[{self.name}] Capture not open; reinitializing")
                if not self._init_camera():
                    return None

            ret, frame = self.cap.read()
            if ret and frame is not None:
                with self.lock:
                    self.frame = frame
                    self.last_frame_time = time.time()
                return frame

            # one retry via reopen
            logger.warning(f"[{self.name}] Read failed; reopening")
            self.cap.release()
            self.cap = None
            if self._init_camera():
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    with self.lock:
                        self.frame = frame
                        self.last_frame_time = time.time()
                    return frame
            return None

        except Exception as e:
            logger.error(f"[{self.name}] Error capturing frame: {e}")
            return None

    def stop(self):
        self.running = False
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
        self.cap = None
        logger.info(f"[{self.name}] Stopped")

class CameraManager:
    def __init__(self):
        self.cameras: Dict[str, USBCamera] = {}
        self._init_cameras()

    def _init_cameras(self):
        """Initialize cameras in specific order with delays"""
        for cam_id in ['C', 'B', 'A', 'M']:  # Initialize in this order
            cfg = CAMERA_CONFIG.get(cam_id)
            if not cfg:
                continue
            dev = cfg['device']
            if not os.path.exists(dev):
                logger.error(f"[{cam_id}] Device path not found: {dev}")
                continue
            cam = USBCamera(dev, cfg['name'])
            if cam.start():
                self.cameras[cam_id] = cam
                logger.info(f"[{cam_id}] Ready: {dev}")
            else:
                logger.error(f"[{cam_id}] Failed to initialize: {dev}")
            time.sleep(0.6)  # Delay between initializations

    def get_frame(self, rack_id: str) -> Optional[np.ndarray]:
        """Get frame from specific camera"""
        camera = self.cameras.get(rack_id)
        if camera:
            return camera.get_frame()
        return None

    def get_generator(self, rack_id: str):
        """Generate MJPEG stream for a specific camera"""
        frame_interval = 1.0 / DEFAULT_FPS
        last_frame_time = 0

        while True:
            try:
                current_time = time.time()
                if current_time - last_frame_time >= frame_interval:
                    frame = self.get_frame(rack_id)
                    if frame is not None:
                        ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, DEFAULT_JPEG_Q])
                        if ret:
                            yield (b'--frame\r\n'
                                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
                            last_frame_time = current_time
                time.sleep(0.005)  # Small sleep to prevent busy waiting
            except Exception as e:
                logger.error(f"Error in frame generator for {rack_id}: {e}")
                time.sleep(0.2)

    def get_available_cameras(self) -> list:
        """Get list of available cameras"""
        return list(self.cameras.keys())

    def stop(self):
        """Stop all cameras"""
        for camera in self.cameras.values():
            camera.stop()

# Global camera manager instance
camera_manager = CameraManager()

def get_available_cameras():
    """Get list of available cameras"""
    try:
        return camera_manager.get_available_cameras()
    except Exception as e:
        logger.error(f"Error getting available cameras: {e}")
        return []

def mjpeg_feed(rack_id: str = 'M'):
    """Get MJPEG feed for specified rack"""
    logger.info(f"MJPEG feed requested for rack {rack_id}")
    return Response(
        camera_manager.get_generator(rack_id),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

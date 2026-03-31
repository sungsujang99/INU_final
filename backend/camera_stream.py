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
from typing import Any, Optional, Dict
from flask import Response

try:
    from .camera_config import CAMERA_CONFIG, resolve_rack_to_device
except ImportError:
    from camera_config import CAMERA_CONFIG, resolve_rack_to_device

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        self.last_fail_reason = ""

    def start(self) -> bool:
        logger.info(f"Starting {self.name} at {self.device_path}")
        self.running = True
        return self._init_camera()

    def _warmup_capture(self, cap: cv2.VideoCapture) -> tuple:
        """Try to read one good frame after properties are set."""
        time.sleep(0.25)
        for _ in range(10):
            ret, frame = cap.read()
            if ret and frame is not None:
                return True, frame
            time.sleep(0.1)
        return False, None

    def _init_camera(self) -> bool:
        cap = None
        try:
            # (mjpeg?, fixed 640x480?) — cheap UVC cams often need "native" (no size/MJPG) to return frames.
            attempts = ((True, True), (False, True), (False, False))
            for prefer_mjpeg, set_resolution in attempts:
                cap = cv2.VideoCapture(self.device_path, cv2.CAP_V4L2)
                if not cap.isOpened():
                    cap = cv2.VideoCapture(self.device_path)
                if not cap.isOpened():
                    self.last_fail_reason = "VideoCapture could not open device"
                    logger.error(f"[{self.name}] Failed to open {self.device_path}")
                    return False

                if prefer_mjpeg:
                    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                if set_resolution:
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                    cap.set(cv2.CAP_PROP_FPS, self.fps)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                ok, last = self._warmup_capture(cap)
                if ok:
                    self.cap = cap
                    with self.lock:
                        self.frame = last
                        self.last_frame_time = time.time()
                    fmt = "MJPG" if prefer_mjpeg else "YUYV/default"
                    res = f"{self.width}x{self.height}" if set_resolution else "native"
                    logger.info(f"[{self.name}] Initialized ({fmt}, {res} @ ~{self.fps} fps requested)")
                    self.last_fail_reason = ""
                    return True

                logger.warning(
                    f"[{self.name}] No frame (mjpeg={prefer_mjpeg}, fixed_res={set_resolution}); trying next mode"
                )
                cap.release()
                cap = None

            self.last_fail_reason = "opened OK but no frames (tried MJPG+640, YUYV+640, native)"
            logger.error(f"[{self.name}] Failed to capture test frame after all modes")
            return False

        except Exception as e:
            self.last_fail_reason = str(e)
            logger.exception(f"[{self.name}] Error initializing: {e}")
            try:
                if cap is not None:
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
        self._diagnostics: Dict[str, Dict[str, Any]] = {}
        self._resolution_meta: Dict[str, Any] = {}
        self._init_cameras()

    def _init_cameras(self):
        """Initialize cameras in specific order with delays (spacing helps multi-cam USB hubs)."""
        resolved, self._resolution_meta = resolve_rack_to_device()
        for cam_id in ['A', 'B', 'C', 'M']:  # M last (matches auto-map A→B→C→M)
            if cam_id in self.cameras:
                continue
            cfg = CAMERA_CONFIG.get(cam_id)
            if not cfg:
                continue
            configured = cfg["device"]
            dev = resolved.get(cam_id)
            rec: Dict[str, Any] = {
                "rack": cam_id,
                "name": cfg.get("name", cam_id),
                "configured_path": configured,
                "path": dev or configured,
            }
            if not dev or not os.path.exists(dev):
                rec["ok"] = False
                rec["error"] = (
                    "no device path (see resolution.hint) — plug UVC cameras, check by-path, "
                    "or fix CAMERA_CONFIG"
                )
                if self._resolution_meta.get("hint"):
                    rec["resolution_hint"] = self._resolution_meta["hint"]
                self._diagnostics[cam_id] = rec
                logger.error(f"[{cam_id}] No resolved path (configured was {configured})")
                continue
            if dev != configured:
                rec["resolved_from"] = "auto-discovery" if self._resolution_meta.get("mode") == "auto" else "partial"
            rec["exists"] = True
            rec["rw"] = os.access(dev, os.R_OK | os.W_OK)
            if not rec["rw"]:
                rec["hint"] = "add user to group 'video' and use SupplementaryGroups=video in systemd"
            cam = USBCamera(dev, cfg["name"])
            if cam.start():
                self.cameras[cam_id] = cam
                rec["ok"] = True
                logger.info(f"[{cam_id}] Ready: {dev}")
            else:
                rec["ok"] = False
                rec["error"] = cam.last_fail_reason or "start() failed"
                logger.error(f"[{cam_id}] Failed to initialize: {dev}")
            self._diagnostics[cam_id] = rec
            time.sleep(1.2)

    def get_diagnostics(self) -> Dict[str, Any]:
        return {
            "racks": {k: dict(v) for k, v in self._diagnostics.items()},
            "opened": sorted(self.cameras.keys()),
            "resolution": dict(self._resolution_meta),
        }

    def ensure_cameras(self) -> None:
        """If import-time init saw no USB (common under systemd), try again on first HTTP hit."""
        if self.cameras:
            return
        logger.warning("CameraManager has 0 devices — retrying open (USB may have been late at boot)")
        self._init_cameras()

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
        camera_manager.ensure_cameras()
        return camera_manager.get_available_cameras()
    except Exception as e:
        logger.error(f"Error getting available cameras: {e}")
        return []


def get_camera_diagnostics() -> Dict[str, Any]:
    """Per-rack open/capture status for troubleshooting empty /api/cameras/available."""
    camera_manager.ensure_cameras()
    return camera_manager.get_diagnostics()


def mjpeg_feed(rack_id: str = 'M'):
    """Get MJPEG feed for specified rack"""
    camera_manager.ensure_cameras()
    logger.info(f"MJPEG feed requested for rack {rack_id}")
    return Response(
        camera_manager.get_generator(rack_id),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

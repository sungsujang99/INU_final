#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stable V4L device paths for USB webcams — shared by camera_stream and check_setup.

Paths use the kernel xhci USB topology (e.g. …usb-0:1.4.4.N…). Identical webcams often
share the same USB serial in udev; **by-path** is the stable differentiator. Re-run
`python list_usb_v4l_paths.py` if you move cables or hubs.

If **every** configured path is missing but **1–4** UVC symlinks exist, racks **M, A, B, C**
are filled in **sorted** by-path order for as many devices as you have (**auto_partial** when under four).
Use **`link_cameras.py`** to remap a rack to a specific physical camera.

**Per-camera mapping (recommended):** plug cameras, run **`python link_cameras.py --list`**, then
**`python link_cameras.py --assign M=0 A=1 B/C=…`** (or interactive **`python link_cameras.py`**),
and paste the printed block into **`CAMERA_CONFIG`** below so each rack points at the right physical USB path.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)

# Camera configurations with stable device paths (/dev/v4l/by-path/...)
CAMERA_CONFIG: Dict[str, Dict[str, str]] = {
    "M": {
        "device": "/dev/v4l/by-path/platform-xhci-hcd.0-usb-0:1.4.4.1:1.0-video-index0",
        "name": "Main Camera",
    },
    "A": {
        "device": "/dev/v4l/by-path/platform-xhci-hcd.0-usb-0:1.4.4.2:1.0-video-index0",
        "name": "Rack A Camera",
    },
    "B": {
        "device": "/dev/v4l/by-path/platform-xhci-hcd.0-usb-0:1.4.4.3:1.0-video-index0",
        "name": "Rack B Camera",
    },
    "C": {
        "device": "/dev/v4l/by-path/platform-xhci-hcd.0-usb-0:1.4.4.4:1.0-video-index0",
        "name": "Rack C Camera",
    },
}

RACK_ORDER_MABC = ("M", "A", "B", "C")
_BY_PATH = "/dev/v4l/by-path"


def _usb_uvc_video_index0(name: str) -> bool:
    """Symlink name under by-path for a USB UVC capture node (not Pi SoC pisp/codec)."""
    if "video-index0" not in name:
        return False
    n = name.lower()
    if "xhci-hcd" in n or ("pci-" in n and "usb" in n) or ("dwc3" in n and "usb" in n):
        return True
    return False


def resolve_rack_to_device() -> Tuple[Dict[str, str], Dict[str, Any]]:
    """
    Map rack letters to absolute device paths.

    Returns:
        (rack -> path, meta) where meta includes mode: configured | auto | partial | none
    """
    meta: Dict[str, Any] = {"mode": "none"}
    explicit: Dict[str, str] = {}
    for rack_id, cfg in CAMERA_CONFIG.items():
        dev = cfg["device"]
        if os.path.exists(dev):
            explicit[rack_id] = dev

    if len(explicit) == len(CAMERA_CONFIG):
        meta["mode"] = "configured"
        return explicit, meta

    if len(explicit) > 0:
        meta["mode"] = "partial"
        meta["missing_racks"] = [k for k in RACK_ORDER_MABC if k not in explicit]
        return explicit, meta

    if not os.path.isdir(_BY_PATH):
        meta["hint"] = f"{_BY_PATH} missing — not Linux V4L or no drivers"
        return {}, meta

    names = sorted(n for n in os.listdir(_BY_PATH) if _usb_uvc_video_index0(n))
    meta["found_uvc_video_index0"] = len(names)
    if names:
        meta["candidates"] = names[:8]

    if len(names) < 1:
        meta["mode"] = "none"
        meta["hint"] = (
            "All CAMERA_CONFIG symlinks missing and no UVC *video-index0* found. "
            "Plug cameras / powered hub, or run: python list_usb_v4l_paths.py"
        )
        return {}, meta

    n = len(names)
    racks_used = RACK_ORDER_MABC[:n]
    meta["mode"] = "auto" if n == len(RACK_ORDER_MABC) else "auto_partial"
    meta["symlinks"] = names
    meta["racks_mapped"] = list(racks_used)
    if n < len(RACK_ORDER_MABC):
        meta["missing_racks"] = list(RACK_ORDER_MABC[n:])
        meta["hint"] = (
            f"Auto-mapped {n} UVC device(s) to racks {','.join(racks_used)} (sorted by-path order). "
            "Use `python link_cameras.py` if a rack is the wrong physical camera; "
            "pin paths in CAMERA_CONFIG. Add more cameras for remaining racks."
        )
        logger.warning(
            "CAMERA_CONFIG paths missing; auto-mapped %d UVC symlink(s) → %s",
            n,
            ",".join(racks_used),
        )
    else:
        meta["hint"] = (
            "Auto-mapped 4 UVC devices M,A,B,C ← sorted by-path. "
            "Confirm with list_usb_v4l_paths.py / link_cameras.py and paste into CAMERA_CONFIG."
        )
        logger.warning(
            "CAMERA_CONFIG paths all missing; auto-mapped 4 UVC devices to M,A,B,C by sorted symlink name"
        )

    out = {rack: os.path.join(_BY_PATH, sym) for rack, sym in zip(racks_used, names)}
    return out, meta

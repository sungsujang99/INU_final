#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stable V4L device paths for USB webcams — shared by camera_stream and check_setup.

Paths use the kernel xhci USB topology (e.g. …usb-0:1.4.4.N…). Identical webcams often
share the same USB serial in udev; **by-path** is the stable differentiator. Re-run
`python list_usb_v4l_paths.py` if you move cables or hubs.
"""

# Camera configurations with stable device paths (/dev/v4l/by-path/...)
CAMERA_CONFIG = {
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

#!/usr/bin/env python3
"""
Map each physical UVC camera (by-path symlink) to racks M, A, B, C.

Run on the Raspberry Pi from backend/ with venv active:

  python link_cameras.py --list
  python link_cameras.py --assign M=0 A=1 B=2

Or run interactively (prompts per rack):

  python link_cameras.py

Tip: with all cameras plugged, note the numbered list; assign indices so each rack
matches the correct physical unit (unplug one camera to see which line disappears).
"""

from __future__ import annotations

import argparse
import os
import sys

_BY = "/dev/v4l/by-path"
# Prompt / assign order: main **M** last (same as auto-discovery).
_RACKS = ("A", "B", "C", "M")
_NAMES = {
    "M": "Main Camera",
    "A": "Rack A Camera",
    "B": "Rack B Camera",
    "C": "Rack C Camera",
}


def _usb_uvc_video_index0(name: str) -> bool:
    if "video-index0" not in name:
        return False
    n = name.lower()
    return "xhci-hcd" in n or ("pci-" in n and "usb" in n) or ("dwc3" in n and "usb" in n)


def list_symlinks() -> list[str]:
    if not os.path.isdir(_BY):
        return []
    return sorted(n for n in os.listdir(_BY) if _usb_uvc_video_index0(n))


def print_list() -> list[str]:
    names = list_symlinks()
    print(f"UVC capture symlinks under {_BY} (*video-index0*, USB):\n")
    if not names:
        print("  (none — plug webcams and check lsusb / powered hub)\n")
        return names
    for i, n in enumerate(names):
        full = os.path.join(_BY, n)
        print(f"  [{i}] {full}")
    print()
    return names


def emit_camera_config(assignments: dict[str, str]) -> None:
    """assignments: rack -> full device path"""
    print("Replace the matching keys inside CAMERA_CONFIG in camera_config.py with:\n")
    for rack in _RACKS:
        if rack not in assignments:
            continue
        path = assignments[rack]
        name = _NAMES[rack]
        print(f'    "{rack}": {{')
        print(f'        "device": "{path}",')
        print(f'        "name": "{name}",')
        print("    },")
    if len(assignments) < len(_RACKS):
        print("\n(Leave other racks unchanged until those cameras are plugged; then run this again.)\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="Link UVC by-path devices to M/A/B/C")
    ap.add_argument(
        "--list",
        action="store_true",
        help="Print numbered UVC symlinks and exit",
    )
    ap.add_argument(
        "--assign",
        nargs="*",
        metavar="RACK=INDEX",
        help="e.g. --assign M=0 A=1 B=2  (indices from --list)",
    )
    args = ap.parse_args()

    names = list_symlinks()
    if args.list:
        print_list()
        return 0 if names else 1

    assignments: dict[str, str] = {}

    if args.assign:
        for pair in args.assign:
            if "=" not in pair:
                print(f"Bad --assign token (need RACK=INDEX): {pair}", file=sys.stderr)
                return 2
            rack, _, idx_s = pair.partition("=")
            rack = rack.strip().upper()
            if rack not in _RACKS:
                print(f"Unknown rack {rack!r}; use one of {_RACKS}", file=sys.stderr)
                return 2
            try:
                idx = int(idx_s.strip())
            except ValueError:
                print(f"Bad index for {rack}: {idx_s!r}", file=sys.stderr)
                return 2
            if idx < 0 or idx >= len(names):
                print(
                    f"Index {idx} out of range (0..{len(names) - 1}); run --list first.",
                    file=sys.stderr,
                )
                return 2
            path = os.path.join(_BY, names[idx])
            assignments[rack] = path
        emit_camera_config(assignments)
        return 0

    # Interactive
    print_list()
    if not names:
        return 1
    print("For each rack, type the index [0..{}] for that physical camera, or Enter to skip.\n".format(len(names) - 1))
    for rack in _RACKS:
        try:
            raw = input(f"  Rack {rack} ({_NAMES[rack]}) index? ").strip()
        except EOFError:
            break
        if not raw:
            continue
        try:
            idx = int(raw)
        except ValueError:
            print("    (skipped — not a number)")
            continue
        if idx < 0 or idx >= len(names):
            print("    (skipped — out of range)")
            continue
        assignments[rack] = os.path.join(_BY, names[idx])
    if not assignments:
        print("No assignments; nothing to emit.")
        return 1
    print()
    emit_camera_config(assignments)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

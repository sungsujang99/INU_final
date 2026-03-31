#!/usr/bin/env python3
"""
Map USB ports to V4L devices on Linux (Raspberry Pi).

Run on the Pi:
  cd backend && source venv/bin/activate
  python list_usb_v4l_paths.py

Use the printed *-video-index0 lines under /dev/v4l/by-path/ as CAMERA_CONFIG paths
in camera_config.py (match each physical USB socket to M / A / B / C).
"""

from __future__ import annotations

import glob
import os
import subprocess
import sys


def sh(
    title: str,
    cmd: str,
    *,
    ok_codes: tuple[int, ...] = (0,),
) -> None:
    print(f"\n{'═' * 64}\n{title}\n{'═' * 64}")
    try:
        r = subprocess.run(
            cmd,
            shell=True,
            text=True,
            capture_output=True,
        )
    except Exception as e:
        print(f"(failed to run) {e}")
        return
    if r.stdout:
        print(r.stdout.rstrip())
    if r.stderr and r.returncode not in ok_codes:
        print(r.stderr.rstrip(), file=sys.stderr)
    if r.returncode not in ok_codes:
        print(f"(exit {r.returncode})")


def list_by_path() -> None:
    base = "/dev/v4l/by-path"
    print(f"\n{'═' * 64}\nStable paths: {base}\n{'═' * 64}")
    if not os.path.isdir(base):
        print("Directory missing — no V4L devices or not Linux.")
        return
    names = sorted(os.listdir(base))
    if not names:
        print("Empty — plug in USB cameras and re-run.")
        return
    for name in names:
        full = os.path.join(base, name)
        try:
            if os.path.islink(full):
                tgt = os.readlink(full)
                real = os.path.realpath(full)
                mark = "  <-- use *video-index0* for capture" if "video-index0" in name else ""
                print(f"  {name}{mark}")
                print(f"      -> {tgt}")
                print(f"      realpath: {real}")
            else:
                print(f"  {name} (not a symlink)")
        except OSError as e:
            print(f"  {name}: {e}")


def udev_video_hints() -> None:
    print(f"\n{'═' * 64}\nudev paths (ID_PATH) for /dev/video*\n{'═' * 64}")
    devices = sorted(glob.glob("/dev/video*"))
    if not devices:
        print("No /dev/video* nodes.")
        return
    for dev in devices:
        try:
            r = subprocess.run(
                ["udevadm", "info", "-q", "property", "-n", dev],
                text=True,
                capture_output=True,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            print(f"{dev}: udevadm: {e}")
            continue
        if r.returncode != 0:
            print(f"{dev}: udevadm exit {r.returncode}")
            continue
        props = {}
        for line in r.stdout.splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                props[k] = v
        id_path = props.get("ID_PATH", "")
        serial = props.get("ID_SERIAL_SHORT") or props.get("ID_SERIAL") or ""
        usb = props.get("ID_USB_INSTANCE") or props.get("ID_USB_INTERFACE_NUM") or ""
        print(f"  {dev}")
        if id_path:
            print(f"      ID_PATH={id_path}")
        if serial:
            print(f"      ID_SERIAL={serial}")
        if usb:
            print(f"      USB_META={usb}")


def main() -> None:
    print("USB + V4L diagnostic (run on Raspberry Pi)\n")

    sh("USB tree", "lsusb -t 2>/dev/null || true")
    sh("USB list", "lsusb 2>/dev/null || true")
    sh("V4L devices (v4l2-ctl)", "v4l2-ctl --list-devices 2>/dev/null || true", ok_codes=(0, 127))

    list_by_path()
    udev_video_hints()

    print(f"\n{'═' * 64}\nNext step\n{'═' * 64}")
    print(
        "Copy each full line starting with /dev/v4l/by-path/...-video-index0 "
        "into camera_config.py for M / A / B / C.\n"
        "Unplug one camera at a time to see which by-path line disappears "
        "and label that port."
    )


if __name__ == "__main__":
    main()

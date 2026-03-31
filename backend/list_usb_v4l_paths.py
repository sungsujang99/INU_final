#!/usr/bin/env python3
"""
Map USB ports to V4L devices on Linux (Raspberry Pi).

Run on the Pi:
  cd backend && source venv/bin/activate
  python list_usb_v4l_paths.py

Use *USB* *-video-index0* lines under /dev/v4l/by-path/ (names containing xhci-hcd
or pci-...-usb) in camera_config.py. Ignore platform-...pisp / codec — those are
the Pi GPU/ISP, not your USB webcams.

**Several UVC webcams (e.g. four) on one hub** need a **powered** USB hub; unpowered
hubs often produce “unable to enumerate”, error -32/-71, and missing /dev/video*
nodes. Splitting cameras across the Pi’s ports + hub helps.
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
) -> str:
    """Print section; return stdout for analysis."""
    print(f"\n{'═' * 64}\n{title}\n{'═' * 64}")
    out = ""
    try:
        r = subprocess.run(
            cmd,
            shell=True,
            text=True,
            capture_output=True,
        )
    except Exception as e:
        print(f"(failed to run) {e}")
        return ""
    out = r.stdout or ""
    if out.strip():
        print(out.rstrip())
    if r.stderr and r.returncode not in ok_codes:
        print(r.stderr.rstrip(), file=sys.stderr)
    if r.returncode not in ok_codes:
        print(f"(exit {r.returncode})")
    return out


def _read_sysfs(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def scan_sysfs_usb_video_class() -> int:
    """Count USB interfaces with bInterfaceClass 0x0e (Video) — real UVC/webcams."""
    base = "/sys/bus/usb/devices"
    print(f"\n{'═' * 64}\nKernel sysfs: USB Video class (0x0e) — if 0, Pi does not see a UVC camera\n{'═' * 64}")
    if not os.path.isdir(base):
        print("(no /sys/bus/usb/devices)")
        return 0
    found = 0
    for name in sorted(os.listdir(base)):
        if ":" not in name:
            continue
        dev_id, iface_tail = name.rsplit(":", 1)
        if not iface_tail.replace(".", "").isdigit():
            continue
        iface_dir = os.path.join(base, name)
        cls_raw = _read_sysfs(os.path.join(iface_dir, "bInterfaceClass"))
        if cls_raw is None:
            continue
        try:
            cls = int(cls_raw.replace("0x", "").strip(), 16)
        except ValueError:
            continue
        if cls != 0x0E:
            continue
        found += 1
        dev_dir = os.path.join(base, dev_id)
        vid = _read_sysfs(os.path.join(dev_dir, "idVendor"))
        pid = _read_sysfs(os.path.join(dev_dir, "idProduct"))
        prod = _read_sysfs(os.path.join(dev_dir, "product")) or "?"
        manu = _read_sysfs(os.path.join(dev_dir, "manufacturer")) or "?"
        dlink = os.path.join(iface_dir, "driver")
        driver = os.path.basename(os.readlink(dlink)) if os.path.islink(dlink) else "(no driver)"
        print(f"  • Bus device {dev_id}  {vid}:{pid}  {manu} — {prod}")
        print(f"    iface {name}  driver={driver}")
    if found == 0:
        print(
            "  (count = 0) Nothing on USB is presenting as a Video device to the kernel.\n"
            "  Cables can be plugged in and you still get this if:\n"
            "    – the device is not a UVC webcam (e.g. CH340 serial, MCU, non‑UVC sensor),\n"
            "    – or it is failing USB negotiation (try a powered hub, shorter cable, direct port),\n"
            "    – or it is a CSI/ribbon camera (uses CSI, not this USB stack)."
        )
    return found


def recent_kernel_usb_lines() -> str:
    print(f"\n{'═' * 64}\nLast kernel lines mentioning usb/new/full-speed/error (plug in/out, re-run)\n{'═' * 64}")
    for cmd in (
        "dmesg -T 2>/dev/null | grep -iE 'usb|uvc|video' | tail -n 50",
        "journalctl -k -n 50 --no-pager 2>/dev/null | grep -iE 'usb|uvc|video'",
    ):
        r = subprocess.run(cmd, shell=True, text=True, capture_output=True, timeout=10)
        if (r.stdout or "").strip():
            print(r.stdout.rstrip())
            return r.stdout
    print("  (no dmesg/journalctl output — try:  sudo dmesg -T | tail -50 )")
    return ""


def interpret_dmesg_hub_and_uvc_vs_serial(dmesg: str) -> None:
    """Explain common patterns: multi-cam hub power, CH341 vs uvcvideo."""
    if not (dmesg or "").strip():
        return
    low = dmesg.lower()
    print(f"\n{'═' * 64}\nReading your log (hub + multiple USB devices)\n{'═' * 64}")

    if (
        "unable to enumerate" in low
        or "error -71" in dmesg
        or "error -32" in dmesg
        or "not accepting address" in low
        or "device descriptor read" in low
    ):
        print(
            "• **Enumeration errors** on a hub port (e.g. `unable to enumerate USB device`,\n"
            "  `device descriptor read/64, error -32`, `error -71`, device not accepting address)\n"
            "  almost always mean **power / signal**, not application software:\n"
            "  – **Unpowered hub** or supply too weak for **four** cameras.\n"
            "  – Use a **powered USB 3 hub** with an adequate adapter (many webcams need **0.5–0.9 A each**).\n"
            "  – **Spread load**: e.g. two cameras on the **Pi’s USB ports**, two on a **powered** hub.\n"
            "  – Try **shorter cables**, another port, or **one camera at a time** to find the bad link.\n"
        )

    ch341 = dmesg.count("ch341-uart converter now attached")
    if ch341 >= 1:
        print(
            f"• The kernel bound **{ch341}× CH341 UART** (`ch341-uart` → ttyUSB*). That is the **serial**\n"
            "  driver for **1a86:7523**, **not** a webcam driver. **`camera_stream` / OpenCV V4L**\n"
            "  needs the **uvcvideo** driver and **USB Video class 0x0e** (see sysfs section above).\n\n"
            "  If you truly have **four UVC webcams**, after fixing hub power you should see **different**\n"
            "  USB product/vendor lines and **uvcvideo** in dmesg, and this script will show **Video 0x0e**.\n"
            "  If every device still shows as **CH340/7523**, they are **not** standard UVC cameras to Linux.\n"
        )


def is_usb_uvc_by_path(name: str) -> bool:
    """True if this by-path symlink is for a USB V4L device (not Pi SoC ISP/codec)."""
    if "video-index0" not in name:
        return False
    n = name.lower()
    if "xhci-hcd" in n:
        return True
    if "pci-" in n and "usb" in n:
        return True
    if "dwc3" in n and "usb" in n:
        return True
    return False


def list_by_path() -> list[str]:
    """Print all by-path symlinks; return directory listing."""
    base = "/dev/v4l/by-path"
    print(f"\n{'═' * 64}\nStable paths: {base}\n{'═' * 64}")
    if not os.path.isdir(base):
        print("Directory missing — no V4L devices or not Linux.")
        return []
    names = sorted(os.listdir(base))
    if not names:
        print("Empty — plug in USB cameras and re-run.")
        return names
    usb_uvc = [n for n in names if is_usb_uvc_by_path(n)]
    for name in names:
        full = os.path.join(base, name)
        try:
            if os.path.islink(full):
                tgt = os.readlink(full)
                real = os.path.realpath(full)
                mark = ""
                if is_usb_uvc_by_path(name):
                    mark = "  <-- USB webcam (use this shape in camera_config.py)"
                elif "video-index0" in name:
                    mark = "  <-- Pi SoC / ISP / decoder (NOT a USB webcam path)"
                print(f"  {name}{mark}")
                print(f"      -> {tgt}")
                print(f"      realpath: {real}")
            else:
                print(f"  {name} (not a symlink)")
        except OSError as e:
            print(f"  {name}: {e}")
    return names


def udev_video_hints() -> None:
    print(f"\n{'═' * 64}\nudev paths (ID_PATH) for /dev/video* (USB rows show ID_USB_*)\n{'═' * 64}")
    devices = sorted(glob.glob("/dev/video*"))
    if not devices:
        print("No /dev/video* nodes.")
        return
    usb_rows = 0
    for dev in devices:
        try:
            r = subprocess.run(
                ["udevadm", "info", "-q", "property", "-n", dev],
                text=True,
                capture_output=True,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            print(f"  {dev}: udevadm: {e}")
            continue
        if r.returncode != 0:
            print(f"  {dev}: udevadm exit {r.returncode}")
            continue
        props = {}
        for line in r.stdout.splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                props[k] = v
        id_path = props.get("ID_PATH", "")
        bus_usb = props.get("ID_BUS") == "usb" or props.get("ID_USB_DRIVER")
        serial = props.get("ID_SERIAL_SHORT") or props.get("ID_SERIAL") or ""
        if bus_usb:
            usb_rows += 1
        print(f"  {dev}")
        if id_path:
            print(f"      ID_PATH={id_path}")
        if serial:
            print(f"      ID_SERIAL={serial}")
        if bus_usb:
            print("      (USB device — udev sees this node on the USB bus)")
    if usb_rows == 0:
        print("\n  No /dev/video* node reported as USB — only SoC/internal capture above.")


def print_usb_lsusb_hints(lsusb_text: str) -> None:
    print(f"\n{'═' * 64}\nWhat your USB devices are\n{'═' * 64}")
    t = lsusb_text
    if "1a86:7523" in t or "CH340" in t.upper():
        print(
            "• CH340 / QinHeng 1a86:7523 = USB–serial (UART). NOT a camera.\n"
            "  Your app’s MJPEG stack needs UVC webcams (they show up as UVC or as\n"
            "  a camera vendor in lsusb, and add xhci… by-path links under /dev/v4l/by-path/)."
        )
    if "05e3:0610" in t or "05e3:0626" in t:
        print("• Genesys Logic 05e3:… = USB hub only (not cameras).")
    if not t.strip():
        return
    print("\n(lsusb does not list any typical UVC camera here — look for classes 0e (Video) or")
    print(" vendors like Logitech, Microdia, Sonix, etc. Run:  lsusb -v 2>/dev/null | less  and search for \"Video\")")


def print_summary(
    by_path_names: list[str],
    lsusb_text: str,
    *,
    usb_video_interface_count: int,
) -> None:
    print(f"\n{'═' * 64}\nSummary\n{'═' * 64}")
    usb_symlinks = [n for n in by_path_names if is_usb_uvc_by_path(n)]
    if usb_symlinks:
        print("USB V4L capture nodes (video-index0) found — use these full paths in camera_config.py:\n")
        for n in usb_symlinks:
            print(f"  /dev/v4l/by-path/{n}")
        print(
            "\nUnplug one camera at a time and re-run this script to see which path "
            "disappears, then assign M / A / B / C."
        )
        return

    print(
        "No USB webcam V4L paths detected — but you may already have cables plugged in.\n\n"
        "That only means the Raspberry Pi OS kernel does not see any **UVC USB camera** right now.\n"
        f"On this run, USB Video class (0x0e) interfaces in sysfs: **{usb_video_interface_count}**.\n\n"
        "  • /dev/v4l/by-path/ entries like platform-…pisp / codec = Pi SoC only, not your USB plugs.\n"
        "  • If lsusb only shows hubs + CH340 (serial), those are not UVC cameras.\n\n"
        "What to do:\n"
        "  1. Confirm hardware: real **UVC** webcams (most USB “plug and play” cameras), not CSI ribbons,\n"
        "     and not CH340/UART boards mistaken for cameras.\n"
        "  2. **Four (or more) webcams on one hub**: use a **powered** hub; fix enumeration errors first\n"
        "     (see “Reading your log” above if dmesg shows -32 / -71 / unable to enumerate).\n"
        "  3. Hotplug test: `sudo dmesg -w` in one terminal, unplug/replug a camera; look for errors.\n"
        "  4. When the kernel sees UVC, this script will show sysfs Video interfaces and new\n"
        "     by-path names with **xhci-hcd** … **video-index0** — put those into camera_config.py.\n"
        "  5. **CSI cameras** need libcamera / Picamera2, not camera_stream V4L paths.\n"
    )
    print_usb_lsusb_hints(lsusb_text)


def main() -> None:
    print("USB + V4L diagnostic (run on Raspberry Pi)\n")

    sh("USB tree", "lsusb -t 2>/dev/null || true")
    lsusb_text = sh("USB list", "lsusb 2>/dev/null || true")
    sh("V4L devices (v4l2-ctl)", "v4l2-ctl --list-devices 2>/dev/null || true", ok_codes=(0, 127))

    by_path_names = list_by_path()
    udev_video_hints()
    usb_vid_count = scan_sysfs_usb_video_class()
    dmesg_blob = recent_kernel_usb_lines()
    interpret_dmesg_hub_and_uvc_vs_serial(dmesg_blob)
    print_summary(by_path_names, lsusb_text, usb_video_interface_count=usb_vid_count)


if __name__ == "__main__":
    main()

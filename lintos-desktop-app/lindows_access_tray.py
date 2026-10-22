#!/usr/bin/env python3
"""
Lindows Access — Lightweight System Tray Application
Part of the Lintos Dual-Boot Ecosystem

Features:
- Linux:
  * "Open Windows Drive" tray action.
  * Auto-detects and auto-mounts NTFS Windows partitions (via udisksctl or /mnt/windows).
  * Automatically opens Linux File Manager at /mnt/windows/Users/ (or detected user path).
- Windows:
  * "Open Linux Files" tray action.
  * Launches Windows File Explorer directly into WSL filesystem (\\wsl$\\).
  * Run Windows-to-Linux reverse downloads sync.
"""

import os
import sys
import json
import platform
import subprocess
import threading
from pathlib import Path

# Try importing PIL and pystray
try:
    from PIL import Image, ImageDraw
    import pystray
    from pystray import MenuItem as item
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False

IS_LINUX = platform.system() == "Linux"
IS_WINDOWS = platform.system() == "Windows"


def notify(title, message):
    """Sends a desktop notification if available."""
    try:
        if IS_LINUX:
            subprocess.run(["notify-send", title, message], check=False)
        elif IS_WINDOWS:
            # Fallback PowerShell notification or print
            ps_cmd = f'[reflection.assembly]::loadwithpartialname("System.Windows.Forms"); [System.Windows.Forms.MessageBox]::Show("{message}", "{title}")'
            subprocess.Popen(["powershell", "-Command", ps_cmd])
    except Exception as e:
        print(f"[{title}] {message} (Notification error: {e})")


# ==========================================
# Linux Specific Actions
# ==========================================

def get_linux_mounted_windows():
    """Checks /proc/mounts to see if a Windows partition is already mounted."""
    try:
        with open("/proc/mounts", "r") as f:
            lines = f.readlines()

        # Check common mount roots
        candidate_prefixes = [
            "/mnt/windows",
            "/media",
            "/run/media",
            "/mnt/c"
        ]

        for line in lines:
            parts = line.split()
            if len(parts) >= 3:
                dev, mount_point, fs_type = parts[0], parts[1], parts[2]
                if fs_type in ["ntfs", "fuseblk", "ntfs-3g", "vfat", "9p", "drvfs"]:
                    users_dir = Path(mount_point) / "Users"
                    if users_dir.is_dir():
                        return mount_point, str(users_dir)

        # Fallback: check candidate folders directly
        for candidate in [Path("/mnt/windows/Users"), Path("/run/media")]:
            if candidate.is_dir():
                return str(candidate.parent), str(candidate)

    except Exception as e:
        print(f"Error checking mounts: {e}")
    return None, None


def auto_mount_windows_partition():
    """Attempts to auto-mount unmounted NTFS partitions using udisksctl or mount."""
    try:
        # Check if already mounted
        mp, users_p = get_linux_mounted_windows()
        if users_p and os.path.exists(users_p):
            return mp, users_p

        # Find unmounted NTFS partitions via lsblk
        result = subprocess.run(
            ["lsblk", "-J", "-o", "NAME,FSTYPE,MOUNTPOINT,LABEL"],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode == 0 and result.stdout:
            data = json.loads(result.stdout)
            devices = data.get("blockdevices", [])

            def search_dev(dev_list):
                for d in dev_list:
                    fstype = (d.get("fstype") or "").lower()
                    label = (d.get("label") or "").lower()
                    mountpoint = d.get("mountpoint")

                    if ("ntfs" in fstype or "windows" in label or "os" in label) and not mountpoint:
                        dev_path = f"/dev/{d['name']}"
                        # Try mounting with udisksctl (user space non-root)
                        mount_res = subprocess.run(
                            ["udisksctl", "mount", "-b", dev_path],
                            capture_output=True,
                            text=True,
                            check=False
                        )
                        if mount_res.returncode == 0:
                            # Extract mount path from udisksctl output
                            # Output format: "Mounted /dev/... at /run/media/..."
                            for word in mount_res.stdout.split():
                                if word.startswith("/"):
                                    return word
                    if "children" in d:
                        res = search_dev(d["children"])
                        if res:
                            return res
                return None

            mounted_path = search_dev(devices)
            if mounted_path:
                users_path = Path(mounted_path) / "Users"
                return mounted_path, str(users_path) if users_path.exists() else mounted_path

        # Check /mnt/windows directory
        mnt_win = Path("/mnt/windows")
        if mnt_win.exists():
            subprocess.run(["pkexec", "mount", "/mnt/windows"], check=False)
            if (mnt_win / "Users").exists():
                return str(mnt_win), str(mnt_win / "Users")
            return str(mnt_win), str(mnt_win)

    except Exception as e:
        print(f"Auto-mount error: {e}")

    return None, None


def open_windows_drive_linux(icon=None, item=None):
    """Handler for 'Open Windows Drive' on Linux."""
    notify("Lindows Access", "Detecting and mounting Windows partition...")

    mount_pt, target_path = auto_mount_windows_partition()
    if not target_path:
        mount_pt, target_path = get_linux_mounted_windows()

    if target_path and os.path.exists(target_path):
        notify("Lindows Access", f"Opening Windows files at:\n{target_path}")
        subprocess.Popen(["xdg-open", target_path])
    elif os.path.exists("/mnt/windows"):
        notify("Lindows Access", "Opening /mnt/windows...")
        subprocess.Popen(["xdg-open", "/mnt/windows"])
    else:
        notify(
            "Lindows Access: Mount Needed",
            "Could not auto-mount Windows partition. Please ensure NTFS drive is mounted or check /etc/fstab."
        )


# ==========================================
# Windows Specific Actions
# ==========================================

def open_linux_files_windows(icon=None, item=None):
    """Handler for 'Open Linux Files' on Windows."""
    try:
        # Check WSL availability
        wsl_check = subprocess.run(["wsl", "-l", "-q"], capture_output=True, text=True, check=False)
        distros = [d.strip() for d in wsl_check.stdout.splitlines() if d.strip()]

        target = r"\\wsl$"
        if distros:
            primary_distro = distros[0]
            target = rf"\\wsl$\{primary_distro}\home"

        notify("Lindows Access", f"Opening WSL Linux files:\n{target}")
        subprocess.Popen(["explorer.exe", target])
    except Exception as e:
        subprocess.Popen(["explorer.exe", r"\\wsl$"])


# ==========================================
# Tray Icon Generation & Main Application
# ==========================================

def create_tray_icon():
    """Dynamically generates a high-contrast tray icon image."""
    img = Image.new("RGBA", (64, 64), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Gradient-like background circle
    draw.ellipse([(4, 4), (60, 60)], fill="#0284c7", outline="#38bdf8", width=3)

    # Sync arrows glyph
    draw.arc([(14, 14), (50, 50)], start=30, end=150, fill="#ffffff", width=4)
    draw.polygon([(46, 32), (54, 32), (50, 42)], fill="#ffffff")

    draw.arc([(14, 14), (50, 50)], start=210, end=330, fill="#ffffff", width=4)
    draw.polygon([(18, 32), (10, 32), (14, 22)], fill="#ffffff")

    return img


def quit_app(icon, item):
    icon.stop()


def run_tray_app():
    if not PYSTRAY_AVAILABLE:
        print("[Lindows Access] pystray / Pillow not installed.")
        print("Please run: pip install -r requirements.txt")
        # CLI fallback
        if IS_LINUX:
            print("Running in CLI mode: Opening Windows Drive...")
            open_windows_drive_linux()
        elif IS_WINDOWS:
            print("Running in CLI mode: Opening Linux Files (WSL)...")
            open_linux_files_windows()
        return

    icon_image = create_tray_icon()

    if IS_LINUX:
        menu_items = (
            item("📂 Open Windows Drive", open_windows_drive_linux, default=True),
            item("🔄 Refresh Mounts", lambda i, it: auto_mount_windows_partition()),
            item("✕ Exit Lindows Access", quit_app)
        )
        title = "Lindows Access (Linux)"
    elif IS_WINDOWS:
        menu_items = (
            item("🐧 Open Linux Files (WSL)", open_linux_files_windows, default=True),
            item("✕ Exit Lindows Access", quit_app)
        )
        title = "Lindows Access (Windows)"
    else:
        menu_items = (
            item("📂 Open Windows Drive", open_windows_drive_linux),
            item("🐧 Open Linux Files", open_linux_files_windows),
            item("✕ Exit", quit_app)
        )
        title = "Lindows Access"

    tray = pystray.Icon("LindowsAccess", icon_image, title, menu=pystray.Menu(*menu_items))
    print(f"✓ {title} running in system tray.")
    tray.run()


if __name__ == "__main__":
    run_tray_app()

#!/usr/bin/env python3
"""
DualSync Native Messaging Host
Bridges Chrome/Brave Extension to the local OS filesystem for syncing downloads.
"""

import sys
import json
import struct
import os
import shutil
import glob
import subprocess

VERSION = "1.2"

def get_message():
    """Read a message from Chrome via standard input (Native Messaging protocol)."""
    raw_length = sys.stdin.buffer.read(4)
    if not raw_length or len(raw_length) < 4:
        return None
    message_length = struct.unpack("@I", raw_length)[0]
    message_bytes = sys.stdin.buffer.read(message_length)
    return json.loads(message_bytes.decode("utf-8"))

def send_message(message_dict):
    """Send a message to Chrome via standard output (Native Messaging protocol)."""
    encoded = json.dumps(message_dict).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("@I", len(encoded)))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()

def get_linux_downloads_path():
    """Return the Linux user's download directory."""
    return os.path.abspath(os.path.expanduser("~/Downloads"))

def find_windows_partition_info():
    """Discover Windows NTFS partition using lsblk without triggering any passwords or mounts."""
    if sys.platform == "win32":
        return None

    try:
        out = subprocess.check_output(
            ["lsblk", "-J", "-o", "NAME,FSTYPE,LABEL,MOUNTPOINTS,PATH"],
            text=True,
            stderr=subprocess.DEVNULL
        )
        data = json.loads(out)
        for dev in data.get("blockdevices", []):
            for child in dev.get("children", []):
                fstype = (child.get("fstype") or "").lower()
                label = (child.get("label") or "").lower()
                if fstype == "ntfs" and ("windows" in label or child.get("label") == "Windows"):
                    mounts = [m for m in child.get("mountpoints", []) if m]
                    return {
                        "name": child.get("name"),
                        "path": child.get("path"),
                        "label": child.get("label"),
                        "mounted": len(mounts) > 0,
                        "mountpoint": mounts[0] if mounts else None
                    }
    except Exception:
        pass
    return None

def detect_windows_download_path():
    """Search exclusively for currently mounted Windows download directories (NO mount or password commands)."""
    if sys.platform == "win32":
        return os.path.abspath(os.path.expanduser("~/Downloads"))

    # Strictly read-only scan of mounted locations - NEVER trigger any mount or password commands
    candidates = [
        "/run/media/*/*/Users/*/Downloads",
        "/run/media/*/*/*/Users/*/Downloads",
        "/media/*/*/Users/*/Downloads",
        "/media/*/Users/*/Downloads",
        "/mnt/*/Users/*/Downloads",
        "/mnt/c/Users/*/Downloads",
        "/run/media/rithik/Windows/Users/Asus/Downloads"
    ]

    # 1. Look for user-specific Downloads folder (avoid Default / Public)
    for pattern in candidates:
        for match in glob.glob(pattern):
            if os.path.isdir(match) and not match.startswith(os.path.expanduser("~")):
                if "/Users/Default/" in match or "/Users/Public/" in match:
                    continue
                return os.path.abspath(match)

    # 2. Secondary fallback for any mounted Windows Users download directory
    for pattern in candidates:
        for match in glob.glob(pattern):
            if os.path.isdir(match) and not match.startswith(os.path.expanduser("~")):
                return os.path.abspath(match)

    return None

def handle_ping(payload):
    target_dir = payload.get("targetDir", "")
    linux_dl = get_linux_downloads_path()

    detected = detect_windows_download_path()
    part_info = find_windows_partition_info()

    # Target folder checks
    target_exists = os.path.isdir(target_dir) if target_dir else False
    target_writable = os.access(target_dir, os.W_OK) if target_exists else False

    is_same_as_linux = False
    if target_dir:
        abs_target = os.path.abspath(os.path.expanduser(target_dir))
        if abs_target == linux_dl:
            is_same_as_linux = True

    response = {
        "status": "ok",
        "version": VERSION,
        "targetExists": target_exists,
        "targetWritable": target_writable,
        "detectedPath": detected,
        "isSameAsLinux": is_same_as_linux,
        "partitionInfo": part_info
    }

    if is_same_as_linux:
        response["warning"] = "Target is set to Linux Downloads! Please set to your Windows partition."
    elif not target_exists:
        if part_info and not part_info.get("mounted"):
            response["warning"] = f"Windows drive is not mounted. Click '{part_info.get('label') or 'Windows'}' in your file manager to mount it."
        else:
            response["warning"] = "Target folder does not exist. Please mount your Windows partition."
    elif not target_writable:
        response["warning"] = "Windows partition is mounted read-only (Windows Fast Startup is locked)."

    return response

def handle_sync_file(payload):
    file_path = payload.get("filePath")
    target_dir = payload.get("targetDir")

    if not file_path or not os.path.exists(file_path):
        return {"success": False, "error": f"Source file does not exist: {file_path}"}

    if not target_dir:
        return {"success": False, "error": "Target directory is not specified."}

    abs_source = os.path.abspath(os.path.expanduser(file_path))
    abs_target = os.path.abspath(os.path.expanduser(target_dir))
    filename = os.path.basename(abs_source)
    dest_path = os.path.join(abs_target, filename)

    # 1. Guard against source and target destination being identical
    if abs_source == dest_path:
        return {
            "success": False,
            "error": (
                f"Source and target destination are the same file ({abs_source})!\n"
                "Target is currently pointing to your Linux Downloads folder instead of Windows.\n"
                "Please configure your Windows drive path in Settings."
            )
        }

    if os.path.exists(dest_path) and os.path.samefile(abs_source, dest_path):
        return {
            "success": False,
            "error": "Destination file points to the same file as source. Please select your Windows drive."
        }

    # 2. CRITICAL: Check if target folder exists before attempting to write or create directories.
    # Never run os.makedirs on an unmounted root-owned directory (/run/media/rithik/...) as that causes Permission Denied!
    if not os.path.isdir(abs_target):
        return {
            "success": False,
            "error": (
                f"Windows destination folder is not mounted or does not exist:\n{abs_target}\n\n"
                "Please mount your Windows partition first by clicking on it in your file manager (Files / Dolphin / Nautilus)."
            )
        }

    # 3. Check write permissions
    if not os.access(abs_target, os.W_OK):
        return {
            "success": False,
            "error": (
                f"Cannot write to Windows folder (Permission Denied / Read-Only):\n{abs_target}\n\n"
                "Your Windows partition is mounted in read-only mode.\n"
                "To fix this, disable Fast Startup in Windows (run 'powercfg /h off' in Administrator Command Prompt)."
            )
        }

    try:
        shutil.copy2(abs_source, dest_path)
        return {
            "success": True,
            "destPath": dest_path
        }
    except PermissionError as pe:
        return {
            "success": False,
            "error": (
                f"Permission Denied while copying to '{dest_path}': {pe}\n"
                "Ensure your Windows drive is mounted with write permissions."
            )
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc)
        }

def main():
    while True:
        try:
            msg = get_message()
            if msg is None:
                break

            action = msg.get("action")
            if action == "ping":
                resp = handle_ping(msg)
            elif action == "sync_file":
                resp = handle_sync_file(msg)
            else:
                resp = {"status": "error", "error": f"Unknown action: {action}"}

            send_message(resp)
        except Exception as exc:
            send_message({"status": "error", "error": str(exc)})
            break

if __name__ == "__main__":
    main()

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

VERSION = "1.1"

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
    """Discover Windows NTFS partition using lsblk on Linux."""
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

def try_automount_windows():
    """Attempt to mount unmounted Windows partition via udisksctl."""
    part_info = find_windows_partition_info()
    if not part_info or part_info.get("mounted"):
        return part_info

    dev_path = part_info.get("path")
    if not dev_path:
        return part_info

    try:
        res = subprocess.run(
            ["udisksctl", "mount", "-b", dev_path],
            capture_output=True,
            text=True,
            timeout=5
        )
        if res.returncode == 0:
            return find_windows_partition_info()
        else:
            stderr = res.stderr.strip()
            part_info["mount_error"] = stderr
            if "wrong fs type" in stderr or "bad superblock" in stderr or "is dirty" in stderr:
                part_info["dirty"] = True
    except Exception as e:
        part_info["mount_error"] = str(e)

    return part_info

def detect_windows_download_path():
    """Search for common dual-boot mounted Windows download directories or local Windows paths."""
    if sys.platform == "win32":
        return os.path.abspath(os.path.expanduser("~/Downloads"))

    # Linux: Try auto-mounting if unmounted
    try_automount_windows()

    candidates = [
        # Dual-boot mount locations
        "/run/media/*/*/Users/*/Downloads",
        "/run/media/*/*/*/Users/*/Downloads",
        "/media/*/*/Users/*/Downloads",
        "/mnt/*/Users/*/Downloads",
        "/mnt/c/Users/*/Downloads",
        "/run/media/rithik/Windows/Users/Asus/Downloads"
    ]
    for pattern in candidates:
        matches = glob.glob(pattern)
        for match in matches:
            # Avoid matching inside Linux home directory
            if os.path.isdir(match) and not match.startswith(os.path.expanduser("~")):
                # Avoid Default / Public accounts if a specific user exists
                if "/Users/Default/" in match or "/Users/Public/" in match:
                    continue
                return os.path.abspath(match)

    # Secondary scan if only Default/Public matched
    for pattern in candidates:
        matches = glob.glob(pattern)
        for match in matches:
            if os.path.isdir(match) and not match.startswith(os.path.expanduser("~")):
                return os.path.abspath(match)

    return None

def handle_ping(payload):
    target_dir = payload.get("targetDir", "")
    linux_dl = get_linux_downloads_path()

    detected = detect_windows_download_path()
    part_info = find_windows_partition_info()

    # Target folder checks
    target_exists = os.path.exists(target_dir) if target_dir else False
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
        response["warning"] = (
            "Target folder is set to your Linux Downloads folder instead of Windows! "
            "Please select your Windows partition path."
        )
    elif part_info and not part_info.get("mounted"):
        if part_info.get("dirty"):
            response["warning"] = (
                "Windows partition is locked because Windows Fast Startup is enabled. "
                "In Windows, disable Fast Startup (run 'powercfg /h off' in Admin CMD) or restart Windows to allow write access."
            )
        else:
            response["warning"] = f"Windows partition is not mounted. Run: udisksctl mount -b {part_info.get('path')}"
    elif target_exists and not target_writable:
        response["warning"] = (
            "Windows partition is mounted read-only. "
            "Disable Fast Startup in Windows (run 'powercfg /h off' in Admin CMD) to enable writing."
        )

    return response

def handle_sync_file(payload):
    file_path = payload.get("filePath")
    target_dir = payload.get("targetDir")

    if not file_path or not os.path.exists(file_path):
        return {"success": False, "error": f"Source file does not exist: {file_path}"}

    if not target_dir:
        return {"success": False, "error": "Target directory is not specified"}

    try:
        abs_source = os.path.abspath(os.path.expanduser(file_path))
        abs_target = os.path.abspath(os.path.expanduser(target_dir))
        filename = os.path.basename(abs_source)
        dest_path = os.path.join(abs_target, filename)

        # 1. Guard against source and target destination being identical
        if abs_source == dest_path:
            return {
                "success": False,
                "error": (
                    f"Target destination is identical to source file ({abs_source})!\n"
                    "Your target folder is configured to your Linux Downloads folder instead of your Windows drive.\n"
                    "Please set your Windows path (e.g. /run/media/rithik/Windows/Users/Asus/Downloads) in Settings."
                )
            }

        # 2. Check if destination file already exists and is the same inode
        if os.path.exists(dest_path) and os.path.samefile(abs_source, dest_path):
            return {
                "success": False,
                "error": (
                    f"Destination '{dest_path}' refers to the same file as source.\n"
                    "Please configure a valid Windows partition destination in DualSync settings."
                )
            }

        # 3. Check target directory writability
        if os.path.exists(abs_target) and not os.access(abs_target, os.W_OK):
            return {
                "success": False,
                "error": (
                    f"Target folder '{abs_target}' is read-only.\n"
                    "Your Windows partition is mounted in read-only mode (likely because Windows Fast Startup is enabled).\n"
                    "To fix: Boot into Windows and run 'powercfg /h off' in Admin Command Prompt."
                )
            }

        os.makedirs(abs_target, exist_ok=True)
        shutil.copy2(abs_source, dest_path)

        return {
            "success": True,
            "destPath": dest_path
        }
    except shutil.SameFileError:
        return {
            "success": False,
            "error": (
                "Source and destination files are identical.\n"
                "Please configure a valid Windows partition destination in DualSync settings."
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

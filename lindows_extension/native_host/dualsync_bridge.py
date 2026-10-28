#!/usr/bin/env python3
"""
DualSync Native Messaging Host
Bridges Chrome/Brave/Edge Extension to the local OS filesystem for syncing downloads
between Linux and Windows partitions in dual-boot setups.
"""

import sys
import json
import struct
import os
import shutil
import glob
import subprocess

VERSION = "1.3"
PLATFORM = "windows" if sys.platform == "win32" else "linux"

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

def get_local_downloads_path():
    """Return the current operating system's local download directory (source)."""
    return os.path.abspath(os.path.expanduser("~/Downloads"))

def auto_mount_partition(part_path):
    """
    Attempt to mount partition using udisksctl with -t ntfs first (ntfs-3g handles
    dirty flags without root password), followed by standard fallbacks.
    """
    if not part_path or PLATFORM == "windows":
        return False

    mount_commands = [
        ["udisksctl", "mount", "-b", part_path, "-t", "ntfs"],
        ["udisksctl", "mount", "-b", part_path],
        ["gio", "mount", "-d", part_path]
    ]

    for cmd in mount_commands:
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            if res.returncode == 0:
                return True
        except Exception:
            continue
    return False

def find_windows_partition_info():
    """Discover Windows NTFS partition using lsblk without requiring root permissions."""
    if PLATFORM == "windows":
        return None

    try:
        out = subprocess.check_output(
            ["lsblk", "-J", "-o", "NAME,FSTYPE,LABEL,MOUNTPOINTS,PATH"],
            text=True,
            stderr=subprocess.DEVNULL
        )
        data = json.loads(out)
        # Search prioritized for 'Windows' label and ntfs / fuseblk filesystem
        for dev in data.get("blockdevices", []):
            devices_to_check = [dev] + dev.get("children", [])
            for child in devices_to_check:
                fstype = (child.get("fstype") or "").lower()
                label = (child.get("label") or "").lower()
                if fstype in ["ntfs", "fuseblk"] and ("windows" in label or child.get("label") == "Windows"):
                    mounts = [m for m in child.get("mountpoints", []) if m]
                    return {
                        "name": child.get("name"),
                        "path": child.get("path"),
                        "label": child.get("label") or "Windows",
                        "mounted": len(mounts) > 0,
                        "mountpoint": mounts[0] if mounts else None
                    }

        # Fallback: any NTFS partition
        for dev in data.get("blockdevices", []):
            devices_to_check = [dev] + dev.get("children", [])
            for child in devices_to_check:
                fstype = (child.get("fstype") or "").lower()
                if fstype in ["ntfs", "fuseblk"]:
                    mounts = [m for m in child.get("mountpoints", []) if m]
                    return {
                        "name": child.get("name"),
                        "path": child.get("path"),
                        "label": child.get("label") or "NTFS Drive",
                        "mounted": len(mounts) > 0,
                        "mountpoint": mounts[0] if mounts else None
                    }
    except Exception:
        pass
    return None

def detect_windows_download_paths(mountpoint=None):
    """
    Search exclusively for valid Windows user download directories.
    Strictly excludes any local Linux directories.
    """
    if PLATFORM == "windows":
        return []

    found = []
    seen = set()
    patterns = []

    if mountpoint and os.path.isdir(mountpoint):
        patterns.append(os.path.join(mountpoint, "Users", "*", "Downloads"))
        patterns.append(os.path.join(mountpoint, "users", "*", "Downloads"))
        patterns.append(os.path.join(mountpoint, "Users", "*", "downloads"))

    patterns.extend([
        "/run/media/*/*/Users/*/Downloads",
        "/run/media/*/*/*/Users/*/Downloads",
        "/media/*/*/Users/*/Downloads",
        "/media/*/Users/*/Downloads",
        "/mnt/*/Users/*/Downloads",
        "/mnt/c/Users/*/Downloads"
    ])

    for pat in patterns:
        for match in glob.glob(pat):
            abs_match = os.path.abspath(match)
            if not os.path.isdir(abs_match) or abs_match in seen:
                continue
            # Strictly ensure it is NOT inside Linux home directory
            if abs_match.startswith(os.path.expanduser("~")):
                continue

            parts = abs_match.split(os.sep)
            user_idx = -1
            for idx, p in enumerate(parts):
                if p.lower() == "users":
                    user_idx = idx + 1
                    break

            if user_idx != -1 and user_idx < len(parts):
                uname = parts[user_idx]
                if uname.lower() in ["default", "default user", "public", "all users"]:
                    continue
                seen.add(abs_match)
                found.append({
                    "label": f"🪟 Windows: {uname} / Downloads",
                    "path": abs_match
                })

    return found

def detect_linux_download_paths():
    """
    When running on Windows, detect Linux download directories (WSL distros or ext4).
    Strictly excludes any local Windows directories.
    """
    if PLATFORM != "windows":
        return []

    found = []
    seen = set()

    for prefix in [r"\\wsl.localhost", r"\\wsl$"]:
        if os.path.exists(prefix):
            try:
                for distro in os.listdir(prefix):
                    distro_path = os.path.join(prefix, distro)
                    home_dir = os.path.join(distro_path, "home")
                    if os.path.isdir(home_dir):
                        for user in os.listdir(home_dir):
                            dl = os.path.join(home_dir, user, "Downloads")
                            if os.path.isdir(dl) and dl not in seen:
                                seen.add(dl)
                                found.append({
                                    "label": f"🐧 WSL: {distro} ({user}) / Downloads",
                                    "path": dl
                                })
            except Exception:
                pass

    return found

def validate_target_for_platform(target_dir):
    """
    Enforce that:
    - On Linux: Target MUST be on a Windows drive. Cannot be local Linux home/folder.
    - On Windows: Target MUST be on a Linux drive/WSL. Cannot be local Windows user/drive.
    """
    if not target_dir:
        return False, "Target directory cannot be empty."

    abs_target = os.path.abspath(os.path.expanduser(target_dir))
    local_home = os.path.abspath(os.path.expanduser("~"))

    if PLATFORM == "linux":
        # Cannot be inside Linux home or equal to Linux Downloads
        if abs_target.startswith(local_home):
            return False, "In Linux, target folder must be on your Windows partition. Local Linux folders are not allowed."
        # Must look like a mounted Windows/NTFS drive
        is_windows_path = (
            "/run/media/" in abs_target or
            "/media/" in abs_target or
            "/mnt/" in abs_target or
            "Users/" in abs_target or
            "users/" in abs_target
        )
        if not is_windows_path:
            return False, "Target folder must reside on your Windows partition (e.g. in /run/media/.../Windows/Users/...)."
        return True, None

    else: # Windows
        # Cannot be inside Windows user profile (C:\Users\...)
        if abs_target.startswith(local_home) or (len(abs_target) >= 2 and abs_target[1] == ":" and "\\Users\\" in abs_target):
            return False, "In Windows, target folder must be on your Linux partition or WSL. Local Windows folders are not allowed."
        # Must look like a WSL or Linux partition path
        is_linux_path = (
            abs_target.startswith(r"\\wsl.localhost") or
            abs_target.startswith(r"\\wsl$") or
            "ext4" in abs_target.lower() or
            "linux" in abs_target.lower()
        )
        if not is_linux_path:
            return False, "Target folder must reside on your Linux partition or WSL distro."
        return True, None

def handle_ping(payload):
    target_dir = payload.get("targetDir", "").strip()

    part_info = find_windows_partition_info()

    # If in Linux and Windows partition is not mounted, attempt auto-mount
    if PLATFORM == "linux" and part_info and not part_info.get("mounted"):
        auto_mount_partition(part_info.get("path"))
        part_info = find_windows_partition_info()

    if PLATFORM == "linux":
        detected_paths = detect_windows_download_paths(part_info.get("mountpoint") if part_info else None)
    else:
        detected_paths = detect_linux_download_paths()

    primary_detected = detected_paths[0]["path"] if detected_paths else None

    # If target_dir is empty or invalid, fallback to primary detected path
    is_valid, validation_err = validate_target_for_platform(target_dir) if target_dir else (False, "Target is unset")
    if not is_valid and primary_detected:
        target_dir = primary_detected
        is_valid, validation_err = validate_target_for_platform(target_dir)

    target_exists = os.path.isdir(target_dir) if (target_dir and is_valid) else False
    target_writable = os.access(target_dir, os.W_OK) if target_exists else False

    response = {
        "status": "ok",
        "platform": PLATFORM,
        "version": VERSION,
        "targetExists": target_exists,
        "targetWritable": target_writable,
        "targetDir": target_dir,
        "detectedPath": primary_detected,
        "detectedPaths": detected_paths,
        "partitionInfo": part_info
    }

    if not is_valid:
        response["warning"] = validation_err
    elif not target_exists:
        if PLATFORM == "linux" and part_info and not part_info.get("mounted"):
            response["warning"] = f"Windows drive is not mounted. Attempted auto-mount, or click '{part_info.get('label') or 'Windows'}' in your file manager."
        else:
            response["warning"] = f"Target folder does not exist: {target_dir}"
    elif not target_writable:
        if PLATFORM == "linux":
            response["warning"] = "Windows partition is mounted read-only (Windows Fast Startup may be locked)."
        else:
            response["warning"] = "Target folder is not writable (check permissions)."

    return response

def handle_sync_file(payload):
    file_path = payload.get("filePath")
    target_dir = payload.get("targetDir", "").strip()

    if not file_path or not os.path.exists(file_path):
        return {"success": False, "error": f"Source file does not exist: {file_path}"}

    # Validate target folder platform constraint
    is_valid, val_err = validate_target_for_platform(target_dir)
    if not is_valid:
        return {"success": False, "error": f"Configuration Error: {val_err}"}

    abs_source = os.path.abspath(os.path.expanduser(file_path))
    abs_target = os.path.abspath(os.path.expanduser(target_dir))
    filename = os.path.basename(abs_source)
    dest_path = os.path.join(abs_target, filename)

    # Guard against identical source and target
    if abs_source == dest_path:
        return {
            "success": False,
            "error": "Source and target destination are identical! Target must point to your other operating system."
        }

    # If target directory does not exist, check if auto-mount is needed (Linux)
    if not os.path.isdir(abs_target) and PLATFORM == "linux":
        part_info = find_windows_partition_info()
        if part_info and not part_info.get("mounted"):
            auto_mount_partition(part_info.get("path"))

    if not os.path.isdir(abs_target):
        return {
            "success": False,
            "error": (
                f"Destination folder does not exist or is not mounted:\n{abs_target}\n\n"
                "Please verify that the target partition is mounted."
            )
        }

    if not os.access(abs_target, os.W_OK):
        return {
            "success": False,
            "error": (
                f"Destination folder is read-only (Permission Denied):\n{abs_target}\n\n"
                "Ensure your partition is mounted with write permissions."
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
            "error": f"Permission Denied while copying to '{dest_path}': {pe}"
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc)
        }

def handle_mount_partition(payload):
    """Explicitly trigger partition mount from UI."""
    if PLATFORM != "linux":
        return {"success": False, "error": "Mount action only applicable on Linux."}

    part_info = find_windows_partition_info()
    if not part_info:
        return {"success": False, "error": "No Windows partition found."}

    if part_info.get("mounted"):
        detected_paths = detect_windows_download_paths(part_info.get("mountpoint"))
        return {
            "success": True,
            "alreadyMounted": True,
            "mountpoint": part_info.get("mountpoint"),
            "detectedPaths": detected_paths
        }

    success = auto_mount_partition(part_info.get("path"))
    part_info = find_windows_partition_info()
    detected_paths = detect_windows_download_paths(part_info.get("mountpoint") if part_info else None)

    return {
        "success": success,
        "mountpoint": part_info.get("mountpoint") if part_info else None,
        "detectedPaths": detected_paths,
        "error": None if success else "Failed to auto-mount partition."
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
            elif action == "mount_partition":
                resp = handle_mount_partition(msg)
            else:
                resp = {"status": "error", "error": f"Unknown action: {action}"}

            send_message(resp)
        except Exception as exc:
            send_message({"status": "error", "error": str(exc)})
            break

if __name__ == "__main__":
    main()

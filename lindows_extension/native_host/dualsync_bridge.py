#!/usr/bin/env python3
"""
DualSync Native Messaging Host
Bridges Chrome/Brave/Edge Extension to the local OS filesystem for syncing downloads
between Linux (Arch Linux) and Windows partitions in dual-boot setups.
"""

import sys
import json
import struct
import os
import shutil
import glob
import subprocess

VERSION = "1.4"
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
    Search exclusively for valid Windows user download directories on Linux.
    Strictly excludes local Linux directories.
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
    When running on Windows, detect Linux download directories (Arch Linux target).
    """
    if PLATFORM != "windows":
        return []

    found = []
    seen = set()

    # Arch Linux target folder
    arch_target = "/home/rithik/Downloads"
    found.append({
        "label": "🐧 Arch Linux: /home/rithik/Downloads",
        "path": arch_target
    })
    seen.add(arch_target)

    # Check for WSL distros (prioritize Arch Linux)
    for prefix in [r"\\wsl.localhost", r"\\wsl$"]:
        if os.path.exists(prefix):
            try:
                distros = sorted(os.listdir(prefix), key=lambda d: 0 if "arch" in d.lower() else 1)
                for distro in distros:
                    distro_path = os.path.join(prefix, distro)
                    home_dir = os.path.join(distro_path, "home")
                    if os.path.isdir(home_dir):
                        for user in os.listdir(home_dir):
                            dl = os.path.join(home_dir, user, "Downloads")
                            if os.path.isdir(dl) and dl not in seen:
                                seen.add(dl)
                                found.append({
                                    "label": f"🐧 WSL ({distro}): ~/{user}/Downloads",
                                    "path": dl
                                })
            except Exception:
                pass

    return found

def resolve_linux_target_on_windows(target_dir):
    """
    On Windows, resolve a Linux path (like /home/rithik/Downloads) into an accessible path:
    1. Check WSL distros (e.g. \\wsl.localhost\\Arch\\home\\rithik\\Downloads).
    2. Check mounted drive letters (e.g. D:\\home\\rithik\\Downloads, E:\\...).
    3. Direct Windows path (e.g. C:\\home\\rithik\\Downloads).
    """
    if not target_dir or PLATFORM != "windows":
        return target_dir, None

    clean = target_dir.strip()
    norm_slash = clean.replace("\\", "/")

    # If already an existing directory or UNC path
    if os.path.isdir(clean):
        return os.path.abspath(clean), None

    # If it is a Linux path starting with /home/... or home/...
    if norm_slash.startswith("/home/") or norm_slash.startswith("home/"):
        rel_home = norm_slash.lstrip("/")
        win_rel = rel_home.replace("/", "\\")

        # 1. Search WSL distros (prioritizing Arch Linux)
        for prefix in [r"\\wsl.localhost", r"\\wsl$"]:
            if os.path.exists(prefix):
                try:
                    distros = sorted(os.listdir(prefix), key=lambda d: 0 if "arch" in d.lower() else 1)
                    for distro in distros:
                        cand = os.path.join(prefix, distro, win_rel)
                        if os.path.isdir(cand):
                            return cand, None
                        # Check if parent user directory exists and create Downloads
                        user_dir = os.path.join(prefix, distro, os.path.dirname(win_rel))
                        if os.path.isdir(user_dir):
                            try:
                                os.makedirs(cand, exist_ok=True)
                                return cand, None
                            except Exception:
                                pass
                except Exception:
                    pass

        # Also probe via wsl.exe list
        try:
            out = subprocess.check_output(["wsl", "-l", "-q"], text=True, stderr=subprocess.DEVNULL)
            distros = [line.strip().replace("\x00", "") for line in out.splitlines() if line.strip()]
            distros = sorted(distros, key=lambda d: 0 if "arch" in d.lower() else 1)
            for distro in distros:
                for prefix in [r"\\wsl.localhost", r"\\wsl$"]:
                    cand = os.path.join(prefix, distro, win_rel)
                    if os.path.isdir(cand):
                        return cand, None
        except Exception:
            pass

        # 2. Check external/mounted drive letters (D:\home\rithik\Downloads, E:\..., etc.)
        for letter in ["D", "E", "F", "G", "H", "Z"]:
            cand = f"{letter}:\\{win_rel}"
            if os.path.isdir(cand):
                return cand, None

        # 3. Create C:\home\rithik\Downloads on Windows partition
        cand = os.path.abspath(clean)
        try:
            os.makedirs(cand, exist_ok=True)
            return cand, None
        except Exception:
            pass

    cand = os.path.abspath(clean)
    try:
        os.makedirs(cand, exist_ok=True)
        return cand, None
    except Exception as e:
        return cand, str(e)

def validate_target_for_platform(target_dir):
    """
    Enforce OS constraint:
    - On Linux: Target MUST be on a Windows drive. Cannot be local Linux home/folder.
    - On Windows: Target MUST be Linux destination (/home/rithik/Downloads, WSL, or ext4). Cannot be the source Windows Downloads folder.
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
        norm = target_dir.replace("\\", "/")
        # Explicitly accept Linux paths like /home/rithik/Downloads and WSL paths
        if norm.startswith("/home/") or norm.startswith("home/"):
            return True, None
        if target_dir.startswith(r"\\wsl.localhost") or target_dir.startswith(r"\\wsl$"):
            return True, None

        # Cannot be the same Windows User Downloads directory (copying onto itself)
        source_dl = os.path.abspath(os.path.expanduser("~/Downloads"))
        if abs_target == source_dl:
            return False, "Target cannot be your Windows Downloads folder. Target must be your Linux folder (e.g. /home/rithik/Downloads)."
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
        primary_detected = detected_paths[0]["path"] if detected_paths else None
    else:
        detected_paths = detect_linux_download_paths()
        primary_detected = detected_paths[0]["path"] if detected_paths else "/home/rithik/Downloads"

    # If target_dir is empty or invalid, fallback to primary detected path
    is_valid, validation_err = validate_target_for_platform(target_dir) if target_dir else (False, "Target is unset")
    if not is_valid and primary_detected:
        target_dir = primary_detected
        is_valid, validation_err = validate_target_for_platform(target_dir)

    if PLATFORM == "windows":
        resolved_target, _ = resolve_linux_target_on_windows(target_dir)
        target_exists = os.path.isdir(resolved_target) if resolved_target else False
        target_writable = os.access(resolved_target, os.W_OK) if target_exists else True
    else:
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
        elif PLATFORM == "linux":
            response["warning"] = f"Target folder does not exist: {target_dir}"
    elif not target_writable:
        if PLATFORM == "linux":
            response["warning"] = "Windows partition is mounted read-only (Windows Fast Startup may be locked)."

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

    # Resolve target on Windows
    if PLATFORM == "windows":
        abs_target, res_err = resolve_linux_target_on_windows(target_dir)
        if not os.path.isdir(abs_target):
            try:
                os.makedirs(abs_target, exist_ok=True)
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Could not create target directory '{abs_target}': {e}"
                }
    else:
        abs_target = os.path.abspath(os.path.expanduser(target_dir))
        # If target directory does not exist, check if auto-mount is needed (Linux)
        if not os.path.isdir(abs_target):
            part_info = find_windows_partition_info()
            if part_info and not part_info.get("mounted"):
                auto_mount_partition(part_info.get("path"))

    filename = os.path.basename(abs_source)
    dest_path = os.path.join(abs_target, filename)

    # Guard against identical source and target
    if abs_source == dest_path:
        return {
            "success": False,
            "error": "Source and target destination are identical! Target must point to your other operating system."
        }

    if not os.path.isdir(abs_target):
        return {
            "success": False,
            "error": (
                f"Destination folder does not exist or is not mounted:\n{abs_target}\n\n"
                "Please verify that the target partition is accessible."
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

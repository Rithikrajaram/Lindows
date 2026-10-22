#!/usr/bin/env python3
"""
DualSync Native Messaging Host Bridge for Linux
Receives file sync requests from the DualSync Chrome Extension
and copies files to the mounted Windows partition / directory.
"""

import sys
import os
import json
import struct
import shutil
import logging
from pathlib import Path

# Prevent bytecode / __pycache__ generation
sys.dont_write_bytecode = True

# Setup logging (Writing only to file/stderr, NEVER to stdout!)
LOG_DIR = Path.home() / ".config" / "dualsync"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "bridge.log"

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logging.info("DualSync Bridge started.")


def send_message(message_dict):
    """
    Encodes and writes a JSON message to stdout following
    the Chrome Native Messaging protocol (4-byte length prefix).
    """
    try:
        encoded_json = json.dumps(message_dict).encode("utf-8")
        # Pack length as 32-bit native unsigned integer
        sys.stdout.buffer.write(struct.pack("@I", len(encoded_json)))
        sys.stdout.buffer.write(encoded_json)
        sys.stdout.buffer.flush()
        logging.info(f"Sent response: {message_dict.get('status') or message_dict.get('success')}")
    except Exception as e:
        logging.error(f"Failed to send message: {e}")


def read_message():
    """
    Reads a single message from stdin following
    the Chrome Native Messaging protocol.
    """
    try:
        # Read the 4-byte length prefix
        raw_length = sys.stdin.buffer.read(4)
        if len(raw_length) == 0:
            return None  # Parent closed pipe

        message_length = struct.unpack("@I", raw_length)[0]
        # Read the message bytes
        raw_message = sys.stdin.buffer.read(message_length)
        if len(raw_message) < message_length:
            logging.error("Incomplete message read from stdin")
            return None

        decoded = json.loads(raw_message.decode("utf-8"))
        logging.info(f"Received message: {decoded.get('action')}")
        return decoded
    except Exception as e:
        logging.error(f"Error reading message from stdin: {e}")
        return None


def is_mount_read_only(target_path):
    """
    Checks /proc/mounts to determine if the target path's mount point is read-only.
    Crucial for dual-boot NTFS partitions locked by Windows Fast Startup or BitLocker.
    """
    try:
        abs_path = os.path.abspath(target_path)
        with open("/proc/mounts", "r") as f:
            mounts = [line.split() for line in f.readlines()]

        # Find longest matching mount point
        best_mount = None
        for m in mounts:
            if len(m) >= 4:
                mount_point = m[1]
                if abs_path.startswith(mount_point):
                    if best_mount is None or len(mount_point) > len(best_mount[1]):
                        best_mount = m

        if best_mount:
            options = best_mount[3].split(",")
            if "ro" in options:
                return True, best_mount[1]
        return False, None
    except Exception as e:
        logging.warning(f"Could not check mount options: {e}")
        return False, None


def detect_windows_downloads():
    """Attempts to auto-detect the user's Windows Downloads directory."""
    candidate_roots = [
        Path("/run/media") / Path.home().name,
        Path("/media") / Path.home().name,
        Path("/mnt"),
    ]
    for root in candidate_roots:
        if root.exists():
            for win_mount in root.glob("*"):
                users_dir = win_mount / "Users"
                if users_dir.is_dir():
                    for user_folder in users_dir.glob("*"):
                        if user_folder.name.lower() not in ["default", "public", "all users", "default user"]:
                            dl = user_folder / "Downloads"
                            if dl.is_dir():
                                return str(dl)
    return None


def ensure_writable(dir_path):
    """Ensures directory has write permission, attempting chmod if needed."""
    try:
        if os.path.exists(dir_path):
            if not os.access(dir_path, os.W_OK):
                # Try adding user write permission
                mode = os.stat(dir_path).st_mode
                os.chmod(dir_path, mode | 0o200)
            return os.access(dir_path, os.W_OK)
    except Exception as e:
        logging.warning(f"Failed to check/adjust write permission on {dir_path}: {e}")
    return os.access(dir_path, os.W_OK) if os.path.exists(dir_path) else False


def handle_ping(data):
    """Handles ping connection check from extension popup."""
    target_dir = os.path.expanduser(data.get("targetDir", ""))
    target_exists = os.path.isdir(target_dir) if target_dir else False
    target_writable = ensure_writable(target_dir) if target_exists else False

    is_ro, mount_point = is_mount_read_only(target_dir) if target_dir else (False, None)
    detected_path = detect_windows_downloads()

    return {
        "status": "ok",
        "version": "1.0.0",
        "targetExists": target_exists,
        "targetWritable": target_writable,
        "readOnlyMount": is_ro,
        "mountPoint": mount_point,
        "detectedPath": detected_path,
    }


def handle_sync_file(data):
    """Handles file copy request from background script."""
    src_path = os.path.expanduser(data.get("filePath", ""))
    target_dir = os.path.expanduser(data.get("targetDir", ""))

    if not src_path or not os.path.exists(src_path):
        err = f"Source file does not exist: '{src_path}'"
        logging.error(err)
        return {"success": False, "error": err}

    detected = detect_windows_downloads()

    # Automatically sanitize target_dir if placeholder, invalid, or missing
    if not target_dir or "/mnt/windows" in target_dir or "Users/Default" in target_dir or not os.path.exists(target_dir):
        if detected:
            logging.info(f"Target '{target_dir}' is invalid/placeholder. Auto-redirecting to detected: '{detected}'")
            target_dir = detected
        elif not target_dir:
            err = "Target Windows directory is not specified and auto-detection found no folder."
            logging.error(err)
            return {"success": False, "error": err}

    # Verify mount status
    is_ro, mount_pt = is_mount_read_only(target_dir)
    if is_ro:
        err = (
            f"Windows drive mounted at '{mount_pt}' is READ-ONLY. "
            "Please turn off 'Fast Startup' in Windows or remount drive with write permissions."
        )
        logging.error(err)
        return {"success": False, "error": err}

    # Ensure target directory exists and is writable
    try:
        os.makedirs(target_dir, exist_ok=True)
        ensure_writable(target_dir)
    except PermissionError:
        if detected and detected != target_dir:
            logging.info(f"Target '{target_dir}' had PermissionError, falling back to detected: '{detected}'")
            target_dir = detected
            try:
                os.makedirs(target_dir, exist_ok=True)
                ensure_writable(target_dir)
            except Exception as e2:
                err = f"Failed to access detected path '{target_dir}': {e2}"
                logging.error(err)
                return {"success": False, "error": err}
        else:
            err = (
                f"Permission denied creating target directory '{target_dir}'. "
                "Please check that your target directory path is on a mounted drive (e.g. /run/media/...)."
            )
            logging.error(err)
            return {"success": False, "error": err}
        return {"success": False, "error": err}
    except Exception as e:
        err = f"Error creating target directory '{target_dir}': {str(e)}"
        logging.error(err)
        return {"success": False, "error": err}

    # Build destination file path
    file_name = os.path.basename(src_path)
    dest_path = os.path.join(target_dir, file_name)

    # Perform safe copy
    try:
        logging.info(f"Copying '{src_path}' to '{dest_path}'...")
        shutil.copy2(src_path, dest_path)

        # Verify copy
        if os.path.exists(dest_path):
            src_size = os.path.getsize(src_path)
            dest_size = os.path.getsize(dest_path)
            if src_size == dest_size:
                logging.info(f"Successfully copied {src_size} bytes to '{dest_path}'")
                return {
                    "success": True,
                    "message": "File synced successfully to Windows directory.",
                    "destPath": dest_path,
                    "fileName": file_name,
                    "bytes": dest_size,
                }
            else:
                return {
                    "success": False,
                    "error": f"File size mismatch: source={src_size}, dest={dest_size}",
                }
        else:
            return {"success": False, "error": "Destination file not found after copy."}
    except Exception as e:
        err = f"Failed to copy file: {str(e)}"
        logging.error(err)
        return {"success": False, "error": err}


def main():
    while True:
        message = read_message()
        if message is None:
            # End of stream (Chrome closed the connection)
            break

        action = message.get("action")
        response = None

        if action == "ping":
            response = handle_ping(message)
        elif action == "sync_file":
            response = handle_sync_file(message)
        else:
            response = {"success": False, "error": f"Unknown action: '{action}'"}

        send_message(response)


if __name__ == "__main__":
    main()

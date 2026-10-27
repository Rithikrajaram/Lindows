#!/usr/bin/env python3
"""
DualSync Native Messaging Host
Bridges Chrome Extension to the local OS filesystem for syncing downloads.
"""

import sys
import json
import struct
import os
import shutil
import glob

VERSION = "1.0"

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

def detect_windows_download_path():
    """Search for common dual-boot mounted Windows download directories or local Windows paths."""
    candidates = [
        # Linux dual-boot mount locations
        "/run/media/*/*/Users/*/Downloads",
        "/media/*/*/Users/*/Downloads",
        "/mnt/*/Users/*/Downloads",
        "/mnt/c/Users/*/Downloads",
        "/run/media/rithik/Windows/Users/Asus/Downloads",
        # Windows local locations
        os.path.expanduser("~/Downloads")
    ]
    for pattern in candidates:
        matches = glob.glob(pattern)
        for match in matches:
            if os.path.isdir(match):
                return os.path.abspath(match)
    return None

def handle_ping(payload):
    target_dir = payload.get("targetDir", "")
    target_exists = os.path.exists(target_dir) if target_dir else False
    target_writable = os.access(target_dir, os.W_OK) if target_exists else False

    detected = detect_windows_download_path()

    return {
        "status": "ok",
        "version": VERSION,
        "targetExists": target_exists,
        "targetWritable": target_writable,
        "detectedPath": detected or target_dir
    }

def handle_sync_file(payload):
    file_path = payload.get("filePath")
    target_dir = payload.get("targetDir")

    if not file_path or not os.path.exists(file_path):
        return {"success": False, "error": f"Source file does not exist: {file_path}"}

    if not target_dir:
        return {"success": False, "error": "Target directory is not specified"}

    try:
        os.makedirs(target_dir, exist_ok=True)
        filename = os.path.basename(file_path)
        dest_path = os.path.join(target_dir, filename)

        shutil.copy2(file_path, dest_path)

        return {
            "success": True,
            "destPath": dest_path
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

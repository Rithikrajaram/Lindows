#!/usr/bin/env python3
"""
DualSync Reverse Watcher for Windows OS
Monitors the Windows 'Downloads' folder and automatically copies newly completed
downloaded files to the shared Linux partition, NTFS shared drive, or WSL directory.
"""

import os
import sys
import time
import shutil
import logging
from pathlib import Path

# Prevent bytecode / __pycache__ generation
sys.dont_write_bytecode = True

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("windows_watcher.log", encoding="utf-8")
    ]
)

# Configuration Defaults (Can be overridden via command line or environment)
USER_HOME = Path.home()
DEFAULT_WATCH_DIR = str(USER_HOME / "Downloads")

# Example target paths:
# 1. A shared NTFS partition mounted at D:\DualSyncShared or E:\Shared
# 2. WSL2 Linux user folder: r"\\wsl$\Ubuntu\home\username\Downloads"
DEFAULT_TARGET_DIR = os.environ.get("DUALSYNC_TARGET_DIR", r"D:\DualSyncShared")

# Incomplete download file extensions to ignore until finished
INCOMPLETE_EXTENSIONS = {".crdownload", ".part", ".tmp", ".download", ".opdownload"}

# Track already synced files (path -> (size, mtime))
synced_cache = {}


def is_file_ready(file_path, wait_seconds=1.5, retries=5):
    """
    Checks if a file has finished downloading and is unlocked.
    Browser downloads frequently lock files during writing.
    """
    for _ in range(retries):
        try:
            if not os.path.exists(file_path):
                return False
            # Check if extension is incomplete
            ext = os.path.splitext(file_path)[1].lower()
            if ext in INCOMPLETE_EXTENSIONS:
                return False

            size1 = os.path.getsize(file_path)
            time.sleep(wait_seconds)
            size2 = os.path.getsize(file_path)

            # File size should be positive and stable
            if size1 == size2 and size1 > 0:
                # Test opening file exclusively to check if download completed
                with open(file_path, "rb"):
                    return True
        except (IOError, PermissionError):
            time.sleep(wait_seconds)
    return False


def copy_to_target(file_path, target_dir):
    """Copies a completed file from Windows to the designated target directory."""
    try:
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        file_name = os.path.basename(file_path)
        dest_path = os.path.join(target_dir, file_name)

        # Check if already synced with same size and mtime
        mtime = os.path.getmtime(file_path)
        size = os.path.getsize(file_path)
        cache_key = f"{file_path}_{size}_{mtime}"

        if cache_key in synced_cache:
            return

        logging.info(f"Syncing: '{file_name}' -> '{dest_path}'")
        shutil.copy2(file_path, dest_path)
        synced_cache[cache_key] = True
        logging.info(f"✓ Successfully synced '{file_name}' ({size} bytes)")
    except Exception as e:
        logging.error(f"Failed to copy '{file_path}': {e}")


def run_with_watchdog(watch_dir, target_dir):
    """Watchdog event-driven implementation."""
    from watchdog.observers import Observer  # type: ignore
    from watchdog.events import FileSystemEventHandler  # type: ignore

    class DownloadHandler(FileSystemEventHandler):
        def on_created(self, event):
            if not event.is_directory:
                self.process(event.src_path)

        def on_modified(self, event):
            if not event.is_directory:
                self.process(event.src_path)

        def on_moved(self, event):
            # Chrome renames file from file.crdownload -> file.zip when complete
            if not event.is_directory:
                self.process(event.dest_path)

        def process(self, path):
            if is_file_ready(path):
                copy_to_target(path, target_dir)

    logging.info(f"[Watchdog Mode] Monitoring '{watch_dir}'...")
    logging.info(f"Target sync directory: '{target_dir}'")

    event_handler = DownloadHandler()
    observer = Observer()
    observer.schedule(event_handler, path=watch_dir, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


def run_polling(watch_dir, target_dir):
    """Fallback polling implementation if watchdog is not installed."""
    logging.info(f"[Polling Mode] Monitoring '{watch_dir}' (interval: 3s)...")
    logging.info(f"Target sync directory: '{target_dir}'")

    seen_files = {}

    # Initialize existing files to avoid copying old history on first launch
    for entry in os.scandir(watch_dir):
        if entry.is_file():
            try:
                seen_files[entry.path] = (entry.stat().st_size, entry.stat().st_mtime)
            except Exception:
                pass

    while True:
        try:
            time.sleep(3)
            for entry in os.scandir(watch_dir):
                if not entry.is_file():
                    continue

                path = entry.path
                ext = os.path.splitext(path)[1].lower()
                if ext in INCOMPLETE_EXTENSIONS:
                    continue

                try:
                    stat = entry.stat()
                    current_sig = (stat.st_size, stat.st_mtime)

                    if path not in seen_files or seen_files[path] != current_sig:
                        if is_file_ready(path):
                            copy_to_target(path, target_dir)
                            seen_files[path] = current_sig
                except Exception as ex:
                    logging.debug(f"Scan error for {path}: {ex}")

        except KeyboardInterrupt:
            logging.info("Polling stopped by user.")
            break


def main():
    watch_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_WATCH_DIR
    target_dir = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_TARGET_DIR

    logging.info("=" * 50)
    logging.info(" DualSync Windows Reverse Watcher")
    logging.info("=" * 50)

    if not os.path.exists(watch_dir):
        logging.error(f"Watch directory does not exist: '{watch_dir}'")
        sys.exit(1)

    try:
        import watchdog  # type: ignore
        run_with_watchdog(watch_dir, target_dir)
    except ImportError:
        logging.warning("watchdog library not installed ('pip install watchdog'). Falling back to polling mode.")
        run_polling(watch_dir, target_dir)


if __name__ == "__main__":
    main()

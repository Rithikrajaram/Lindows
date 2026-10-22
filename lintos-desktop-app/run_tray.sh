#!/usr/bin/env bash
# Launcher for Lindows Access System Tray App on Linux
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! python3 -c "import pystray, PIL" 2>/dev/null; then
    echo "Installing missing dependencies (pystray, pillow)..."
    pip install -r requirements.txt
fi

python3 lindows_access_tray.py

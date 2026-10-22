#!/usr/bin/env bash
# DualSync Native Messaging Host Installer for Linux
# Supports Google Chrome, Chromium, Brave, Microsoft Edge, and Vivaldi

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST_NAME="com.dualsync.bridge"
PYTHON_SCRIPT="$SCRIPT_DIR/dualsync_bridge.py"
MANIFEST_FILE="$SCRIPT_DIR/$HOST_NAME.json"

# ANSI Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}====================================================${NC}"
echo -e "${CYAN}      DualSync Native Messaging Host Installer      ${NC}"
echo -e "${CYAN}====================================================${NC}"

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR] python3 could not be found. Please install Python 3 first.${NC}"
    exit 1
fi

# Ensure Python script is executable
chmod +x "$PYTHON_SCRIPT"
echo -e "${GREEN}[✓] Made python bridge executable: ${PYTHON_SCRIPT}${NC}"

# Get Extension ID
EXTENSION_ID="$1"

if [ -z "$EXTENSION_ID" ]; then
    echo ""
    echo -e "${YELLOW}How to find your Extension ID:${NC}"
    echo "  1. Open Chrome/Chromium and go to: chrome://extensions"
    echo "  2. Enable 'Developer mode' (top-right toggle)"
    echo "  3. Click 'Load unpacked' and select: $SCRIPT_DIR"
    echo "  4. Copy the 32-character ID shown on the 'DualSync' card"
    echo ""
    read -p "Enter your Chrome Extension ID (or press Enter to configure later): " EXTENSION_ID
fi

if [ -z "$EXTENSION_ID" ]; then
    echo -e "${YELLOW}[!] No Extension ID provided. Using placeholder 'REPLACE_WITH_YOUR_EXTENSION_ID'.${NC}"
    EXTENSION_ID="REPLACE_WITH_YOUR_EXTENSION_ID"
fi

# Generate manifest JSON with absolute path and extension ID
cat <<EOF > "$MANIFEST_FILE"
{
  "name": "$HOST_NAME",
  "description": "DualSync Native Messaging Bridge for Windows/Linux file sync",
  "path": "$PYTHON_SCRIPT",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://$EXTENSION_ID/"
  ]
}
EOF

echo -e "${GREEN}[✓] Generated manifest file: ${MANIFEST_FILE}${NC}"

# Target directories for all popular Chromium browsers on Linux
TARGET_DIRS=(
    "$HOME/.config/google-chrome/NativeMessagingHosts"
    "$HOME/.config/google-chrome-beta/NativeMessagingHosts"
    "$HOME/.config/google-chrome-unstable/NativeMessagingHosts"
    "$HOME/.config/chromium/NativeMessagingHosts"
    "$HOME/.config/BraveSoftware/Brave-Browser/NativeMessagingHosts"
    "$HOME/.config/microsoft-edge/NativeMessagingHosts"
    "$HOME/.config/microsoft-edge-dev/NativeMessagingHosts"
    "$HOME/.config/vivaldi/NativeMessagingHosts"
)

INSTALLED_COUNT=0

for DIR in "${TARGET_DIRS[@]}"; do
    # Create directory if parent browser config exists
    PARENT_DIR="$(dirname "$DIR")"
    if [ -d "$PARENT_DIR" ]; then
        mkdir -p "$DIR"
        cp "$MANIFEST_FILE" "$DIR/$HOST_NAME.json"
        echo -e "${GREEN}[✓] Installed to: $DIR/$HOST_NAME.json${NC}"
        INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
    fi
done

# If no browser folders existed yet, default to standard google-chrome path
if [ $INSTALLED_COUNT -eq 0 ]; then
    DEFAULT_DIR="$HOME/.config/google-chrome/NativeMessagingHosts"
    mkdir -p "$DEFAULT_DIR"
    cp "$MANIFEST_FILE" "$DEFAULT_DIR/$HOST_NAME.json"
    echo -e "${GREEN}[✓] Default installed to: $DEFAULT_DIR/$HOST_NAME.json${NC}"
fi

echo ""
echo -e "${CYAN}====================================================${NC}"
echo -e "${GREEN}✓ Native Messaging Host installation complete!${NC}"
if [ "$EXTENSION_ID" == "REPLACE_WITH_YOUR_EXTENSION_ID" ]; then
    echo -e "${YELLOW}REMINDER: Once you load the extension in Chrome, run:${NC}"
    echo -e "${CYAN}  ./install_host.sh <YOUR_ACTUAL_EXTENSION_ID>${NC}"
else
    echo -e "${GREEN}Registered with Extension ID: ${EXTENSION_ID}${NC}"
fi
echo -e "${CYAN}====================================================${NC}"

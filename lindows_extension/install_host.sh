#!/usr/bin/env bash
# DualSync Native Messaging Host Installer for Linux (Google Chrome, Brave, Chromium, Edge, Vivaldi, Opera)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST_DIR="$SCRIPT_DIR/native_host"
HOST_SCRIPT="$HOST_DIR/dualsync_bridge.py"

if [ ! -f "$HOST_SCRIPT" ]; then
    echo "❌ Error: Could not find $HOST_SCRIPT"
    exit 1
fi

chmod +x "$HOST_SCRIPT"

FIXED_ID="dlgiaeggibjmhegpeakmgjckgpildjdb"
LEGACY_ID="obkmhhkdmmbpjaiadpikanbjnfcoehah"

echo "=== DualSync Native Host Installer (Linux) ==="
echo ""

if [ -n "$1" ]; then
    EXT_ID="$1"
    echo "Using provided Extension ID: $EXT_ID"
else
    EXT_ID="$FIXED_ID"
    echo "Using automated DualSync Extension ID: $EXT_ID"
fi

if [ "$EXT_ID" = "$FIXED_ID" ]; then
    ALLOWED_ORIGINS="\"chrome-extension://$FIXED_ID/\",
    \"chrome-extension://$LEGACY_ID/\""
else
    ALLOWED_ORIGINS="\"chrome-extension://$EXT_ID/\",
    \"chrome-extension://$FIXED_ID/\",
    \"chrome-extension://$LEGACY_ID/\""
fi

MANIFEST_CONTENT=$(cat <<EOF
{
  "name": "com.dualsync.bridge",
  "description": "DualSync Native Messaging Host for Linux <-> Windows Sync",
  "path": "$HOST_SCRIPT",
  "type": "stdio",
  "allowed_origins": [
    $ALLOWED_ORIGINS
  ]
}
EOF
)

# Standard target directories for Native Messaging in Linux browsers
TARGET_DIRS=(
    "$HOME/.config/google-chrome/NativeMessagingHosts"
    "$HOME/.config/chromium/NativeMessagingHosts"
    "$HOME/.config/BraveSoftware/Brave-Browser/NativeMessagingHosts"
    "$HOME/.config/microsoft-edge/NativeMessagingHosts"
    "$HOME/.config/vivaldi/NativeMessagingHosts"
    "$HOME/.config/opera/NativeMessagingHosts"
)

INSTALLED_COUNT=0
for DIR in "${TARGET_DIRS[@]}"; do
    PARENT_DIR="$(dirname "$DIR")"
    if [ -d "$PARENT_DIR" ]; then
        mkdir -p "$DIR"
        echo "$MANIFEST_CONTENT" > "$DIR/com.dualsync.bridge.json"
        echo "✅ Installed host manifest to: $DIR/com.dualsync.bridge.json"
        INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
    fi
done

if [ $INSTALLED_COUNT -eq 0 ]; then
    DEFAULT_DIR="$HOME/.config/google-chrome/NativeMessagingHosts"
    mkdir -p "$DEFAULT_DIR"
    echo "$MANIFEST_CONTENT" > "$DEFAULT_DIR/com.dualsync.bridge.json"
    echo "✅ Created default directory and installed manifest: $DEFAULT_DIR/com.dualsync.bridge.json"
fi

echo ""
echo "🎉 Native host registered successfully!"
echo "Extension ID: $EXT_ID"
echo "Now reload your extension in chrome://extensions and click 'Test Bridge' in the DualSync popup."

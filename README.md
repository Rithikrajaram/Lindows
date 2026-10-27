# 🔄 DualSync - Chrome Extension & Native Sync Bridge

[![Manifest V3](https://img.shields.io/badge/Manifest-V3-brightgreen.svg)](https://developer.chrome.com/docs/extensions/mv3/intro/)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows%20Dual--Boot-blue.svg)](#)

DualSync tracks completed downloads in your browser and automatically synchronizes them between Linux and Windows partitions in dual-boot setups.

---

## 💡 How It Works & Why Local Files Are Required

Web browsers enforce strict security sandboxing on extensions: **a Chrome extension is not permitted to directly read or write files to arbitrary partitions on your hard drive**.

To sync files across partitions, DualSync uses **Chrome Native Messaging**:
1. **Chrome Extension (Browser)**: Monitors download completion and prompts you to sync.
2. **Native Messaging Host (Local Python Script)**: Runs locally on your operating system and physically copies files to your designated Windows partition/folder.

Without registering the local Native Host, Chrome displays **"Bridge Not Connected / Specified native messaging host not found"**.

---

## 📁 Project Structure

```
dualsync/
├── .gitignore             # Git ignore file
├── README.md              # Project documentation
└── lindows_extension/     # Everything in one extension folder
    ├── manifest.json      # Extension manifest
    ├── background.js      # Service Worker (downloads listener)
    ├── popup.html         # Settings & bridge test UI
    ├── popup.css          # Glassmorphic UI styling
    ├── popup.js           # Settings controller & native bridge caller
    ├── install_host.bat   # Windows Native Host installer
    ├── install_host.sh    # Linux Native Host installer
    ├── icons/             # Icons (16, 48, 128)
    └── native_host/       # Local Python Host Bridge
        ├── dualsync_bridge.py      # Python script handling native messaging & file copy
        ├── dualsync_bridge.bat     # Windows execution wrapper
        └── com.dualsync.bridge.json# Host manifest
```

---

## 🚀 Setup Instructions

### Step 1: Load Extension in Browser
1. Open Google Chrome or Brave (`chrome://extensions` or `brave://extensions`).
2. Enable **Developer mode** (toggle in the top-right corner).
3. Click **Load unpacked** and select the `lindows_extension` folder.
4. Copy the **Extension ID** (e.g. `obkmhhkdmmbpjaiadpikanbjnfcoehah`).

### Step 2: Install Local Native Host Bridge

#### On Windows:
Double-click `install_host.bat` inside `lindows_extension`, then press Enter.

#### On Linux:
```bash
cd lindows_extension
chmod +x install_host.sh
./install_host.sh
```

### Step 3: Test the Connection
1. Click the DualSync icon in your browser toolbar to open the popup.
2. Click **"Test Bridge"**.
3. The badge in the top right will turn green: **"Connected"**.

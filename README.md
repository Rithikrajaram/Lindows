# 🔄 DualSync - Linux & Windows Auto-Sync Chrome Extension

[![Manifest V3](https://img.shields.io/badge/Manifest-V3-brightgreen.svg)](https://developer.chrome.com/docs/extensions/mv3/intro/)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows-blue.svg)](#)
[![Python](https://img.shields.io/badge/Python-3.8%2B-yellow.svg)](https://www.python.org/)

**DualSync** solves a classic dual-boot annoyance: you download a driver, installer, game patch, or document while running Linux, and later when you boot into Windows, you have to download it all over again.

With **DualSync**, any file you download in Chrome on Linux is automatically mirrored (or prompted with `[Yes/No]`) to your mounted Windows partition (e.g., `/mnt/windows/Users/<Name>/Downloads`). An optional Windows watcher script is also provided for reverse synchronization!

---

## 🏗️ Architecture Overview

```mermaid
graph TD
    A[Browser: Chrome / Brave / Edge] -->|File Download Completed| B[DualSync Extension - Manifest V3]
    B -->|Check settings & prompt user| C{Auto-sync or Prompt?}
    C -->|User clicks Yes| D[chrome.runtime.sendNativeMessage]
    D -->|stdio 4-byte binary + JSON| E[dualsync_bridge.py: Native Host]
    E -->|Check mount & write permissions| F[/mnt/windows/... Windows Partition]
    F -->|shutil.copy2 file| G[Windows Downloads Folder]
    E -->|JSON Response| D
    D -->|Desktop Notification| A
```

---

## 📁 Project Structure

```
dualsync/
├── manifest.json              # Chrome Extension Manifest V3
├── background.js             # Service Worker (downloads listener & native messaging)
├── popup.html                # Modern Dark-mode Settings UI
├── popup.css                 # Glassmorphic UI styles
├── popup.js                  # Settings controller & bridge tester
├── icons/                    # High-res extension icons (16, 48, 128)
│   ├── icon-16.png
│   ├── icon-48.png
│   └── icon-128.png
├── dualsync_bridge.py        # Linux Python Native Messaging Host
├── com.dualsync.bridge.json  # Native Messaging Host Manifest
├── install_host.sh           # 1-Click Linux installer for Chrome/Brave/Edge
├── windows_watcher.py        # Windows reverse sync background daemon
├── run_watcher.bat           # Windows 1-click startup script
├── requirements.txt          # Python dependencies for Windows watcher
└── README.md                 # Setup & User Guide
```

---

## 🚀 Step-by-Step Installation

### Step 1: Load the Chrome Extension

1. Open **Google Chrome** (or Chromium / Brave / Edge / Vivaldi).
2. Navigate to: `chrome://extensions`
3. Toggle on **Developer mode** (top right corner).
4. Click **Load unpacked** (top left).
5. Select the folder: `/home/rithik/dualsync`
6. Look at the **DualSync** card that appears and **copy your Extension ID** (a 32-character lowercase string, for example: `abcdefghijklmnopabcdefghijklmnop`).

---

### Step 2: Install the Linux Native Messaging Host

Open your Linux terminal inside the `dualsync` folder and run the installer script:

```bash
cd /home/rithik/dualsync
./install_host.sh <YOUR_EXTENSION_ID>
```

> **Example:**
> `./install_host.sh abcdefghijklmnopabcdefghijklmnop`

This automatically:
- Marks `dualsync_bridge.py` as executable (`chmod +x`).
- Configures `com.dualsync.bridge.json` with the absolute path and your extension ID.
- Installs the manifest to Chrome, Chromium, Brave, and Edge directories.

---

### Step 3: Configure Target Windows Drive

1. Click the **DualSync extension icon** in your browser toolbar to open the popup.
2. In the **Target Windows Download Folder** field, enter your Windows partition's mount path.
   - Example 1 (Standard Dual Boot): `/mnt/windows/Users/YourName/Downloads`
   - Example 2 (GNOME Disks Auto-mount): `/media/rithik/OS/Users/rithik/Downloads`
   - Example 3 (WSL2): `/mnt/c/Users/YourName/Downloads`
3. Click **"Test Bridge"** to verify communication:
   - Green pill (`Connected`) means Python bridge is communicating properly.
4. Click **"Save Settings"**.

---

### Step 4: Test Download Sync

1. Download any test file in Chrome (e.g., an image or PDF).
2. When the download finishes, a system notification will pop up:
   > **DualSync: Download Completed**  
   > *Sync "sample.pdf" to Windows Drive?*  
   > `[✓ Yes, Sync to Windows]` `[✕ No, Skip]`
3. Click **"Yes, Sync to Windows"**.
4. You will see a confirmation notification with the destination path!

---

## 🪟 Step 5 (Bonus): Windows to Linux Reverse Sync

If you download files while on Windows and want them copied back to Linux:

1. In Windows, ensure your Linux shared partition or target directory is accessible (e.g. `D:\DualSyncShared` or WSL path `\\wsl$\Ubuntu\home\rithik\Downloads`).
2. Open PowerShell or Command Prompt inside this folder on Windows.
3. Install watchdog:
   ```cmd
   pip install -r requirements.txt
   ```
4. Run the watcher:
   ```cmd
   python windows_watcher.py "%USERPROFILE%\Downloads" "D:\DualSyncShared"
   ```
   Or double-click `run_watcher.bat`.

---

## ⚠️ Important Dual-Boot Tips (Troubleshooting)

### 1. Windows "Fast Startup" Must Be Disabled
Windows 10/11 uses **Fast Startup**, which puts NTFS drives into a hibernated, read-only state. When Linux mounts the drive, it is forced to read-only (`ro`), causing copy operations to fail.
- **Fix**: In Windows, open **Control Panel** &rarr; **Power Options** &rarr; **Choose what the power buttons do** &rarr; click **Change settings that are currently unavailable** &rarr; uncheck **Turn on fast startup** &rarr; Save changes.

### 2. Auto-Mounting Windows Partition at Linux Boot
To automatically mount your Windows partition on Linux boot with write permissions, add an entry to `/etc/fstab` or use the Ubuntu **Disks** utility:
```
UUID=YOUR_NTFS_UUID /mnt/windows ntfs-3g defaults,uid=1000,gid=1000,umask=022 0 0
```

### 3. Check Bridge Logs
If any issue occurs, check the native bridge log:
```bash
cat ~/.config/dualsync/bridge.log
```

---

## 🇮🇳 தமிழ் சுருக்கம் (Tamil Quick Reference)

1. **Chrome Extensions** பக்கத்திற்கு போ (`chrome://extensions`).
2. **Developer mode** ஆன் பண்ணி, **Load Unpacked** கொடுத்து `/home/rithik/dualsync` ஃபோல்டரை தேர்ந்தெடு.
3. வந்திருக்கும் **Extension ID**-ஐ காப்பி செய்.
4. டெர்மினலில் `./install_host.sh <EXTENSION_ID>` என இயக்கி Native Host-ஐ இன்ஸ்டால் செய்.
5. எக்ஸ்டென்ஷன் Popup-ல் உன் விண்டோஸ் Download பாத் (எ.கா: `/mnt/windows/Users/YourName/Downloads`) கொடுத்து **Test Bridge** கொடுத்து உறுதி செய்!

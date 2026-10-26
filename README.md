# 🔄 DualSync - Chrome Extension (lintos-extension)

[![Manifest V3](https://img.shields.io/badge/Manifest-V3-brightgreen.svg)](https://developer.chrome.com/docs/extensions/mv3/intro/)
[![Platform](https://img.shields.io/badge/Platform-Chrome%20%7C%20Edge%20%7C%20Brave-blue.svg)](#)

DualSync is a Chrome Extension designed to track completed downloads and coordinate synchronization between Linux and Windows partitions in dual-boot setups.

---

## 📁 Project Structure

```
dualsync/
└── lintos-extension/
    ├── manifest.json   # Chrome Extension Manifest V3
    ├── background.js   # Service Worker (downloads listener & sync logic)
    ├── popup.html      # Dark-mode Settings & Status UI
    ├── popup.css       # Glassmorphic UI styles
    ├── popup.js        # Settings controller
    └── icons/          # Extension icons (16, 48, 128)
        ├── icon-16.png
        ├── icon-48.png
        └── icon-128.png
```

---

## 🚀 How to Install / Load Unpacked Extension

1. Open **Google Chrome** (or Chromium, Brave, Microsoft Edge, Vivaldi).
2. Navigate to `chrome://extensions`.
3. Enable **Developer mode** using the toggle switch in the top-right corner.
4. Click **Load unpacked** in the top-left corner.
5. Select the `lintos-extension` directory:
   ```
   /home/rithik/dualsync/lintos-extension
   ```
6. The **DualSync** extension will now be active in your browser.

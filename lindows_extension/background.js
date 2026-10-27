// DualSync Service Worker (Manifest V3)
// Listens for completed downloads and delegates syncing to Native Messaging Host

const NATIVE_HOST_NAME = "com.dualsync.bridge";

// Helper to extract filename from full path
function getBaseName(filePath) {
  if (!filePath) return "file";
  const parts = filePath.split(/[/\\]/);
  return parts[parts.length - 1] || "file";
}

// Persistent storage helper for pending sync items
async function savePendingSync(id, item) {
  try {
    const data = await chrome.storage.local.get("pendingSyncQueue");
    const queue = data.pendingSyncQueue || {};
    queue[id] = item;
    await chrome.storage.local.set({ pendingSyncQueue: queue });
  } catch (err) {
    console.error("[DualSync] Error saving pending sync:", err);
  }
}

async function getPendingSync(id) {
  try {
    const data = await chrome.storage.local.get("pendingSyncQueue");
    return (data.pendingSyncQueue || {})[id] || null;
  } catch (err) {
    console.error("[DualSync] Error getting pending sync:", err);
    return null;
  }
}

async function removePendingSync(id) {
  try {
    const data = await chrome.storage.local.get("pendingSyncQueue");
    const queue = data.pendingSyncQueue || {};
    delete queue[id];
    await chrome.storage.local.set({ pendingSyncQueue: queue });
  } catch (err) {
    console.error("[DualSync] Error removing pending sync:", err);
  }
}

// Listen for download state changes
chrome.downloads.onChanged.addListener(async (delta) => {
  // Only proceed when a download transitions to 'complete'
  if (!delta.state || delta.state.current !== "complete") {
    return;
  }

  try {
    // Retry search up to 5 times (total ~1 second) in case Chrome is renaming the .crdownload file
    let downloadItem = null;
    for (let attempt = 0; attempt < 5; attempt++) {
      const items = await chrome.downloads.search({ id: delta.id });
      if (items && items[0] && items[0].filename) {
        downloadItem = items[0];
        break;
      }
      await new Promise((resolve) => setTimeout(resolve, 200));
    }

    if (!downloadItem || !downloadItem.filename) {
      console.warn("[DualSync] Download finished but file path unavailable for id:", delta.id);
      return;
    }

    const filePath = downloadItem.filename;
    const baseName = getBaseName(filePath);

    // Retrieve user settings
    chrome.storage.local.get(
      {
        autoSync: true,
        promptBeforeSync: true,
        targetFolder: "/run/media/rithik/Windows/Users/Asus/Downloads"
      },
      (config) => {
        if (!config.targetFolder) {
          config.targetFolder = "/run/media/rithik/Windows/Users/Asus/Downloads";
          chrome.storage.local.set({ targetFolder: config.targetFolder });
        }

        if (!config.autoSync) {
          console.log("[DualSync] Auto-sync is currently disabled. Skipping:", filePath);
          return;
        }

        if (config.promptBeforeSync) {
          askUserToSync(delta.id, filePath, baseName, config.targetFolder);
        } else {
          // Direct auto-sync without prompt
          executeFileSync(filePath, config.targetFolder, baseName);
        }
      }
    );
  } catch (error) {
    console.error("[DualSync] Error processing completed download:", error);
  }
});

// Prompt user via interactive popup window AND Chrome notification
async function askUserToSync(downloadId, filePath, fileName, targetFolder) {
  const syncId = String(downloadId);
  const notificationId = `dualsync_prompt_${syncId}_${Date.now()}`;

  const syncData = {
    downloadId: syncId,
    notificationId: notificationId,
    filePath,
    fileName,
    targetFolder,
    timestamp: Date.now()
  };

  // Persist pending item in chrome.storage.local (survives Service Worker termination)
  await savePendingSync(syncId, syncData);
  await savePendingSync(notificationId, syncData);

  // 1. Open interactive popup window
  openPromptWindow(syncId, filePath, fileName, targetFolder);

  // 2. Also send system notification
  sendSystemNotification(notificationId, fileName, targetFolder);
}

// Open clean standalone popup window
function openPromptWindow(downloadId, filePath, fileName, targetFolder) {
  const width = 480;
  const height = 340;

  const promptUrl = chrome.runtime.getURL(
    `prompt.html?id=${encodeURIComponent(downloadId)}&file=${encodeURIComponent(filePath)}&name=${encodeURIComponent(fileName)}&target=${encodeURIComponent(targetFolder)}`
  );

  chrome.windows.getCurrent((currentWin) => {
    let left = undefined;
    let top = undefined;

    if (currentWin && currentWin.left !== undefined && currentWin.width !== undefined) {
      left = Math.round(currentWin.left + (currentWin.width - width) / 2);
      top = Math.round(currentWin.top + (currentWin.height - height) / 2);
      // Ensure on-screen
      if (left < 0) left = 100;
      if (top < 0) top = 100;
    }

    chrome.windows.create(
      {
        url: promptUrl,
        type: "popup",
        width: width,
        height: height,
        left: left,
        top: top,
        focused: true
      },
      (popupWin) => {
        if (chrome.runtime.lastError) {
          console.warn("[DualSync] Could not open popup window:", chrome.runtime.lastError.message);
        } else {
          console.log("[DualSync] Prompt window opened successfully:", popupWin?.id);
        }
      }
    );
  });
}

// Display Chrome Notification with buttons
function sendSystemNotification(notificationId, fileName, targetFolder) {
  const iconUrl = chrome.runtime.getURL("icons/icon-128.png");

  const optionsWithButtons = {
    type: "basic",
    iconUrl: iconUrl,
    title: "DualSync: Download Completed",
    message: `Sync "${fileName}" to Windows Drive?\nTarget: ${targetFolder}`,
    buttons: [
      { title: "✓ Yes, Sync to Windows" },
      { title: "✕ No, Skip" }
    ],
    priority: 2,
    requireInteraction: true
  };

  chrome.notifications.create(notificationId, optionsWithButtons, () => {
    if (chrome.runtime.lastError) {
      console.warn("[DualSync] Rich notification failed, trying basic:", chrome.runtime.lastError.message);
      // Fallback for notification daemons that reject custom buttons (e.g. some Linux distros)
      chrome.notifications.create(notificationId, {
        type: "basic",
        iconUrl: iconUrl,
        title: "DualSync: Download Completed",
        message: `Click to sync "${fileName}" to Windows Drive (${targetFolder})`,
        priority: 2
      });
    }
  });
}

// Handle notification button clicks (Yes / No)
chrome.notifications.onButtonClicked.addListener(async (notificationId, buttonIndex) => {
  const syncData = await getPendingSync(notificationId);
  if (!syncData) return;

  await removePendingSync(notificationId);
  if (syncData.downloadId) {
    await removePendingSync(syncData.downloadId);
  }
  chrome.notifications.clear(notificationId);

  if (buttonIndex === 0) {
    console.log("[DualSync] User accepted sync via notification for:", syncData.filePath);
    executeFileSync(syncData.filePath, syncData.targetFolder, syncData.fileName);
  } else {
    console.log("[DualSync] User dismissed sync via notification for:", syncData.filePath);
  }
});

// Handle clicking directly on the notification body
chrome.notifications.onClicked.addListener(async (notificationId) => {
  const syncData = await getPendingSync(notificationId);
  if (!syncData) return;

  chrome.notifications.clear(notificationId);
  // Bring up popup window
  openPromptWindow(syncData.downloadId, syncData.filePath, syncData.fileName, syncData.targetFolder);
});

// Handle notification close/dismiss
chrome.notifications.onClosed.addListener(async (notificationId) => {
  await removePendingSync(notificationId);
});

// Listen for runtime messages from popup window or settings UI
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "confirm_sync") {
    const { downloadId, filePath, targetFolder, fileName } = message;

    if (downloadId) {
      removePendingSync(downloadId);
    }

    executeFileSync(filePath, targetFolder, fileName, (result) => {
      sendResponse(result);
    });
    return true; // Keep message channel open for async response
  }

  if (message.action === "cancel_sync") {
    const { downloadId } = message;
    if (downloadId) {
      removePendingSync(downloadId);
    }
    sendResponse({ success: true });
    return false;
  }

  if (message.action === "test_prompt") {
    // Simulate a download completion prompt for user testing
    const sampleDownloadId = `test_${Date.now()}`;
    const sampleFile = "Sample_Downloaded_Document.pdf";
    const samplePath = `C:\\Users\\Default\\Downloads\\${sampleFile}`;

    chrome.storage.local.get({ targetFolder: "/run/media/rithik/Windows/Users/Asus/Downloads" }, (config) => {
      askUserToSync(sampleDownloadId, samplePath, sampleFile, config.targetFolder);
      sendResponse({ success: true });
    });
    return true;
  }
});

// Execute the file sync using Chrome Native Messaging Host
function executeFileSync(filePath, targetFolder, fileName, callback = null) {
  const payload = {
    action: "sync_file",
    filePath: filePath,
    targetDir: targetFolder
  };

  console.log("[DualSync] Sending payload to native host:", payload);

  chrome.runtime.sendNativeMessage(NATIVE_HOST_NAME, payload, (response) => {
    const iconUrl = chrome.runtime.getURL("icons/icon-128.png");

    if (chrome.runtime.lastError) {
      const errorMsg = chrome.runtime.lastError.message;
      console.error("[DualSync] Native messaging error:", errorMsg);

      chrome.notifications.create(`dualsync_err_${Date.now()}`, {
        type: "basic",
        iconUrl: iconUrl,
        title: "DualSync: Sync Failed",
        message: `Native host error: ${errorMsg}\nPlease check that the native host is installed.`
      });

      if (callback) callback({ success: false, error: errorMsg });
      return;
    }

    if (response && response.success) {
      console.log("[DualSync] Sync successful:", response);

      // Increment stats in chrome.storage.local
      chrome.storage.local.get({ syncedCount: 0 }, (items) => {
        chrome.storage.local.set({
          syncedCount: (items.syncedCount || 0) + 1,
          lastSynced: fileName
        });
      });

      // Show success notification
      chrome.notifications.create(`dualsync_success_${Date.now()}`, {
        type: "basic",
        iconUrl: iconUrl,
        title: "DualSync: File Synced!",
        message: `"${fileName}" copied successfully to:\n${response.destPath || targetFolder}`
      });

      if (callback) callback({ success: true, destPath: response.destPath });
    } else {
      const failReason = response?.error || "Unknown host error";
      console.error("[DualSync] Bridge returned error:", failReason);

      chrome.notifications.create(`dualsync_fail_${Date.now()}`, {
        type: "basic",
        iconUrl: iconUrl,
        title: "DualSync: Copy Failed",
        message: `Failed to copy "${fileName}":\n${failReason}`
      });

      if (callback) callback({ success: false, error: failReason });
    }
  });
}

// Lifecycle event
chrome.runtime.onInstalled.addListener(() => {
  console.log("[DualSync] Extension installed/updated successfully.");
});

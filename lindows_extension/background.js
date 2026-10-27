// DualSync Service Worker (Manifest V3)
// Listens for completed downloads and delegates syncing to Linux Native Messaging Host

const NATIVE_HOST_NAME = "com.dualsync.bridge";

// Store pending notifications and their corresponding file paths
const pendingSyncQueue = new Map();

// Helper to extract filename from full path
function getBaseName(filePath) {
  if (!filePath) return "file";
  const parts = filePath.split(/[/\\]/);
  return parts[parts.length - 1] || "file";
}

// Listen for download state changes
chrome.downloads.onChanged.addListener(async (delta) => {
  // Only proceed when a download has transitioned to 'complete'
  if (!delta.state || delta.state.current !== "complete") {
    return;
  }

  try {
    const [downloadItem] = await chrome.downloads.search({ id: delta.id });
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
        // Set fallback targetFolder only if completely empty
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

// Prompt user via Chrome Notification with Yes/No action buttons
function askUserToSync(downloadId, filePath, fileName, targetFolder) {
  const notificationId = `dualsync_prompt_${downloadId}_${Date.now()}`;

  // Store in pending queue for notification button listener
  pendingSyncQueue.set(notificationId, {
    filePath,
    fileName,
    targetFolder
  });

  chrome.notifications.create(notificationId, {
    type: "basic",
    iconUrl: "icons/icon-128.png",
    title: "DualSync: Download Completed",
    message: `Sync "${fileName}" to Windows Drive?\nTarget: ${targetFolder}`,
    buttons: [
      { title: "✓ Yes, Sync to Windows" },
      { title: "✕ No, Skip" }
    ],
    priority: 2,
    requireInteraction: true
  });
}

// Handle notification button clicks (Yes / No)
chrome.notifications.onButtonClicked.addListener((notificationId, buttonIndex) => {
  if (!pendingSyncQueue.has(notificationId)) {
    return;
  }

  const { filePath, fileName, targetFolder } = pendingSyncQueue.get(notificationId);
  pendingSyncQueue.delete(notificationId);

  // Clear prompt notification
  chrome.notifications.clear(notificationId);

  if (buttonIndex === 0) {
    // User selected "Yes"
    console.log("[DualSync] User accepted sync for:", filePath);
    executeFileSync(filePath, targetFolder, fileName);
  } else {
    // User selected "No"
    console.log("[DualSync] User dismissed sync for:", filePath);
  }
});

// Handle notification close/dismiss
chrome.notifications.onClosed.addListener((notificationId) => {
  if (pendingSyncQueue.has(notificationId)) {
    pendingSyncQueue.delete(notificationId);
  }
});

// Execute the file sync using Chrome Native Messaging Host
function executeFileSync(filePath, targetFolder, fileName) {
  const payload = {
    action: "sync_file",
    filePath: filePath,
    targetDir: targetFolder
  };

  console.log("[DualSync] Sending payload to native host:", payload);

  chrome.runtime.sendNativeMessage(NATIVE_HOST_NAME, payload, (response) => {
    if (chrome.runtime.lastError) {
      const errorMsg = chrome.runtime.lastError.message;
      console.error("[DualSync] Native messaging communication error:", errorMsg);

      chrome.notifications.create(`dualsync_err_${Date.now()}`, {
        type: "basic",
        iconUrl: "icons/icon-128.png",
        title: "DualSync: Sync Failed",
        message: `Native host error: ${errorMsg}\nPlease check that the native host is installed.`
      });
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
        iconUrl: "icons/icon-128.png",
        title: "DualSync: File Synced!",
        message: `"${fileName}" copied successfully to:\n${response.destPath || targetFolder}`
      });
    } else {
      const failReason = response?.error || "Unknown host error";
      console.error("[DualSync] Bridge returned error:", failReason);

      chrome.notifications.create(`dualsync_fail_${Date.now()}`, {
        type: "basic",
        iconUrl: "icons/icon-128.png",
        title: "DualSync: Copy Failed",
        message: `Failed to copy "${fileName}":\n${failReason}`
      });
    }
  });
}

// Lifecycle event
chrome.runtime.onInstalled.addListener(() => {
  console.log("[DualSync] Extension installed/updated successfully.");
});

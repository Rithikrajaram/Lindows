// DualSync Interactive Download Prompt Controller

const IS_WINDOWS = typeof navigator !== "undefined" && (navigator.platform?.includes("Win") || navigator.userAgent?.includes("Windows"));
const DEFAULT_TARGET = IS_WINDOWS ? "C:\\Users\\Default\\Downloads" : "/run/media/rithik/Windows/Users/Asus/Downloads";

// DOM Elements
const fileNameEl = document.getElementById("file-name");
const fileSourceEl = document.getElementById("file-source");
const targetFolderDisplay = document.getElementById("target-folder-display");
const rememberChoiceEl = document.getElementById("remember-choice");
const syncBtn = document.getElementById("sync-btn");
const skipBtn = document.getElementById("skip-btn");
const syncBtnText = document.getElementById("sync-btn-text");
const syncBtnIcon = document.getElementById("sync-btn-icon");
const promptFeedback = document.getElementById("prompt-feedback");
const feedbackTitle = document.getElementById("feedback-title");
const feedbackMessage = document.getElementById("feedback-message");

// Parse URL Parameters
const urlParams = new URLSearchParams(window.location.search);
const downloadId = urlParams.get("id");
let filePath = urlParams.get("file");
let fileName = urlParams.get("name");
let targetFolder = urlParams.get("target");

function getBaseName(path) {
  if (!path) return "Unknown File";
  const parts = path.split(/[/\\]/);
  return parts[parts.length - 1] || "File";
}

document.addEventListener("DOMContentLoaded", async () => {
  // Try retrieving pending sync info from storage if not fully in URL
  if (!filePath && downloadId) {
    try {
      const stored = await chrome.storage.local.get("pendingSyncQueue");
      const queue = stored.pendingSyncQueue || {};
      const pendingItem = queue[downloadId];
      if (pendingItem) {
        filePath = pendingItem.filePath;
        fileName = pendingItem.fileName;
        targetFolder = pendingItem.targetFolder;
      }
    } catch (e) {
      console.warn("Storage lookup error:", e);
    }
  }

  // Load configured targetFolder fallback
  if (!targetFolder) {
    const config = await chrome.storage.local.get({ targetFolder: DEFAULT_TARGET });
    targetFolder = config.targetFolder || DEFAULT_TARGET;
  }

  // Fallback filename extraction
  if (!fileName && filePath) {
    fileName = getBaseName(filePath);
  } else if (!fileName) {
    fileName = "Downloaded File";
  }

  // Populate UI
  fileNameEl.textContent = fileName;
  fileSourceEl.textContent = filePath ? `Source: ${filePath}` : "Source: Browser Downloads";
  targetFolderDisplay.textContent = targetFolder;

  // Auto focus the Sync button
  syncBtn.focus();
});

// Sync Button Click
syncBtn.addEventListener("click", () => {
  handleSync();
});

// Skip Button Click
skipBtn.addEventListener("click", () => {
  handleSkip();
});

// Keyboard shortcuts: Enter to sync, Escape to skip
document.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    handleSync();
  } else if (e.key === "Escape") {
    e.preventDefault();
    handleSkip();
  }
});

async function handleSync() {
  syncBtn.disabled = true;
  skipBtn.disabled = true;
  syncBtnText.textContent = "Syncing...";
  syncBtnIcon.innerHTML = `
    <svg class="spinning" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
      <path d="M21 12a9 9 0 1 1-6.219-8.56"></path>
    </svg>
  `;

  // Update prompt preference if checked
  if (rememberChoiceEl.checked) {
    await chrome.storage.local.set({ promptBeforeSync: false });
  }

  // Send message to background script to perform sync
  chrome.runtime.sendMessage(
    {
      action: "confirm_sync",
      downloadId: downloadId,
      filePath: filePath,
      targetFolder: targetFolder,
      fileName: fileName
    },
    (response) => {
      if (chrome.runtime.lastError) {
        showStatus("error", "Communication Error", chrome.runtime.lastError.message);
        syncBtn.disabled = false;
        skipBtn.disabled = false;
        syncBtnText.textContent = "Retry Sync";
        return;
      }

      if (response && response.success) {
        showStatus("success", "Sync Complete!", `"${fileName}" copied to Windows.`);
        syncBtnText.textContent = "✓ Synced!";
        setTimeout(() => {
          window.close();
        }, 1200);
      } else {
        const errorText = response?.error || "Native Bridge failed to copy file.";
        showStatus("error", "Sync Failed", errorText);
        syncBtn.disabled = false;
        skipBtn.disabled = false;
        syncBtnText.textContent = "Retry Sync";
      }
    }
  );
}

function handleSkip() {
  if (downloadId) {
    chrome.runtime.sendMessage({
      action: "cancel_sync",
      downloadId: downloadId
    });
  }
  window.close();
}

function showStatus(type, title, message) {
  promptFeedback.className = `feedback-card ${type}`;
  feedbackTitle.textContent = title;
  feedbackMessage.textContent = message;
  promptFeedback.classList.remove("hidden");
}

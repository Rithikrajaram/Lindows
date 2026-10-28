// DualSync Interactive Download Prompt Controller
// Linux (Arch Linux) <-> Windows Partition Sync

const isWindowsOS = typeof navigator !== "undefined" && (
  navigator.platform?.includes("Win") ||
  navigator.userAgent?.includes("Windows")
);

const DEFAULT_TARGET = isWindowsOS
  ? "/home/rithik/Downloads"
  : "/run/media/rithik/Windows/Users/Asus/Downloads";

// DOM Elements
const promptSubtitle = document.getElementById("prompt-subtitle");
const promptQuestionText = document.getElementById("prompt-question-text");
const fileNameEl = document.getElementById("file-name");
const fileSourceEl = document.getElementById("file-source");
const targetLabelEl = document.getElementById("target-label");
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

function validateTargetForPlatform(target, isWin) {
  if (!target || !target.trim()) return { valid: false, reason: "Target destination is not set." };
  const clean = target.trim();

  if (!isWin) {
    // On Linux: Target MUST be Windows
    if (clean.startsWith("/home/") || clean === "/root" || clean.startsWith("/tmp")) {
      return {
        valid: false,
        reason: "In Linux, target folder must be on your Windows drive. Local Linux folders are not allowed."
      };
    }
    const isWindows = (
      clean.includes("/Windows") ||
      clean.includes("/windows") ||
      clean.includes("/Users/") ||
      clean.includes("/users/") ||
      clean.startsWith("/run/media/") ||
      clean.startsWith("/media/") ||
      clean.startsWith("/mnt/")
    );
    if (!isWindows) {
      return {
        valid: false,
        reason: "In Linux, target must point to your Windows partition."
      };
    }
    return { valid: true };
  } else {
    // On Windows: Target MUST be Linux (/home/rithik/Downloads, WSL, or external drive)
    if (clean.toLowerCase().includes("\\users\\asus\\downloads") || clean.toLowerCase().includes("/users/asus/downloads")) {
      return {
        valid: false,
        reason: "Target cannot be your Windows Downloads folder. Target must be your Linux folder (e.g. /home/rithik/Downloads)."
      };
    }
    return { valid: true };
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  // Update UI text according to current OS
  if (isWindowsOS) {
    if (promptSubtitle) promptSubtitle.textContent = "Windows → Linux Drive Sync";
    if (promptQuestionText) promptQuestionText.textContent = "Sync this downloaded file to your Arch Linux folder?";
    if (targetLabelEl) targetLabelEl.textContent = "Linux Target Destination (Arch Linux):";
    if (syncBtnText) syncBtnText.textContent = "Sync to Linux (Enter)";
  } else {
    if (promptSubtitle) promptSubtitle.textContent = "Linux → Windows Drive Sync";
    if (promptQuestionText) promptQuestionText.textContent = "Sync this downloaded file to your Windows drive?";
    if (targetLabelEl) targetLabelEl.textContent = "Windows Target Destination (NTFS):";
    if (syncBtnText) syncBtnText.textContent = "Sync to Windows (Enter)";
  }

  // Retrieve pending sync data from storage if needed
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

  // Load configured targetFolder fallback & sanitize
  const config = await chrome.storage.local.get({ targetFolder: DEFAULT_TARGET });
  if (!targetFolder || !validateTargetForPlatform(targetFolder, isWindowsOS).valid || targetFolder.includes("Ubuntu")) {
    targetFolder = config.targetFolder || DEFAULT_TARGET;
    if (!validateTargetForPlatform(targetFolder, isWindowsOS).valid || targetFolder.includes("Ubuntu")) {
      targetFolder = DEFAULT_TARGET;
      chrome.storage.local.set({ targetFolder: DEFAULT_TARGET });
    }
  }

  // Filename fallback
  if (!fileName && filePath) {
    fileName = getBaseName(filePath);
  } else if (!fileName) {
    fileName = "Downloaded File";
  }

  // Populate UI
  fileNameEl.textContent = fileName;
  fileSourceEl.textContent = filePath ? `Source: ${filePath}` : "Source: Browser Downloads";
  targetFolderDisplay.textContent = targetFolder;

  // Strict constraint validation
  const validation = validateTargetForPlatform(targetFolder, isWindowsOS);
  if (!validation.valid) {
    targetFolderDisplay.innerHTML = `<span style="color:#f87171;font-weight:600;">⚠️ Invalid Target Folder</span><br><span style="font-size:11px;color:#94a3b8;">${targetFolder}</span>`;
    syncBtn.disabled = true;
    syncBtnText.textContent = isWindowsOS ? "Configure Linux Drive in Settings" : "Configure Windows Drive in Settings";
    showStatus(
      "error",
      isWindowsOS ? "Linux Partition Not Selected" : "Windows Partition Not Selected",
      validation.reason
    );
  } else {
    syncBtn.focus();
  }
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
  if (e.key === "Enter" && !syncBtn.disabled) {
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

  // Send message to background service worker
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
        const destOS = isWindowsOS ? "Arch Linux" : "Windows";
        showStatus("success", "Sync Complete!", `"${fileName}" copied to ${destOS}.`);
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

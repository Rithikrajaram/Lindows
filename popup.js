// DualSync Popup Controller

const NATIVE_HOST_NAME = "com.dualsync.bridge";

// DOM Elements
const autoSyncToggle = document.getElementById("auto-sync-toggle");
const promptToggle = document.getElementById("prompt-toggle");
const targetFolderInput = document.getElementById("target-folder");
const saveBtn = document.getElementById("save-btn");
const testBridgeBtn = document.getElementById("test-bridge-btn");
const bridgeStatusPill = document.getElementById("bridge-status-pill");
const bridgeStatusText = document.getElementById("bridge-status-text");
const feedbackCard = document.getElementById("feedback-card");
const feedbackTitle = document.getElementById("feedback-title");
const feedbackMessage = document.getElementById("feedback-message");
const statSyncedCount = document.getElementById("stat-synced-count");
const statLastSynced = document.getElementById("stat-last-synced");
const chips = document.querySelectorAll(".chip");
const viewGuideLink = document.getElementById("view-guide-link");

// Default configuration
const DEFAULT_CONFIG = {
  autoSync: true,
  promptBeforeSync: true,
  targetFolder: "/run/media/rithik/Windows/Users/Asus/Downloads",
  syncedCount: 0,
  lastSynced: "Never"
};

// Initialize
document.addEventListener("DOMContentLoaded", async () => {
  await loadSettings();
  await checkBridgeStatus(false);
});

// Load settings from chrome.storage.local
async function loadSettings() {
  chrome.storage.local.get(DEFAULT_CONFIG, (items) => {
    // Auto-migrate placeholder path
    if (!items.targetFolder || items.targetFolder.includes("/mnt/windows") || items.targetFolder.includes("Default")) {
      items.targetFolder = DEFAULT_CONFIG.targetFolder;
      chrome.storage.local.set({ targetFolder: items.targetFolder });
    }

    autoSyncToggle.checked = items.autoSync;
    promptToggle.checked = items.promptBeforeSync;
    targetFolderInput.value = items.targetFolder;
    statSyncedCount.textContent = items.syncedCount || 0;
    statLastSynced.textContent = items.lastSynced || "Never";
  });
}

// Preset chips click
chips.forEach((chip) => {
  chip.addEventListener("click", () => {
    const path = chip.getAttribute("data-path");
    if (path) {
      targetFolderInput.value = path;
      showFeedback("info", "Preset selected", `Target set to: ${path}`);
    }
  });
});

// Save settings handler
saveBtn.addEventListener("click", () => {
  const settings = {
    autoSync: autoSyncToggle.checked,
    promptBeforeSync: promptToggle.checked,
    targetFolder: targetFolderInput.value.trim() || DEFAULT_CONFIG.targetFolder
  };

  chrome.storage.local.set(settings, () => {
    showFeedback("success", "Settings Saved", "Your DualSync preferences have been updated.");
    // Notify background script of update
    chrome.runtime.sendMessage({ action: "settings_updated", settings });
  });
});

// Auto-save toggle changes immediately
autoSyncToggle.addEventListener("change", () => {
  chrome.storage.local.set({ autoSync: autoSyncToggle.checked });
});

promptToggle.addEventListener("change", () => {
  chrome.storage.local.set({ promptBeforeSync: promptToggle.checked });
});

// Test Bridge Connection
testBridgeBtn.addEventListener("click", async () => {
  await checkBridgeStatus(true);
});

// Bridge status verification via chrome.runtime.sendNativeMessage
async function checkBridgeStatus(interactive = false) {
  setBridgePill("checking", "Checking...");

  const targetDir = targetFolderInput.value.trim() || DEFAULT_CONFIG.targetFolder;

  try {
    chrome.runtime.sendNativeMessage(
      NATIVE_HOST_NAME,
      { action: "ping", targetDir: targetDir },
      (response) => {
        if (chrome.runtime.lastError) {
          const errMsg = chrome.runtime.lastError.message || "Host not responding";
          setBridgePill("disconnected", "Offline");
          if (interactive) {
            showFeedback(
              "error",
              "Bridge Not Connected",
              `${errMsg}. Did you run './install_host.sh' in the extension directory?`
            );
          }
          return;
        }

        if (response && response.status === "ok") {
          setBridgePill("connected", "Connected");

          // Auto-update if previous target was placeholder or not found
          if (response.detectedPath && (targetFolderInput.value.includes("/mnt/windows") || !response.targetExists)) {
            targetFolderInput.value = response.detectedPath;
            chrome.storage.local.set({ targetFolder: response.detectedPath });
          }

          if (interactive) {
            let detail = `Python Bridge v${response.version || "1.0"} active.`;
            if (response.targetExists && response.targetWritable) {
              detail += ` Windows folder verified & writable!`;
            } else if (response.detectedPath) {
              detail += ` Detected active Windows path: ${response.detectedPath}`;
            } else {
              detail += ` Note: Folder will be created or requires mount.`;
            }
            showFeedback("success", "Native Bridge Connected!", detail);
          }
        } else {
          setBridgePill("disconnected", "Error");
          if (interactive) {
            showFeedback(
              "error",
              "Bridge Returned Error",
              response?.error || "Unknown response from Python bridge script."
            );
          }
        }
      }
    );
  } catch (err) {
    setBridgePill("disconnected", "Offline");
    if (interactive) {
      showFeedback("error", "Native Host Exception", err.message);
    }
  }
}

function setBridgePill(status, text) {
  bridgeStatusPill.className = "status-pill";
  if (status === "connected") {
    bridgeStatusPill.classList.add("status-connected");
  } else if (status === "disconnected") {
    bridgeStatusPill.classList.add("status-disconnected");
  } else {
    bridgeStatusPill.classList.add("status-unknown");
  }
  bridgeStatusText.textContent = text;
}

function showFeedback(type, title, msg) {
  feedbackCard.className = `feedback-card ${type}`;
  feedbackTitle.textContent = title;
  feedbackMessage.textContent = msg;
  feedbackCard.classList.remove("hidden");

  // Auto hide after 5 seconds if success
  if (type === "success" || type === "info") {
    setTimeout(() => {
      feedbackCard.classList.add("hidden");
    }, 5000);
  }
}

// Help / Guide link click
viewGuideLink.addEventListener("click", (e) => {
  e.preventDefault();
  chrome.tabs.create({ url: "https://github.com/rithik/dualsync#readme" });
});

// DualSync Popup Controller
// Linux <-> Windows Partition Sync

const NATIVE_HOST_NAME = "com.dualsync.bridge";

// Initial platform detection from browser environment
let isWindowsOS = typeof navigator !== "undefined" && (
  navigator.platform?.includes("Win") ||
  navigator.userAgent?.includes("Windows")
);

// DOM Elements
const subtitleText = document.getElementById("subtitle-text");
const bridgeStatusPill = document.getElementById("bridge-status-pill");
const bridgeStatusText = document.getElementById("bridge-status-text");
const extIdVal = document.getElementById("ext-id-val");
const copyIdBtn = document.getElementById("copy-id-btn");
const copyText = document.getElementById("copy-text");

const autoSyncToggle = document.getElementById("auto-sync-toggle");
const autoSyncTitle = document.getElementById("auto-sync-title");
const autoSyncDesc = document.getElementById("auto-sync-desc");

const promptToggle = document.getElementById("prompt-toggle");

const targetLabelText = document.getElementById("target-label-text");
const targetBadge = document.getElementById("target-badge");
const targetTooltip = document.getElementById("target-tooltip");
const targetFolderInput = document.getElementById("target-folder");

const mountBar = document.getElementById("mount-bar");
const mountDot = document.getElementById("mount-dot");
const mountStatusText = document.getElementById("mount-status-text");
const mountDriveBtn = document.getElementById("mount-drive-btn");

const presetChipsList = document.getElementById("preset-chips-list");

const testBridgeBtn = document.getElementById("test-bridge-btn");
const testPromptBtn = document.getElementById("test-prompt-btn");
const saveBtn = document.getElementById("save-btn");

const feedbackCard = document.getElementById("feedback-card");
const feedbackTitle = document.getElementById("feedback-title");
const feedbackMessage = document.getElementById("feedback-message");

const statSyncedCount = document.getElementById("stat-synced-count");
const statLastSynced = document.getElementById("stat-last-synced");
const viewGuideLink = document.getElementById("view-guide-link");

// Default configurations
function getDefaultTarget(isWin) {
  return isWin
    ? "\\\\wsl.localhost\\Ubuntu\\home\\user\\Downloads"
    : "/run/media/rithik/Windows/Users/Asus/Downloads";
}

// Target Validation Constraint:
// In Linux -> Target MUST be Windows drive only. No Linux paths allowed.
// In Windows -> Target MUST be Linux/WSL drive only. No Windows paths allowed.
function validateTargetFolder(path, isWin) {
  if (!path || !path.trim()) {
    return { valid: false, reason: "Target folder cannot be empty." };
  }
  const cleanPath = path.trim();

  if (!isWin) {
    // Linux Environment: Must target Windows
    if (cleanPath.startsWith("/home/") || cleanPath === "/root" || cleanPath.startsWith("/tmp")) {
      return {
        valid: false,
        reason: "In Linux, the sync target must be a Windows partition folder (e.g. in /run/media/.../Windows/Users/...).\nLocal Linux folders cannot be selected."
      };
    }
    const looksLikeWindows = (
      cleanPath.includes("/Windows") ||
      cleanPath.includes("/windows") ||
      cleanPath.includes("/Users/") ||
      cleanPath.includes("/users/") ||
      cleanPath.startsWith("/run/media/") ||
      cleanPath.startsWith("/media/") ||
      cleanPath.startsWith("/mnt/")
    );
    if (!looksLikeWindows) {
      return {
        valid: false,
        reason: "In Linux, target folder must be on your Windows drive (e.g. /run/media/rithik/Windows/Users/Asus/Downloads)."
      };
    }
    return { valid: true };
  } else {
    // Windows Environment: Must target Linux / WSL
    if (/^[A-Za-z]:\\/.test(cleanPath) || cleanPath.includes("\\Users\\")) {
      return {
        valid: false,
        reason: "In Windows, the sync target must be a Linux partition or WSL folder (e.g. \\\\wsl.localhost\\Ubuntu\\home\\...).\nWindows folders cannot be selected."
      };
    }
    const looksLikeLinux = (
      cleanPath.startsWith("\\\\wsl.localhost") ||
      cleanPath.startsWith("\\\\wsl$") ||
      cleanPath.toLowerCase().includes("ext4") ||
      cleanPath.toLowerCase().includes("linux")
    );
    if (!looksLikeLinux) {
      return {
        valid: false,
        reason: "In Windows, target folder must be on your Linux partition or WSL."
      };
    }
    return { valid: true };
  }
}

// Adapt UI to current Operating System
function applyPlatformUI(isWin) {
  if (isWin) {
    if (subtitleText) subtitleText.textContent = "Windows → Linux Drive Sync";
    if (autoSyncTitle) autoSyncTitle.textContent = "Auto-Sync to Linux";
    if (autoSyncDesc) autoSyncDesc.textContent = "Automatically mirror Windows downloads to your Linux partition / WSL";
    if (targetLabelText) targetLabelText.textContent = "Target Linux Download Folder";
    if (targetBadge) {
      targetBadge.className = "os-badge os-badge-linux";
      targetBadge.textContent = "🐧 Linux / WSL Only";
    }
    if (targetTooltip) {
      targetTooltip.title = "In Windows, only Linux partition or WSL download folders are choosable. Windows folders are not allowed.";
    }
    if (targetFolderInput) {
      targetFolderInput.placeholder = "\\\\wsl.localhost\\Ubuntu\\home\\user\\Downloads";
    }
    if (mountBar) {
      mountBar.style.display = "none";
    }
  } else {
    if (subtitleText) subtitleText.textContent = "Linux → Windows Drive Sync";
    if (autoSyncTitle) autoSyncTitle.textContent = "Auto-Sync to Windows";
    if (autoSyncDesc) autoSyncDesc.textContent = "Automatically mirror Linux downloads to your Windows partition";
    if (targetLabelText) targetLabelText.textContent = "Target Windows Download Folder";
    if (targetBadge) {
      targetBadge.className = "os-badge os-badge-windows";
      targetBadge.textContent = "🪟 Windows Only";
    }
    if (targetTooltip) {
      targetTooltip.title = "In Linux, only Windows partition download folders are choosable. Local Linux folders are not allowed.";
    }
    if (targetFolderInput) {
      targetFolderInput.placeholder = "/run/media/rithik/Windows/Users/Asus/Downloads";
    }
    if (mountBar) {
      mountBar.style.display = "flex";
    }
  }
}

// Initialize on DOM load
document.addEventListener("DOMContentLoaded", async () => {
  // Show Extension ID
  const activeId = chrome.runtime?.id || "dlgiaeggibjmhegpeakmgjckgpildjdb";
  if (extIdVal) {
    extIdVal.textContent = activeId;
  }

  // Copy Extension ID
  if (copyIdBtn) {
    copyIdBtn.addEventListener("click", () => {
      const idToCopy = chrome.runtime?.id || extIdVal?.textContent || "";
      navigator.clipboard.writeText(idToCopy).then(() => {
        if (copyText) {
          copyText.textContent = "Copied!";
          setTimeout(() => { copyText.textContent = "Copy"; }, 2000);
        }
      });
    });
  }

  // Setup initial UI for platform
  applyPlatformUI(isWindowsOS);

  // Load existing storage settings
  await loadSettings();

  // Check Native Bridge & verify partition status (triggers auto-mount if needed)
  await checkBridgeStatus(false);
});

// Load settings from storage
async function loadSettings() {
  const defaultTarget = getDefaultTarget(isWindowsOS);
  chrome.storage.local.get(
    {
      autoSync: true,
      promptBeforeSync: true,
      targetFolder: defaultTarget,
      syncedCount: 0,
      lastSynced: "Never"
    },
    (items) => {
      // Validate stored target
      const validation = validateTargetFolder(items.targetFolder, isWindowsOS);
      let targetPath = items.targetFolder;
      if (!validation.valid) {
        targetPath = defaultTarget;
        chrome.storage.local.set({ targetFolder: targetPath });
      }

      if (autoSyncToggle) autoSyncToggle.checked = items.autoSync;
      if (promptToggle) promptToggle.checked = items.promptBeforeSync;
      if (targetFolderInput) targetFolderInput.value = targetPath;
      if (statSyncedCount) statSyncedCount.textContent = items.syncedCount || 0;
      if (statLastSynced) statLastSynced.textContent = items.lastSynced || "Never";
    }
  );
}

// Render dynamic chips strictly from detected valid targets
function renderDetectedChips(paths) {
  if (!presetChipsList) return;
  presetChipsList.innerHTML = "";

  if (!paths || paths.length === 0) {
    const emptySpan = document.createElement("span");
    emptySpan.style.color = "var(--text-muted)";
    emptySpan.style.fontSize = "11px";
    emptySpan.textContent = isWindowsOS ? "No WSL distros detected" : "No Windows download folders detected";
    presetChipsList.appendChild(emptySpan);
    return;
  }

  const currentVal = targetFolderInput.value.trim();

  paths.forEach((item) => {
    const chipBtn = document.createElement("button");
    chipBtn.type = "button";
    chipBtn.className = "chip";
    if (currentVal && currentVal === item.path) {
      chipBtn.classList.add("chip-active");
    }
    chipBtn.textContent = item.label;
    chipBtn.title = item.path;

    chipBtn.addEventListener("click", () => {
      targetFolderInput.value = item.path;
      chrome.storage.local.set({ targetFolder: item.path });

      // Update active state
      document.querySelectorAll(".chip").forEach(c => c.classList.remove("chip-active"));
      chipBtn.classList.add("chip-active");

      showFeedback("success", "Target Selected", `Folder locked to: ${item.label}`);
    });

    presetChipsList.appendChild(chipBtn);
  });
}

// Update partition mount bar status
function updateMountBar(partInfo) {
  if (!mountBar || isWindowsOS) return;

  if (partInfo && partInfo.mounted) {
    mountDot.className = "mount-dot mounted";
    mountStatusText.className = "mount-status-text";
    mountStatusText.innerHTML = `Partition <strong style="color:#86efac;">Mounted (Read/Write)</strong>: ${partInfo.label || "Windows"}`;
    if (mountDriveBtn) mountDriveBtn.style.display = "none";
  } else if (partInfo) {
    mountDot.className = "mount-dot unmounted";
    mountStatusText.className = "mount-status-text";
    mountStatusText.innerHTML = `Partition <strong style="color:#fca5a5;">Unmounted</strong>: ${partInfo.label || "Windows"}`;
    if (mountDriveBtn) mountDriveBtn.style.display = "inline-block";
  } else {
    mountDot.className = "mount-dot";
    mountStatusText.className = "mount-status-text";
    mountStatusText.textContent = "Scanning block devices...";
    if (mountDriveBtn) mountDriveBtn.style.display = "none";
  }
}

// Mount Drive Button Click
if (mountDriveBtn) {
  mountDriveBtn.addEventListener("click", () => {
    mountDriveBtn.disabled = true;
    mountDriveBtn.textContent = "Mounting...";
    showFeedback("info", "Mounting Drive", "Attempting automatic NTFS mount via native host...");

    chrome.runtime.sendNativeMessage(
      NATIVE_HOST_NAME,
      { action: "mount_partition" },
      (resp) => {
        mountDriveBtn.disabled = false;
        mountDriveBtn.textContent = "Mount Drive";

        if (chrome.runtime.lastError) {
          showFeedback("error", "Mount Failed", chrome.runtime.lastError.message);
          return;
        }

        if (resp && resp.success) {
          showFeedback("success", "Drive Mounted!", "Windows partition is now accessible in read/write mode.");
          checkBridgeStatus(true);
        } else {
          showFeedback("error", "Mount Failed", resp?.error || "Could not mount Windows partition.");
        }
      }
    );
  });
}

// Check Bridge Status via Native Host
async function checkBridgeStatus(interactive = false) {
  setBridgePill("checking", "Checking...");

  const currentVal = targetFolderInput.value.trim() || getDefaultTarget(isWindowsOS);

  try {
    chrome.runtime.sendNativeMessage(
      NATIVE_HOST_NAME,
      { action: "ping", targetDir: currentVal },
      (response) => {
        if (chrome.runtime.lastError) {
          const errMsg = chrome.runtime.lastError.message || "Host not responding";
          setBridgePill("disconnected", "Offline");
          if (interactive) {
            const script = isWindowsOS ? "install_host.bat" : "./install_host.sh";
            showFeedback("error", "Bridge Not Connected", `${errMsg}. Run '${script}' in extension folder.`);
          }
          return;
        }

        if (response && response.status === "ok") {
          setBridgePill("connected", "Connected");

          // Update platform awareness from native host if provided
          if (response.platform) {
            const hostIsWin = response.platform === "windows";
            if (hostIsWin !== isWindowsOS) {
              isWindowsOS = hostIsWin;
              applyPlatformUI(isWindowsOS);
            }
          }

          // Update partition mount status bar
          updateMountBar(response.partitionInfo);

          // Render detected target chips dynamically
          if (response.detectedPaths) {
            renderDetectedChips(response.detectedPaths);
          }

          // Auto-select valid detected target if empty or pointing to current OS
          if (response.detectedPath) {
            const currentValidation = validateTargetFolder(targetFolderInput.value, isWindowsOS);
            if (!currentValidation.valid || !targetFolderInput.value.trim()) {
              targetFolderInput.value = response.detectedPath;
              chrome.storage.local.set({ targetFolder: response.detectedPath });
            }
          }

          // Handle warnings or success
          if (response.warning) {
            showFeedback("error", "Partition Notice", response.warning);
          } else if (interactive) {
            let detail = `Native Host v${response.version || "1.3"} active. Target verified & writable!`;
            showFeedback("success", "Bridge Connected!", detail);
          }
        } else {
          setBridgePill("disconnected", "Error");
          if (interactive) {
            showFeedback("error", "Bridge Error", response?.error || "Unknown host error.");
          }
        }
      }
    );
  } catch (err) {
    setBridgePill("disconnected", "Offline");
    if (interactive) {
      showFeedback("error", "Exception", err.message);
    }
  }
}

// Save Settings Button
saveBtn.addEventListener("click", () => {
  const chosenPath = targetFolderInput.value.trim();

  // Strict enforcement:
  // In Linux -> Target must be Windows only.
  // In Windows -> Target must be Linux only.
  const validation = validateTargetFolder(chosenPath, isWindowsOS);
  if (!validation.valid) {
    showFeedback("error", "Invalid Target Folder", validation.reason);
    return;
  }

  const settings = {
    autoSync: autoSyncToggle.checked,
    promptBeforeSync: promptToggle.checked,
    targetFolder: chosenPath
  };

  chrome.storage.local.set(settings, () => {
    showFeedback("success", "Settings Saved", `Target folder locked to: ${chosenPath}`);
    chrome.runtime.sendMessage({ action: "settings_updated", settings });
    checkBridgeStatus(false);
  });
});

// Auto-save toggle switches
autoSyncToggle.addEventListener("change", () => {
  chrome.storage.local.set({ autoSync: autoSyncToggle.checked });
});

promptToggle.addEventListener("change", () => {
  chrome.storage.local.set({ promptBeforeSync: promptToggle.checked });
});

// Bridge Test Button
testBridgeBtn.addEventListener("click", async () => {
  await checkBridgeStatus(true);
});

// Test Pop-up Button
if (testPromptBtn) {
  testPromptBtn.addEventListener("click", () => {
    chrome.runtime.sendMessage({ action: "test_prompt" }, () => {
      showFeedback("info", "Pop-up Window Launched", "A test download prompt window has been opened.");
    });
  });
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

  if (type === "success" || type === "info") {
    setTimeout(() => {
      feedbackCard.classList.add("hidden");
    }, 7000);
  }
}

// Guide Link
if (viewGuideLink) {
  viewGuideLink.addEventListener("click", (e) => {
    e.preventDefault();
    chrome.tabs.create({ url: "https://github.com/Rithikrajaram/Lindows#readme" });
  });
}

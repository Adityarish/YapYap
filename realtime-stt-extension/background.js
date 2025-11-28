let YAPYAP_CONFIG = self.YAPYAP_CONFIG || {};
try {
  importScripts("config.js");
  // config.js populates self.YAPYAP_CONFIG
  YAPYAP_CONFIG = self.YAPYAP_CONFIG || YAPYAP_CONFIG;
} catch (err) {
  console.warn("YapYap config not found, falling back to defaults", err);
}

const backendBaseUrl = (YAPYAP_CONFIG.backendBaseUrl || "http://localhost:5000").replace(/\/$/, "");
const BACKEND_URL = `${backendBaseUrl}/api/extension/latest`;
const POLL_INTERVAL_MS = 2000;

let polling = false;
let pollTimeout = null;
let lastTranscriptId = null;
const activePorts = new Set();

function broadcast(message) {
  activePorts.forEach((port) => {
    try {
      port.postMessage(message);
    } catch (err) {
      console.warn("Failed to post message to port", err);
    }
  });
}

async function pollBackend() {
  if (!polling) {
    return;
  }

  try {
    const resp = await fetch(BACKEND_URL, { cache: "no-store" });
    if (!resp.ok) {
      throw new Error(`Backend responded with ${resp.status}`);
    }

    const payload = await resp.json();
    if (payload && payload.id && payload.id !== lastTranscriptId) {
      lastTranscriptId = payload.id;
      broadcast({ transcript: payload.text || "", timestamp: payload.timestamp });
    }
  } catch (err) {
    console.error("YapYap poll failed", err);
    broadcast({ error: "Unable to reach YapYap backend." });
  } finally {
    pollTimeout = setTimeout(pollBackend, POLL_INTERVAL_MS);
  }
}

function startPolling() {
  if (polling) {
    return;
  }
  polling = true;
  lastTranscriptId = null;
  broadcast({ status: "listening" });
  pollBackend();
}

function stopPolling() {
  polling = false;
  if (pollTimeout) {
    clearTimeout(pollTimeout);
    pollTimeout = null;
  }
  broadcast({ status: "stopped" });
}

chrome.runtime.onConnect.addListener((port) => {
  if (port.name !== "yapyap") {
    return;
  }

  activePorts.add(port);

  port.onMessage.addListener((msg) => {
    if (!msg || !msg.action) {
      return;
    }

    if (msg.action === "START") {
      startPolling();
    } else if (msg.action === "STOP") {
      stopPolling();
    }
  });

  port.onDisconnect.addListener(() => {
    activePorts.delete(port);
    if (activePorts.size === 0) {
      stopPolling();
    }
  });
});

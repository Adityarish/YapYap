let port = chrome.runtime.connect({ name: "yapyap" });

const micButton = document.getElementById("micButton");
const statusBadge = document.getElementById("status");
const output = document.getElementById("output");
const transcriptBox = document.getElementById("transcript");
const searchBtn = document.getElementById("searchBtn");
const copyBtn = document.getElementById("copyBtn");
const insertBtn = document.getElementById("insertBtn");  // NEW

let listening = false;

function setListeningState(isListening) {
  listening = isListening;
  micButton.classList.toggle("listening", isListening);
  statusBadge.textContent = isListening ? "Listening" : "Idle";
}

micButton.addEventListener("click", () => {
  port.postMessage({ action: listening ? "STOP" : "START" });
});
port.onMessage.addListener((msg) => {
  if (!msg) return;

  if (msg.status) {
    if (msg.status === "listening") {
      setListeningState(true);
    } else if (msg.status === "stopped") {
      setListeningState(false);
    } else {
      statusBadge.textContent = msg.status;
    }
  }

  if (msg.error) {
    statusBadge.textContent = "Error";
  }

  if (msg.transcript) {
    output.value += msg.transcript + "\n";
    output.scrollTop = output.scrollHeight;
    transcriptBox.innerText = msg.transcript;
  }
});
copyBtn.addEventListener("click", () => {
  const text = transcriptBox.innerText.trim();
  if (!text) return;

  navigator.clipboard.writeText(text)
    .then(() => console.log("Copied"))
    .catch(err => console.error("Copy failed:", err));
});
searchBtn.addEventListener("click", () => {
  const text = transcriptBox.innerText.trim();
  if (!text) return;

  chrome.tabs.update({
    url: "https://www.google.com/search?q=" + encodeURIComponent(text)
  });
});
insertBtn.addEventListener("click", () => {
  const text = transcriptBox.innerText.trim();
  if (!text) return;

  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (!tabs || !tabs.length) return;

    chrome.tabs.sendMessage(tabs[0].id, {
      action: "INSERT_AT_CURSOR",
      value: text
    });
  });
});

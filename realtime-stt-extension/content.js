console.log("YapYap content script loaded");

// --------------------
// SEARCH TEXT HANDLER
// --------------------
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.action === "SEARCH_TEXT") {
    const text = msg.value;

    const active = document.activeElement;
    if (active && (active.tagName === "INPUT" || active.tagName === "TEXTAREA")) {
      active.value = text;
      active.dispatchEvent(new Event("input", { bubbles: true }));
      active.focus();
      return;
    }

    const selectors = [
      "input[type='search']",
      "input[name='q']",
      "input[aria-label='Search']",
      "input[title='Search']",
      "input[type='text']",
      "textarea"
    ];

    for (const s of selectors) {
      const input = document.querySelector(s);
      if (input) {
        input.value = text;
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.focus();
        return;
      }
    }

    // ChatGPT, WhatsApp Web, Messenger, Discord etc.
    const editable = document.querySelector("[contenteditable='true']");
    if (editable) {
      editable.innerText = text;
      editable.dispatchEvent(new Event("input", { bubbles: true }));
      editable.focus();
    }
  }
});

// ---------------------------------------------
// INSERT_AT_CURSOR (NEW FEATURE)
// ---------------------------------------------
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.action !== "INSERT_AT_CURSOR") return;
  
  const text = msg.value;
  const active = document.activeElement;

  // Case 1: INPUT or TEXTAREA
  if (active && (active.tagName === "INPUT" || active.tagName === "TEXTAREA")) {
    const start = active.selectionStart;
    const end = active.selectionEnd;

    active.value =
      active.value.substring(0, start) +
      text +
      active.value.substring(end);

    // Move cursor to end of inserted text
    const caretPos = start + text.length;
    active.selectionStart = active.selectionEnd = caretPos;

    active.dispatchEvent(new Event("input", { bubbles: true }));
    return;
  }

  // Case 2: contenteditable divs (ChatGPT, WhatsApp, Messenger etc.)
  if (active && active.getAttribute("contenteditable") === "true") {
    const selection = window.getSelection();
    if (!selection.rangeCount) return;

    const range = selection.getRangeAt(0);
    range.deleteContents();

    const node = document.createTextNode(text);
    range.insertNode(node);

    // Move cursor after inserted text
    range.setStartAfter(node);
    range.setEndAfter(node);

    selection.removeAllRanges();
    selection.addRange(range);

    active.dispatchEvent(new Event("input", { bubbles: true }));
    return;
  }

  console.warn("INSERT_AT_CURSOR: No editable field focused.");
});

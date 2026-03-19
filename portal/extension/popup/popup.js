/**
 * Browser Hands — Popup JS
 * ─────────────────────────
 * Handles the manual command panel and live action log display.
 */

const actionSelect  = document.getElementById("action-select");
const selectorInput = document.getElementById("selector-input");
const valueInput    = document.getElementById("value-input");
const valueRow      = document.getElementById("value-row");
const selectorRow   = document.getElementById("selector-row");
const runBtn        = document.getElementById("run-btn");
const wsBtn         = document.getElementById("ws-btn");
const resultBox     = document.getElementById("result-box");
const logBox        = document.getElementById("log-box");
const clearLogBtn   = document.getElementById("clear-log-btn");
const wsBadge       = document.getElementById("ws-badge");

// Actions that need a value field
const NEEDS_VALUE    = ["type", "navigate", "eval"];
const NO_SELECTOR    = ["navigate", "eval"];

// ── Action selector change ──────────────────────────────────────────────────

actionSelect.addEventListener("change", () => {
  const a = actionSelect.value;
  valueRow.style.display    = NEEDS_VALUE.includes(a) ? "flex" : "none";
  selectorRow.style.display = NO_SELECTOR.includes(a) ? "none" : "flex";

  // Update placeholders
  if (a === "navigate") valueInput.placeholder = "https://example.com";
  else if (a === "eval") valueInput.placeholder = "document.title";
  else valueInput.placeholder = "text / value";
});

// ── Run command ─────────────────────────────────────────────────────────────

runBtn.addEventListener("click", async () => {
  const action   = actionSelect.value;
  const selector = selectorInput.value.trim();
  const value    = valueInput.value.trim();

  const command = { action };
  if (!NO_SELECTOR.includes(action) && selector) command.selector = selector;
  if (action === "navigate")  command.url  = value;
  else if (action === "type") command.text = value;
  else if (action === "eval") command.code = value;
  else if (action === "assert" && value) command.text = value;

  resultBox.className = "result-box";
  resultBox.textContent = "⏳ executing…";

  const resp = await chrome.runtime.sendMessage({ type: "HANDS_CMD", command });

  if (resp?.ok) {
    resultBox.className = "result-box ok";
    resultBox.textContent = "✓ " + JSON.stringify(resp.result, null, 2);
  } else {
    resultBox.className = "result-box error";
    resultBox.textContent = "✗ " + (resp?.error ?? "No response");
  }

  loadLog();
});

// ── WebSocket connect ───────────────────────────────────────────────────────

wsBtn.addEventListener("click", async () => {
  await chrome.runtime.sendMessage({ type: "WS_CONNECT" });
  wsBtn.textContent = "⏳ з'єднання…";
  setTimeout(checkWsStatus, 1500);
});

async function checkWsStatus() {
  const resp = await chrome.runtime.sendMessage({ type: "GET_WS_STATUS" });
  const online = resp?.status === "connected";
  wsBadge.textContent = online ? "🟢 portal online" : "⚪ offline";
  wsBadge.className   = "ws-badge " + (online ? "online" : "offline");
  wsBtn.textContent   = "⚡ Підключити портал";
}

// ── Log ─────────────────────────────────────────────────────────────────────

clearLogBtn.addEventListener("click", async () => {
  await chrome.runtime.sendMessage({ type: "CLEAR_LOG" });
  logBox.innerHTML = "";
});

async function loadLog() {
  const entries = await chrome.runtime.sendMessage({ type: "GET_LOG" });
  if (!entries?.length) {
    logBox.innerHTML = '<div style="color:var(--muted);padding:4px">Порожній лог</div>';
    return;
  }
  logBox.innerHTML = entries
    .slice(-50)
    .reverse()
    .map(e => {
      const ts = e.ts ? e.ts.slice(11, 19) : "—";
      const step = (e.stepId || "").slice(-6);
      const ok = e.error ? false : true;
      const detail = ok
        ? `<span class="log-ok">✓</span> ${JSON.stringify(e.result ?? {})}`
        : `<span class="log-err">✗</span> ${e.error}`;
      return `<div class="log-entry">
        <span class="log-ts">${ts}</span>
        <span class="log-step">${step}</span>
        <span class="log-action"><b>${e.action}</b> ${detail}</span>
      </div>`;
    })
    .join("");
}

// ── WS status listener (from background) ────────────────────────────────────

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "WS_STATUS") {
    wsBadge.textContent = msg.status === "connected" ? "🟢 portal online" : "⚪ offline";
    wsBadge.className   = "ws-badge " + (msg.status === "connected" ? "online" : "offline");
  }
});

// ── Init ────────────────────────────────────────────────────────────────────

checkWsStatus();
loadLog();
// Poll log every 3s while popup is open
setInterval(loadLog, 3000);

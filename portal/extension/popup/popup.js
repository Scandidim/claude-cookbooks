/**
 * Browser Hands — Popup v2
 * ─────────────────────────
 * Full rewrite:
 *   - Tabs (Command / Log / Config)
 *   - All 18 actions supported with correct param display
 *   - WS URL configurable via Config tab
 *   - Service worker restart detection
 *   - Live log polling with record count
 */

// ── Elements ────────────────────────────────────────────────────────────────

const actionSelect = document.getElementById("action-select");
const rowSelector  = document.getElementById("row-selector");
const rowValue     = document.getElementById("row-value");
const rowAttr      = document.getElementById("row-attr");
const inpSelector  = document.getElementById("inp-selector");
const inpValue     = document.getElementById("inp-value");
const inpAttr      = document.getElementById("inp-attr");
const runBtn       = document.getElementById("run-btn");
const wsBtn        = document.getElementById("ws-btn");
const resultBox    = document.getElementById("result-box");
const wsBadge      = document.getElementById("ws-badge");
const logBox       = document.getElementById("log-box");
const logCount     = document.getElementById("log-count");
const clearLogBtn  = document.getElementById("clear-log-btn");
const cfgWsUrl     = document.getElementById("cfg-ws-url");
const cfgCmdTimeout = document.getElementById("cfg-cmd-timeout");
const cfgSaveBtn   = document.getElementById("cfg-save-btn");
const cfgResetBtn  = document.getElementById("cfg-reset-btn");
const cfgResult    = document.getElementById("cfg-result");

// ── Tabs ────────────────────────────────────────────────────────────────────

document.querySelectorAll(".tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab, .panel").forEach(el => el.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    if (btn.dataset.tab === "log") loadLog();
    if (btn.dataset.tab === "cfg") loadConfig();
  });
});

// ── Action param visibility ──────────────────────────────────────────────────

const ACTION_CONFIG = {
  // [showSelector, showValue, showAttr, valuePlaceholder]
  navigate:        [false, true,  false, "https://example.com"],
  get_url:         [false, false, false, ""],
  get_title:       [false, false, false, ""],
  click:           [true,  false, false, ""],
  type:            [true,  true,  false, "текст для введення"],
  select:          [true,  true,  false, "option value"],
  clear:           [true,  false, false, ""],
  hover:           [true,  false, false, ""],
  focus:           [true,  false, false, ""],
  key_press:       [true,  true,  false, "Enter / Tab / Escape / ArrowDown…"],
  scroll:          [true,  true,  false, "pixels (default 400) або порожньо для елемента"],
  get_text:        [true,  false, false, ""],
  get_attr:        [true,  false, true,  ""],
  get_value:       [true,  false, false, ""],
  assert:          [true,  true,  false, "очікуваний текст (опц.)"],
  wait_for:        [true,  false, false, ""],
  wait_for_hidden: [true,  false, false, ""],
  screenshot:      [false, false, false, ""],
  eval:            [false, true,  false, "document.title"],
};

actionSelect.addEventListener("change", updateParamRows);

function updateParamRows() {
  const action = actionSelect.value;
  const [showSel, showVal, showAttr, valPlaceholder] = ACTION_CONFIG[action] ?? [true, false, false, ""];
  rowSelector.style.display = showSel  ? "flex" : "none";
  rowValue.style.display    = showVal  ? "flex" : "none";
  rowAttr.style.display     = showAttr ? "flex" : "none";
  inpValue.placeholder = valPlaceholder;
}

updateParamRows();

// ── Build command from UI ────────────────────────────────────────────────────

function buildCommand() {
  const action   = actionSelect.value;
  const selector = inpSelector.value.trim();
  const value    = inpValue.value.trim();
  const attr     = inpAttr.value.trim();

  const cmd = { action };
  if (selector) cmd.selector = selector;

  switch (action) {
    case "navigate":   cmd.url = value;  break;
    case "type":       cmd.text = value; break;
    case "select":     cmd.value = value; break;
    case "key_press":  cmd.key = value;  break;
    case "get_attr":   cmd.attr = attr;  break;
    case "scroll":     if (value) cmd.y = parseInt(value, 10) || 400; break;
    case "assert":     if (value) cmd.contains = value; break;
    case "eval":       cmd.code = value; break;
  }
  return cmd;
}

// ── Run command ──────────────────────────────────────────────────────────────

runBtn.addEventListener("click", async () => {
  const command = buildCommand();
  resultBox.className = "result-box";
  resultBox.textContent = "⏳ виконую…";

  try {
    const resp = await sendToSW({ type: "HANDS_CMD", command });
    if (resp?.ok) {
      resultBox.className = "result-box ok";
      resultBox.textContent = "✓ " + JSON.stringify(resp.result ?? {}, null, 2);
      // Show screenshot inline
      if (command.action === "screenshot" && resp.result?.dataUrl) {
        const img = document.createElement("img");
        img.src = resp.result.dataUrl;
        img.style.cssText = "width:100%;margin-top:6px;border-radius:4px";
        resultBox.appendChild(img);
      }
    } else {
      resultBox.className = "result-box error";
      resultBox.textContent = "✗ " + (resp?.error ?? "Немає відповіді");
    }
  } catch (e) {
    resultBox.className = "result-box error";
    resultBox.textContent = "✗ " + e.message;
  }

  if (document.getElementById("tab-log").classList.contains("active")) loadLog();
});

// ── WebSocket connect button ─────────────────────────────────────────────────

wsBtn.addEventListener("click", async () => {
  wsBtn.textContent = "⏳…";
  await sendToSW({ type: "WS_CONNECT" });
  await sleep(1800);
  updateWsStatus();
  wsBtn.textContent = "⚡ Портал";
});

async function updateWsStatus() {
  try {
    const resp = await sendToSW({ type: "GET_WS_STATUS" });
    const online = resp?.status === "connected";
    wsBadge.textContent = online ? "🟢 online" : "⚪ offline";
    wsBadge.className   = "ws-badge " + (online ? "online" : "offline");
  } catch {
    wsBadge.textContent = "⚪ offline";
    wsBadge.className   = "ws-badge offline";
  }
}

// ── Log ──────────────────────────────────────────────────────────────────────

clearLogBtn.addEventListener("click", async () => {
  await sendToSW({ type: "CLEAR_LOG" });
  loadLog();
});

async function loadLog() {
  let entries;
  try {
    entries = await sendToSW({ type: "GET_LOG", limit: 100 });
  } catch {
    return;
  }
  if (!Array.isArray(entries) || !entries.length) {
    logBox.innerHTML = '<div class="log-empty">Лог порожній</div>';
    logCount.textContent = "0 записів";
    return;
  }
  logCount.textContent = `${entries.length} записів`;
  logBox.innerHTML = [...entries].reverse().map(e => {
    const ts     = (e.ts || "").slice(11, 19);
    const ok     = !e.error;
    const icon   = ok ? '<span class="ok-icon">✓</span>' : '<span class="err-icon">✗</span>';
    const detail = ok
      ? JSON.stringify(e.result ?? {}).slice(0, 60)
      : e.error?.slice(0, 60);
    return `<div class="log-entry">
      <span class="log-ts">${ts}</span>
      <span class="log-action">${icon} ${e.action ?? "?"}</span>
      <span class="log-detail" title="${escHtml(e.error || '')}">${escHtml(detail)}</span>
    </div>`;
  }).join("");
}

// ── Config ───────────────────────────────────────────────────────────────────

async function loadConfig() {
  const cfg = await sendToSW({ type: "GET_CONFIG" });
  cfgWsUrl.value    = cfg.ws_url     ?? "ws://localhost:8765";
  cfgCmdTimeout.value = cfg.cmd_timeout_ms ?? 30000;
}

cfgSaveBtn.addEventListener("click", async () => {
  const config = {
    ws_url:         cfgWsUrl.value.trim() || "ws://localhost:8765",
    cmd_timeout_ms: parseInt(cfgCmdTimeout.value, 10) || 30000,
  };
  await sendToSW({ type: "SET_CONFIG", config });
  cfgResult.textContent = "✓ Збережено. Перепідключіть портал.";
  setTimeout(() => { cfgResult.textContent = ""; }, 3000);
});

cfgResetBtn.addEventListener("click", async () => {
  await sendToSW({ type: "SET_CONFIG", config: {
    ws_url: "ws://localhost:8765",
    cmd_timeout_ms: 30000,
  }});
  loadConfig();
  cfgResult.textContent = "↩ Скинуто до defaults";
  setTimeout(() => { cfgResult.textContent = ""; }, 2000);
});

// ── WS status listener (push from background) ────────────────────────────────

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "WS_STATUS") {
    wsBadge.textContent = msg.status === "connected" ? "🟢 online" : "⚪ offline";
    wsBadge.className   = "ws-badge " + (msg.status === "connected" ? "online" : "offline");
  }
});

// ── Helpers ──────────────────────────────────────────────────────────────────

function sendToSW(msg) {
  return new Promise((resolve, reject) => {
    try {
      chrome.runtime.sendMessage(msg, resp => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          resolve(resp);
        }
      });
    } catch (e) {
      reject(e);
    }
  });
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function escHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ── Init ─────────────────────────────────────────────────────────────────────

updateWsStatus();
setInterval(updateWsStatus, 5000);

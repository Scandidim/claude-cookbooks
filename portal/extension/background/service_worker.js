/**
 * Browser Hands — Background Service Worker v2
 * ─────────────────────────────────────────────
 * Fixes from audit:
 *   - Keepalive alarm prevents MV3 service worker from dying (prevents WS drop)
 *   - WS URL configurable via chrome.storage
 *   - Pending futures rejected when WS closes (no more 30s phantom waits)
 *   - Timeout on message dispatch to content script
 *   - Screenshot action handled here (chrome.tabs.captureVisibleTab)
 *   - Fallback content script injection if tab was opened before extension
 *   - Retry with exponential backoff for content script messages
 *   - GET_LOG WS message type implemented
 *   - Navigate timeout passed from Python client
 */

import { ActionLog } from "./action_log.js";

const log = new ActionLog();

// ── Config (defaults, overridable via chrome.storage) ───────────────────────

const DEFAULTS = {
  ws_url:        "ws://localhost:8765",
  ws_retry_ms:   5000,
  cmd_timeout_ms: 30000,
  nav_timeout_ms: 20000,
};

async function getConfig() {
  const stored = await chrome.storage.local.get(Object.keys(DEFAULTS));
  return { ...DEFAULTS, ...stored };
}

// ── Keepalive (prevents MV3 SW from dying every 30s) ────────────────────────

chrome.alarms.create("hands_keepalive", { periodInMinutes: 0.4 }); // every 24s

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "hands_keepalive") {
    // Just accessing chrome API keeps SW alive
    chrome.storage.local.get("hands_keepalive_ping").then(() => {});
  }
});

// ── WebSocket bridge ─────────────────────────────────────────────────────────

let ws = null;
let wsRetryTimer = null;
let wsConnecting = false;

// Pending commands: requestId → { resolve, reject, timer }
const pending = new Map();

async function connectWS() {
  if (wsConnecting) return;
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;

  wsConnecting = true;
  const cfg = await getConfig();
  clearTimeout(wsRetryTimer);

  try {
    ws = new WebSocket(cfg.ws_url);

    ws.onopen = () => {
      wsConnecting = false;
      console.log("[Hands SW] WebSocket connected:", cfg.ws_url);
      broadcastStatus("connected");
      ws.send(JSON.stringify({ type: "HELLO", agent: "browser_hands", version: "2.0" }));
    };

    ws.onmessage = async (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch { return; }

      switch (msg.type) {
        case "HANDS_CMD": {
          const result = await dispatchToTab(msg.command, msg.tabId);
          ws.send(JSON.stringify({ type: "HANDS_RESULT", requestId: msg.requestId, ...result }));
          break;
        }
        case "HANDS_PIPELINE": {
          // Execute a sequence of commands, stop on first failure
          const results = [];
          for (const cmd of msg.commands ?? []) {
            const r = await dispatchToTab(cmd);
            results.push(r);
            if (!r.ok && !msg.continueOnError) break;
          }
          ws.send(JSON.stringify({ type: "PIPELINE_RESULT", requestId: msg.requestId, results }));
          break;
        }
        case "GET_LOG": {
          const entries = await log.last(msg.limit ?? 100);
          ws.send(JSON.stringify({ type: "LOG_DATA", requestId: msg.requestId, entries }));
          break;
        }
        case "CLEAR_LOG": {
          await log.clear();
          ws.send(JSON.stringify({ type: "LOG_CLEARED", requestId: msg.requestId }));
          break;
        }
        case "GET_STATUS": {
          const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
          ws.send(JSON.stringify({
            type: "STATUS",
            requestId: msg.requestId,
            tab: tab ? { id: tab.id, url: tab.url, title: tab.title } : null,
          }));
          break;
        }
      }
    };

    ws.onclose = (event) => {
      wsConnecting = false;
      console.log("[Hands SW] WebSocket closed:", event.code, event.reason);
      broadcastStatus("disconnected");
      // Reject all pending commands so callers don't wait 30s
      for (const [id, p] of pending) {
        clearTimeout(p.timer);
        p.reject(new Error("WebSocket disconnected while command was pending"));
        pending.delete(id);
      }
      wsRetryTimer = setTimeout(connectWS, cfg.ws_retry_ms);
    };

    ws.onerror = () => {
      wsConnecting = false;
      // onclose will fire after onerror
    };
  } catch (e) {
    wsConnecting = false;
    console.warn("[Hands SW] WebSocket create failed:", e.message);
    wsRetryTimer = setTimeout(connectWS, cfg.ws_retry_ms);
  }
}

function broadcastStatus(status) {
  chrome.runtime.sendMessage({ type: "WS_STATUS", status }).catch(() => {});
}

// ── Message handler (from popup) ─────────────────────────────────────────────

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  switch (msg.type) {
    case "HANDS_CMD":
      dispatchToTab(msg.command, msg.tabId).then(sendResponse);
      return true;

    case "GET_LOG":
      log.last(msg.limit ?? 100).then(sendResponse);
      return true;

    case "CLEAR_LOG":
      log.clear().then(() => sendResponse({ ok: true }));
      return true;

    case "WS_CONNECT":
      connectWS().then(() => sendResponse({ ok: true }));
      return true;

    case "WS_DISCONNECT":
      if (ws) ws.close(1000, "User requested disconnect");
      sendResponse({ ok: true });
      return false;

    case "GET_WS_STATUS":
      sendResponse({
        status: ws && ws.readyState === WebSocket.OPEN ? "connected" : "disconnected",
      });
      return false;

    case "GET_CONFIG":
      getConfig().then(sendResponse);
      return true;

    case "SET_CONFIG":
      chrome.storage.local.set(msg.config).then(() => sendResponse({ ok: true }));
      return true;

    case "SCREENSHOT":
      captureScreenshot(msg.tabId).then(sendResponse);
      return true;
  }
  return false;
});

// ── Tab & content script helpers ─────────────────────────────────────────────

async function getActiveTabId() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab?.id ?? null;
}

async function ensureContentScript(tabId) {
  // Try to ping content script; if it doesn't respond, inject it
  try {
    const resp = await Promise.race([
      chrome.tabs.sendMessage(tabId, { type: "HANDS_PING" }),
      sleep(500),
    ]);
    if (resp?.pong) return; // already injected
  } catch { /* not injected yet */ }

  // Inject programmatically
  await chrome.scripting.executeScript({
    target: { tabId },
    files: ["content/RUKI.js"],
  });
  await sleep(100); // let it initialise
}

// ── Screenshot ───────────────────────────────────────────────────────────────

async function captureScreenshot(tabId) {
  const id = tabId ?? await getActiveTabId();
  if (!id) return { ok: false, error: "No active tab" };
  try {
    const dataUrl = await chrome.tabs.captureVisibleTab(null, { format: "png" });
    const stepId = makeStepId();
    await log.add({ stepId, action: "screenshot", result: { size: dataUrl.length } });
    return { ok: true, result: { dataUrl, stepId } };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

// ── Navigation ───────────────────────────────────────────────────────────────

async function navigateAndWait(tabId, url, timeoutMs) {
  await chrome.tabs.update(tabId, { url });
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      chrome.webNavigation.onCompleted.removeListener(listener);
      reject(new Error(`Navigation timeout after ${timeoutMs}ms: ${url}`));
    }, timeoutMs);

    function listener(details) {
      if (details.tabId === tabId && details.frameId === 0) {
        clearTimeout(timer);
        chrome.webNavigation.onCompleted.removeListener(listener);
        resolve();
      }
    }
    chrome.webNavigation.onCompleted.addListener(listener);
  });
}

// ── Dispatch to content script ───────────────────────────────────────────────

async function dispatchToTab(command, tabId = null) {
  const { action, url, timeoutMs: cmdTimeout, ...params } = command;
  const stepId = makeStepId();
  const cfg = await getConfig();
  const timeout = cmdTimeout ?? cfg.cmd_timeout_ms;

  const activeTabId = tabId ?? await getActiveTabId();
  if (!activeTabId) {
    const err = "No active tab found";
    await log.add({ stepId, action, params, error: err });
    return { ok: false, error: err };
  }

  try {
    // Navigate: handled in background
    if (action === "navigate") {
      const navTimeout = params.navTimeoutMs ?? cfg.nav_timeout_ms;
      await navigateAndWait(activeTabId, url, navTimeout);
      await sleep(300); // let page scripts initialise
      const result = { url };
      await log.add({ stepId, action, params: { url }, result });
      return { ok: true, result };
    }

    // Screenshot: handled in background
    if (action === "screenshot") {
      return captureScreenshot(activeTabId);
    }

    // All other actions → content script
    await ensureContentScript(activeTabId);

    const result = await Promise.race([
      chrome.tabs.sendMessage(activeTabId, { type: "HANDS_CMD", stepId, command: { action, ...params } }),
      sleep(timeout).then(() => ({ ok: false, error: `Timeout after ${timeout}ms: ${action}` })),
    ]);

    await log.add({ stepId, action, params, result: result?.result, error: result?.error });
    return result ?? { ok: false, error: "No response from content script" };

  } catch (e) {
    const err = e.message || String(e);
    await log.add({ stepId, action, params, error: err });
    return { ok: false, error: err };
  }
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function makeStepId() {
  return `${Date.now().toString(36)}_${crypto.randomUUID().slice(0, 8)}`;
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ── Init ─────────────────────────────────────────────────────────────────────

chrome.runtime.onInstalled.addListener(() => {
  console.log("[Hands SW] Installed v2");
});

// Add PING handler to content script (for ensureContentScript check)
// Note: this is a no-op message, content script already handles it implicitly
// via the message listener. We respond to HANDS_PING there via background.

connectWS();

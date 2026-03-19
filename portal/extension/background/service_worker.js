/**
 * Browser Hands — Background Service Worker
 * ──────────────────────────────────────────
 * Command Bus: routes commands from popup / WebSocket bridge
 * to the active tab's content script.
 *
 * Message protocol:
 *   { type: "HANDS_CMD", command: { action, ...params }, requestId }
 *   → content script executes action
 *   → responds with { ok, result, error, requestId }
 *
 * WebSocket bridge:
 *   Connects to ws://localhost:8765 (local AI portal server).
 *   Portal sends JSON commands; bridge relays them to active tab.
 */

import { ActionLog } from "./action_log.js";

const log = new ActionLog();

// ── WebSocket bridge to local portal ────────────────────────────────────────

let ws = null;
let wsRetryTimer = null;
const WS_URL = "ws://localhost:8765";
const WS_RETRY_MS = 5000;

function connectWS() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
  try {
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      console.log("[Hands] WebSocket connected to portal");
      clearTimeout(wsRetryTimer);
      broadcastStatus("connected");
      ws.send(JSON.stringify({ type: "HELLO", agent: "browser_hands", version: "1.0.0" }));
    };

    ws.onmessage = async (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch { return; }
      if (msg.type === "HANDS_CMD") {
        const result = await dispatchToTab(msg.command);
        ws.send(JSON.stringify({ type: "HANDS_RESULT", requestId: msg.requestId, ...result }));
      }
    };

    ws.onclose = () => {
      console.log("[Hands] WebSocket closed — retry in", WS_RETRY_MS, "ms");
      broadcastStatus("disconnected");
      wsRetryTimer = setTimeout(connectWS, WS_RETRY_MS);
    };

    ws.onerror = (err) => {
      console.warn("[Hands] WebSocket error", err);
    };
  } catch (e) {
    console.warn("[Hands] Could not create WebSocket:", e);
    wsRetryTimer = setTimeout(connectWS, WS_RETRY_MS);
  }
}

function broadcastStatus(status) {
  chrome.runtime.sendMessage({ type: "WS_STATUS", status }).catch(() => {});
}

// ── Message handler from popup / content ────────────────────────────────────

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === "HANDS_CMD") {
    dispatchToTab(msg.command).then(sendResponse);
    return true; // async
  }
  if (msg.type === "GET_LOG") {
    log.getAll().then(sendResponse);
    return true;
  }
  if (msg.type === "CLEAR_LOG") {
    log.clear().then(() => sendResponse({ ok: true }));
    return true;
  }
  if (msg.type === "WS_CONNECT") {
    connectWS();
    sendResponse({ ok: true });
    return false;
  }
  if (msg.type === "GET_WS_STATUS") {
    sendResponse({ status: ws && ws.readyState === WebSocket.OPEN ? "connected" : "disconnected" });
    return false;
  }
});

// ── Tab navigation helper ────────────────────────────────────────────────────

async function getActiveTabId() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab?.id ?? null;
}

async function navigateAndWait(tabId, url, timeoutMs = 15000) {
  await chrome.tabs.update(tabId, { url });
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      chrome.webNavigation.onCompleted.removeListener(listener);
      reject(new Error("Navigation timeout"));
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

// ── Dispatch command to active tab's content script ─────────────────────────

async function dispatchToTab(command) {
  const { action, url, ...params } = command;
  const stepId = `step_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;

  try {
    let tabId = await getActiveTabId();
    if (!tabId) throw new Error("No active tab found");

    // Handle navigation at the background level (cannot inject before page loads)
    if (action === "navigate") {
      await navigateAndWait(tabId, url);
      // small settle delay for JS to run
      await sleep(500);
      const result = { ok: true, result: { url } };
      await log.add({ stepId, action, params: { url }, result: result.result });
      return result;
    }

    // All other actions go to content script
    const result = await chrome.tabs.sendMessage(tabId, {
      type: "HANDS_CMD",
      stepId,
      command: { action, ...params },
    });
    await log.add({ stepId, action, params, result: result?.result, error: result?.error });
    return result ?? { ok: false, error: "No response from content script" };

  } catch (e) {
    const err = e.message || String(e);
    await log.add({ stepId, action, params, error: err });
    return { ok: false, error: err };
  }
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ── Init ────────────────────────────────────────────────────────────────────

chrome.runtime.onInstalled.addListener(() => {
  console.log("[Hands] Extension installed / updated");
});

// Auto-connect to local portal on startup
connectWS();

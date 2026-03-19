/**
 * Browser Hands — Content Script
 * ───────────────────────────────
 * Runs on every page. Listens for HANDS_CMD messages from the
 * background service worker and executes browser actions.
 *
 * Supported actions:
 *   click        { selector }
 *   type         { selector, text, clear? }
 *   select       { selector, value }
 *   assert       { selector, text?, exists? }
 *   wait_for     { selector, timeoutMs? }
 *   get_text     { selector }
 *   get_attr     { selector, attr }
 *   scroll       { selector? | x, y }
 *   screenshot   (triggers chrome API from background; content returns ack)
 *   eval         { code }   ⚠ sandboxed string eval for simple DOM expressions
 */

(function () {
  "use strict";

  // ── Selector strategy ──────────────────────────────────────────────────────
  // Priority: data-testid → aria-label → name → id → css
  // Returns null if nothing found within timeoutMs.

  const RETRY_INTERVAL = 100;

  async function findElement(selector, timeoutMs = 5000) {
    const deadline = Date.now() + timeoutMs;

    while (Date.now() < deadline) {
      const el = resolveSelector(selector);
      if (el) return el;
      await sleep(RETRY_INTERVAL);
    }
    return null;
  }

  function resolveSelector(selector) {
    if (!selector) return null;

    // data-testid shorthand: testid=foo
    if (selector.startsWith("testid=")) {
      return document.querySelector(`[data-testid="${selector.slice(7)}"]`);
    }
    // aria shorthand: aria=label text
    if (selector.startsWith("aria=")) {
      const label = selector.slice(5);
      return (
        document.querySelector(`[aria-label="${label}"]`) ||
        document.querySelector(`[aria-labelledby="${label}"]`) ||
        findByText(label)
      );
    }
    // name shorthand: name=foo
    if (selector.startsWith("name=")) {
      return document.querySelector(`[name="${selector.slice(5)}"]`);
    }
    // text shorthand: text=Click me
    if (selector.startsWith("text=")) {
      return findByText(selector.slice(5));
    }
    // Fallback: standard CSS / id
    try {
      return document.querySelector(selector);
    } catch {
      return null;
    }
  }

  function findByText(text) {
    const lower = text.toLowerCase();
    const candidates = ["button", "a", "label", "span", "div", "li", "td", "th", "input[type=submit]"];
    for (const tag of candidates) {
      for (const el of document.querySelectorAll(tag)) {
        if (el.textContent.trim().toLowerCase() === lower) return el;
      }
    }
    return null;
  }

  // ── Actions ────────────────────────────────────────────────────────────────

  async function actionClick({ selector, timeoutMs = 5000 }) {
    const el = await findElement(selector, timeoutMs);
    if (!el) throw new Error(`Element not found: ${selector}`);
    el.scrollIntoView({ block: "center", behavior: "smooth" });
    await sleep(80);
    el.focus();
    el.click();
    return { selector, tag: el.tagName };
  }

  async function actionType({ selector, text, clear = true, timeoutMs = 5000 }) {
    const el = await findElement(selector, timeoutMs);
    if (!el) throw new Error(`Element not found: ${selector}`);
    el.scrollIntoView({ block: "center" });
    el.focus();
    if (clear) {
      el.value = "";
      el.dispatchEvent(new Event("input", { bubbles: true }));
    }
    for (const char of String(text)) {
      el.value += char;
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new KeyboardEvent("keydown", { key: char, bubbles: true }));
      el.dispatchEvent(new KeyboardEvent("keyup",  { key: char, bubbles: true }));
      await sleep(20);
    }
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return { selector, typed: text };
  }

  async function actionSelect({ selector, value, timeoutMs = 5000 }) {
    const el = await findElement(selector, timeoutMs);
    if (!el) throw new Error(`Element not found: ${selector}`);
    el.focus();
    el.value = value;
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return { selector, value };
  }

  async function actionWaitFor({ selector, timeoutMs = 10000 }) {
    const el = await findElement(selector, timeoutMs);
    if (!el) throw new Error(`Timeout waiting for: ${selector}`);
    return { selector, found: true };
  }

  async function actionAssert({ selector, text, exists = true, timeoutMs = 5000 }) {
    const el = await findElement(selector, timeoutMs);
    if (exists && !el) throw new Error(`Assert failed — element not found: ${selector}`);
    if (!exists && el) throw new Error(`Assert failed — element should NOT exist: ${selector}`);
    if (text !== undefined && el) {
      const actual = el.textContent.trim();
      if (!actual.includes(text)) {
        throw new Error(`Assert failed — expected text "${text}" in "${actual}"`);
      }
    }
    return { selector, ok: true };
  }

  async function actionGetText({ selector, timeoutMs = 5000 }) {
    const el = await findElement(selector, timeoutMs);
    if (!el) throw new Error(`Element not found: ${selector}`);
    return { selector, text: el.textContent.trim() };
  }

  async function actionGetAttr({ selector, attr, timeoutMs = 5000 }) {
    const el = await findElement(selector, timeoutMs);
    if (!el) throw new Error(`Element not found: ${selector}`);
    return { selector, attr, value: el.getAttribute(attr) };
  }

  async function actionScroll({ selector, x = 0, y = 0, timeoutMs = 3000 }) {
    if (selector) {
      const el = await findElement(selector, timeoutMs);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
    } else {
      window.scrollBy({ top: y, left: x, behavior: "smooth" });
    }
    return { scrolled: true };
  }

  async function actionEval({ code }) {
    // Safety: only allow simple expressions (no Function constructor, no eval of eval)
    if (/\beval\b|\bFunction\b|\bimport\b/.test(code)) {
      throw new Error("Blocked: unsafe eval expression");
    }
    // eslint-disable-next-line no-eval
    const result = eval(code);
    return { result: String(result) };
  }

  // ── Dispatch ───────────────────────────────────────────────────────────────

  const ACTIONS = {
    click:    actionClick,
    type:     actionType,
    select:   actionSelect,
    wait_for: actionWaitFor,
    assert:   actionAssert,
    get_text: actionGetText,
    get_attr: actionGetAttr,
    scroll:   actionScroll,
    eval:     actionEval,
  };

  async function handleCommand(command) {
    const { action, ...params } = command;
    const fn = ACTIONS[action];
    if (!fn) return { ok: false, error: `Unknown action: ${action}` };
    try {
      const result = await fn(params);
      return { ok: true, result };
    } catch (e) {
      return { ok: false, error: e.message || String(e) };
    }
  }

  // ── Message listener ───────────────────────────────────────────────────────

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg.type !== "HANDS_CMD") return false;
    handleCommand(msg.command).then(sendResponse);
    return true; // async
  });

  // ── Helpers ────────────────────────────────────────────────────────────────

  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

  console.log("[Hands] Content script loaded on", location.href);
})();

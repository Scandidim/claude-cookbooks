/**
 * Browser Hands — Content Script v3
 * ────────────────────────────────────
 * Accessibility-first rewrite.
 * This extension IS the hands, eyes, and ears for people with disabilities.
 *
 * 🤲 MOTOR  (no hands) — click, drag, key combos, checkboxes, context menu
 * 👁  VISION (no eyes)  — page structure, headings, links, forms, tables, ARIA
 * 👂 HEARING (no ears)  — media control, captions, transcript extraction
 */

(function () {
  "use strict";

  const LOG_PREFIX = "[Hands]";
  const POLL_MS = 80;          // element polling interval
  const SETTLE_MS = 50;        // settle delay after DOM interaction
  const SCROLL_SETTLE_MS = 80; // after scrollIntoView

  function dbg(...args) {
    console.debug(LOG_PREFIX, ...args);
  }

  // ── Selector Engine (7 levels) ─────────────────────────────────────────────

  /**
   * Resolve a selector to a DOM element.
   * Levels tried in order:
   *   1. testid=foo       → [data-testid="foo"]
   *   2. aria=label text  → [aria-label], [aria-labelledby], role+text
   *   3. name=foo         → [name="foo"]
   *   4. placeholder=foo  → [placeholder="foo"]
   *   5. text=Click me    → exact visible text match (trimmed)
   *   6. contains=Click   → partial visible text match
   *   7. CSS              → document.querySelector(selector)
   */
  function resolveSelector(selector) {
    if (!selector || typeof selector !== "string") return null;
    const s = selector.trim();

    if (s.startsWith("testid=")) {
      return qs(`[data-testid="${css(s.slice(7))}"]`);
    }
    if (s.startsWith("aria=")) {
      const label = s.slice(5);
      return (
        qs(`[aria-label="${css(label)}"]`) ||
        qs(`[aria-placeholder="${css(label)}"]`) ||
        findByRole(label) ||
        findByExactText(label)
      );
    }
    if (s.startsWith("name=")) {
      return qs(`[name="${css(s.slice(5))}"]`);
    }
    if (s.startsWith("placeholder=")) {
      return qs(`[placeholder="${css(s.slice(12))}"]`);
    }
    if (s.startsWith("text=")) {
      return findByExactText(s.slice(5));
    }
    if (s.startsWith("contains=")) {
      return findByPartialText(s.slice(9));
    }
    // CSS fallback
    try {
      return document.querySelector(s);
    } catch {
      return null;
    }
  }

  function qs(sel) {
    try { return document.querySelector(sel); } catch { return null; }
  }

  // Escape for CSS attribute selector
  function css(v) {
    return v.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  }

  // Normalise whitespace: collapse runs of whitespace to single space, trim
  function normalise(text) {
    return text.replace(/\s+/g, " ").trim().toLowerCase();
  }

  const TEXT_TAGS = ["button", "a", "label", "span", "div", "li", "td", "th",
    "h1", "h2", "h3", "h4", "p", "input", "summary"];

  function findByExactText(text) {
    const target = normalise(text);
    for (const tag of TEXT_TAGS) {
      for (const el of document.querySelectorAll(tag)) {
        if (!isVisible(el)) continue;
        if (normalise(el.textContent) === target) return el;
        // value for inputs
        if (el.tagName === "INPUT" && normalise(el.value) === target) return el;
      }
    }
    return null;
  }

  function findByPartialText(text) {
    const target = normalise(text);
    for (const tag of TEXT_TAGS) {
      for (const el of document.querySelectorAll(tag)) {
        if (!isVisible(el)) continue;
        if (normalise(el.textContent).includes(target)) return el;
      }
    }
    return null;
  }

  function findByRole(label) {
    const target = normalise(label);
    for (const el of document.querySelectorAll("[role]")) {
      const ariaLabel = el.getAttribute("aria-label") || el.getAttribute("aria-labelledby") || "";
      if (normalise(ariaLabel) === target && isVisible(el)) return el;
    }
    return null;
  }

  // ── Visibility & Interactability ───────────────────────────────────────────

  function isVisible(el) {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return false;
    const style = window.getComputedStyle(el);
    return style.visibility !== "hidden" && style.display !== "none" && style.opacity !== "0";
  }

  function isInteractable(el) {
    if (!el || !isVisible(el)) return false;
    if (el.disabled) return false;
    if (el.getAttribute("aria-disabled") === "true") return false;
    // pointer-events: none
    const style = window.getComputedStyle(el);
    if (style.pointerEvents === "none") return false;
    return true;
  }

  // ── Element waiter with backoff ────────────────────────────────────────────

  async function waitForElement(selector, timeoutMs = 5000, requireInteractable = false) {
    const deadline = Date.now() + timeoutMs;
    let delay = POLL_MS;

    while (Date.now() < deadline) {
      const el = resolveSelector(selector);
      if (el) {
        if (!requireInteractable || isInteractable(el)) return el;
      }
      await sleep(Math.min(delay, deadline - Date.now()));
      delay = Math.min(delay * 1.5, 500); // backoff, max 500ms
    }
    return null;
  }

  // ── Scroll helper ──────────────────────────────────────────────────────────

  async function scrollTo(el) {
    el.scrollIntoView({ block: "center", behavior: "instant" });
    await sleep(SCROLL_SETTLE_MS);
  }

  // ── Actions ────────────────────────────────────────────────────────────────

  async function actionClick({ selector, timeoutMs = 5000 }) {
    const el = await waitForElement(selector, timeoutMs, true);
    if (!el) throw new Error(`click: element not found or not interactable: ${selector}`);
    await scrollTo(el);
    el.focus();
    el.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, cancelable: true }));
    el.dispatchEvent(new MouseEvent("mousedown",  { bubbles: true, cancelable: true }));
    el.dispatchEvent(new MouseEvent("mouseup",    { bubbles: true }));
    el.click();
    el.dispatchEvent(new MouseEvent("mouseleave", { bubbles: true }));
    await sleep(SETTLE_MS);
    return { selector, tag: el.tagName.toLowerCase(), text: el.textContent.trim().slice(0, 80) };
  }

  async function actionType({ selector, text, clear = true, timeoutMs = 5000 }) {
    const el = await waitForElement(selector, timeoutMs, true);
    if (!el) throw new Error(`type: element not found or not interactable: ${selector}`);
    await scrollTo(el);
    el.focus();

    if (clear) {
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        Object.getPrototypeOf(el) === HTMLInputElement.prototype
          ? HTMLInputElement.prototype
          : HTMLTextAreaElement.prototype,
        "value"
      )?.set;
      if (nativeInputValueSetter) {
        // React/Vue friendly clear
        nativeInputValueSetter.call(el, "");
      } else {
        el.value = "";
      }
      el.dispatchEvent(new Event("input",  { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
    }

    const chars = String(text);
    for (const char of chars) {
      el.dispatchEvent(new KeyboardEvent("keydown",  { key: char, bubbles: true, cancelable: true }));
      el.dispatchEvent(new KeyboardEvent("keypress", { key: char, bubbles: true, cancelable: true }));
      const setter = Object.getOwnPropertyDescriptor(
        Object.getPrototypeOf(el) === HTMLInputElement.prototype
          ? HTMLInputElement.prototype
          : HTMLTextAreaElement.prototype,
        "value"
      )?.set;
      if (setter) {
        setter.call(el, el.value + char);
      } else {
        el.value += char;
      }
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new KeyboardEvent("keyup", { key: char, bubbles: true }));
      await sleep(15);
    }

    el.dispatchEvent(new Event("change", { bubbles: true }));
    await sleep(SETTLE_MS);
    return { selector, typed: chars, length: chars.length };
  }

  async function actionSelect({ selector, value, label, timeoutMs = 5000 }) {
    const el = await waitForElement(selector, timeoutMs, true);
    if (!el) throw new Error(`select: element not found: ${selector}`);
    if (el.tagName.toUpperCase() !== "SELECT") {
      throw new Error(`select: element is not a <select>: ${selector} (got ${el.tagName})`);
    }

    let found = false;
    for (const opt of el.options) {
      if (opt.value === value || (label && opt.text === label)) {
        el.value = opt.value;
        found = true;
        break;
      }
    }
    if (!found) {
      const available = Array.from(el.options).map(o => o.value).join(", ");
      throw new Error(`select: option "${value}" not found. Available: ${available}`);
    }

    el.dispatchEvent(new Event("change", { bubbles: true }));
    await sleep(SETTLE_MS);
    return { selector, value: el.value };
  }

  async function actionWaitFor({ selector, timeoutMs = 10000, visible = true }) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const el = resolveSelector(selector);
      if (el && (!visible || isVisible(el))) {
        return { selector, found: true, tag: el.tagName.toLowerCase() };
      }
      await sleep(POLL_MS);
    }
    throw new Error(`wait_for: timeout (${timeoutMs}ms) waiting for: ${selector}`);
  }

  async function actionWaitForHidden({ selector, timeoutMs = 10000 }) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const el = resolveSelector(selector);
      if (!el || !isVisible(el)) return { selector, hidden: true };
      await sleep(POLL_MS);
    }
    throw new Error(`wait_for_hidden: timeout (${timeoutMs}ms): ${selector} still visible`);
  }

  async function actionAssert({ selector, text, contains, exists = true, timeoutMs = 5000 }) {
    const el = await waitForElement(selector, timeoutMs);

    if (exists && !el) {
      throw new Error(`assert: element not found: ${selector}`);
    }
    if (!exists) {
      if (el && isVisible(el)) throw new Error(`assert: element should NOT exist/be visible: ${selector}`);
      return { selector, ok: true, exists: false };
    }

    if (text !== undefined) {
      const actual = normalise(el.textContent);
      const expected = normalise(text);
      if (actual !== expected) {
        throw new Error(`assert text: expected "${expected}", got "${actual}"`);
      }
    }
    if (contains !== undefined) {
      const actual = normalise(el.textContent);
      if (!actual.includes(normalise(contains))) {
        throw new Error(`assert contains: "${contains}" not found in "${el.textContent.trim().slice(0, 200)}"`);
      }
    }

    return { selector, ok: true, text: el.textContent.trim().slice(0, 200) };
  }

  async function actionGetText({ selector, timeoutMs = 5000, trim = true }) {
    const el = await waitForElement(selector, timeoutMs);
    if (!el) throw new Error(`get_text: element not found: ${selector}`);
    const text = trim ? el.textContent.trim() : el.textContent;
    return { selector, text };
  }

  async function actionGetAttr({ selector, attr, timeoutMs = 5000 }) {
    if (!attr) throw new Error("get_attr: 'attr' parameter required");
    const el = await waitForElement(selector, timeoutMs);
    if (!el) throw new Error(`get_attr: element not found: ${selector}`);
    return { selector, attr, value: el.getAttribute(attr) };
  }

  async function actionGetValue({ selector, timeoutMs = 5000 }) {
    const el = await waitForElement(selector, timeoutMs);
    if (!el) throw new Error(`get_value: element not found: ${selector}`);
    return { selector, value: el.value ?? null };
  }

  async function actionScroll({ selector, x = 0, y = 400, timeoutMs = 3000 }) {
    if (selector) {
      const el = await waitForElement(selector, timeoutMs);
      if (el) {
        await scrollTo(el);
        return { scrolled: "element", selector };
      }
    }
    window.scrollBy({ top: y, left: x, behavior: "instant" });
    await sleep(SCROLL_SETTLE_MS);
    return { scrolled: "window", x, y };
  }

  async function actionHover({ selector, timeoutMs = 5000 }) {
    const el = await waitForElement(selector, timeoutMs);
    if (!el) throw new Error(`hover: element not found: ${selector}`);
    await scrollTo(el);
    el.dispatchEvent(new MouseEvent("mouseover", { bubbles: true }));
    el.dispatchEvent(new MouseEvent("mouseenter", { bubbles: true }));
    await sleep(SETTLE_MS);
    return { selector, hovered: true };
  }

  async function actionFocus({ selector, timeoutMs = 5000 }) {
    const el = await waitForElement(selector, timeoutMs);
    if (!el) throw new Error(`focus: element not found: ${selector}`);
    el.focus();
    await sleep(SETTLE_MS);
    return { selector, focused: true };
  }

  async function actionClear({ selector, timeoutMs = 5000 }) {
    return actionType({ selector, text: "", clear: true, timeoutMs });
  }

  async function actionKeyPress({ selector, key, timeoutMs = 5000 }) {
    if (!key) throw new Error("key_press: 'key' parameter required (e.g. 'Enter', 'Tab', 'Escape')");
    let target = document.activeElement || document.body;
    if (selector) {
      const el = await waitForElement(selector, timeoutMs);
      if (!el) throw new Error(`key_press: element not found: ${selector}`);
      el.focus();
      target = el;
    }
    target.dispatchEvent(new KeyboardEvent("keydown",  { key, bubbles: true, cancelable: true }));
    target.dispatchEvent(new KeyboardEvent("keyup",    { key, bubbles: true }));
    await sleep(SETTLE_MS);
    return { key, target: target.tagName };
  }

  async function actionScreenshot() {
    // Screenshot is handled by the background script (needs chrome.tabs.captureVisibleTab)
    // Content script just acknowledges.
    return { ok: true, note: "Screenshot handled by background" };
  }

  async function actionGetUrl() {
    return { url: location.href, title: document.title };
  }

  async function actionGetTitle() {
    return { title: document.title };
  }

  // Safe eval: sandboxed in a Worker blob so it cannot access DOM
  async function actionEval({ code, timeoutMs = 5000 }) {
    if (!code || typeof code !== "string") throw new Error("eval: 'code' string required");

    return new Promise((resolve, reject) => {
      const blob = new Blob([`
        self.onmessage = function(e) {
          try {
            var result = (function() { return eval(e.data); })();
            self.postMessage({ ok: true, result: String(result) });
          } catch(err) {
            self.postMessage({ ok: false, error: err.message });
          }
        };
      `], { type: "application/javascript" });

      const url = URL.createObjectURL(blob);
      const worker = new Worker(url);

      const timer = setTimeout(() => {
        worker.terminate();
        URL.revokeObjectURL(url);
        reject(new Error(`eval: timeout after ${timeoutMs}ms`));
      }, timeoutMs);

      worker.onmessage = (e) => {
        clearTimeout(timer);
        worker.terminate();
        URL.revokeObjectURL(url);
        if (e.data.ok) resolve({ result: e.data.result });
        else reject(new Error(`eval error: ${e.data.error}`));
      };

      worker.onerror = (e) => {
        clearTimeout(timer);
        worker.terminate();
        URL.revokeObjectURL(url);
        reject(new Error(`eval worker error: ${e.message}`));
      };

      worker.postMessage(code);
    });
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 🤲 MOTOR ACTIONS — for people without hands
  // Повний набір керування: подвійний клік, правий клік, перетягування,
  // комбінації клавіш, чекбокси, навігація браузером
  // ══════════════════════════════════════════════════════════════════════════

  async function actionDoubleClick({ selector, timeoutMs = 5000 }) {
    const el = await waitForElement(selector, timeoutMs, true);
    if (!el) throw new Error(`double_click: not found or not interactable: ${selector}`);
    await scrollTo(el);
    el.focus();
    el.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true, detail: 1 }));
    el.dispatchEvent(new MouseEvent("mouseup",   { bubbles: true, detail: 1 }));
    el.dispatchEvent(new MouseEvent("click",     { bubbles: true, detail: 1 }));
    el.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true, detail: 2 }));
    el.dispatchEvent(new MouseEvent("mouseup",   { bubbles: true, detail: 2 }));
    el.dispatchEvent(new MouseEvent("dblclick",  { bubbles: true, detail: 2 }));
    await sleep(SETTLE_MS);
    return { selector, dblclicked: true };
  }

  async function actionRightClick({ selector, timeoutMs = 5000 }) {
    const el = await waitForElement(selector, timeoutMs);
    if (!el) throw new Error(`right_click: not found: ${selector}`);
    await scrollTo(el);
    el.dispatchEvent(new MouseEvent("mousedown",   { bubbles: true, cancelable: true, button: 2 }));
    el.dispatchEvent(new MouseEvent("mouseup",     { bubbles: true, button: 2 }));
    el.dispatchEvent(new MouseEvent("contextmenu", { bubbles: true, cancelable: true, button: 2 }));
    await sleep(SETTLE_MS);
    return { selector, contextmenu: true };
  }

  /**
   * Drag from one element/coordinate to another.
   * fromSelector / toSelector — use element centres
   * fromX,fromY / toX,toY   — use explicit viewport coordinates
   */
  async function actionDrag({ fromSelector, toSelector, fromX, fromY, toX, toY, timeoutMs = 5000 }) {
    function centre(el) {
      const r = el.getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    }

    let start, end;
    if (fromSelector) {
      const el = await waitForElement(fromSelector, timeoutMs);
      if (!el) throw new Error(`drag: from element not found: ${fromSelector}`);
      start = centre(el);
    } else {
      start = { x: fromX ?? 0, y: fromY ?? 0 };
    }
    if (toSelector) {
      const el = await waitForElement(toSelector, timeoutMs);
      if (!el) throw new Error(`drag: to element not found: ${toSelector}`);
      end = centre(el);
    } else {
      end = { x: toX ?? 0, y: toY ?? 0 };
    }

    const dt = new DataTransfer();
    const fromEl = fromSelector ? resolveSelector(fromSelector) : document.elementFromPoint(start.x, start.y);
    const toEl   = toSelector   ? resolveSelector(toSelector)   : document.elementFromPoint(end.x, end.y);

    fromEl?.dispatchEvent(new DragEvent("dragstart", { bubbles: true, cancelable: true, dataTransfer: dt, clientX: start.x, clientY: start.y }));
    await sleep(30);
    toEl?.dispatchEvent(new DragEvent("dragover",  { bubbles: true, cancelable: true, dataTransfer: dt, clientX: end.x, clientY: end.y }));
    toEl?.dispatchEvent(new DragEvent("drop",      { bubbles: true, cancelable: true, dataTransfer: dt, clientX: end.x, clientY: end.y }));
    fromEl?.dispatchEvent(new DragEvent("dragend",   { bubbles: true, dataTransfer: dt }));
    await sleep(SETTLE_MS);
    return { from: start, to: end };
  }

  /**
   * key_combo — multi-key shortcuts: "Ctrl+C", "Alt+Tab", "Shift+Enter", "Ctrl+Shift+T"
   * Supports: Ctrl, Alt, Shift, Meta (Cmd on Mac)
   */
  async function actionKeyCombo({ keys, selector, timeoutMs = 5000 }) {
    if (!keys) throw new Error("key_combo: 'keys' required (e.g. 'Ctrl+C', 'Alt+Tab')");

    const parts   = keys.split("+").map(s => s.trim());
    const mainKey = parts[parts.length - 1];
    const mods    = parts.slice(0, -1).map(m => m.toLowerCase());

    const opts = {
      key:      mainKey,
      ctrlKey:  mods.includes("ctrl")  || mods.includes("control"),
      altKey:   mods.includes("alt"),
      shiftKey: mods.includes("shift"),
      metaKey:  mods.includes("meta")  || mods.includes("cmd"),
      bubbles:  true,
      cancelable: true,
    };

    let target = document.activeElement || document.body;
    if (selector) {
      const el = await waitForElement(selector, timeoutMs);
      if (!el) throw new Error(`key_combo: element not found: ${selector}`);
      el.focus();
      target = el;
    }

    target.dispatchEvent(new KeyboardEvent("keydown", opts));
    target.dispatchEvent(new KeyboardEvent("keyup",   opts));
    await sleep(SETTLE_MS);
    return { keys, target: target.tagName };
  }

  async function actionCheck({ selector, timeoutMs = 5000 }) {
    const el = await waitForElement(selector, timeoutMs, true);
    if (!el) throw new Error(`check: element not found: ${selector}`);
    if (el.type !== "checkbox" && el.type !== "radio") {
      throw new Error(`check: element is not checkbox/radio (got type="${el.type}")`);
    }
    if (!el.checked) {
      el.click();
      await sleep(SETTLE_MS);
    }
    return { selector, checked: el.checked };
  }

  async function actionUncheck({ selector, timeoutMs = 5000 }) {
    const el = await waitForElement(selector, timeoutMs, true);
    if (!el) throw new Error(`uncheck: element not found: ${selector}`);
    if (el.type !== "checkbox") throw new Error(`uncheck: element is not a checkbox`);
    if (el.checked) {
      el.click();
      await sleep(SETTLE_MS);
    }
    return { selector, checked: el.checked };
  }

  function actionBack() {
    history.back();
    return Promise.resolve({ navigated: "back" });
  }

  function actionForward() {
    history.forward();
    return Promise.resolve({ navigated: "forward" });
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 👁  VISION ACTIONS — for people without sight
  // Читання структури сторінки, заголовки, посилання, форми, таблиці, ARIA
  // ══════════════════════════════════════════════════════════════════════════

  /**
   * get_page_text — all visible text in reading order, grouped by section.
   * This is the "read the whole screen" action.
   */
  function actionGetPageText() {
    function walkNode(node, chunks) {
      if (node.nodeType === Node.TEXT_NODE) {
        const t = node.textContent.trim();
        if (t) chunks.push(t);
        return;
      }
      if (node.nodeType !== Node.ELEMENT_NODE) return;
      const tag = node.tagName.toLowerCase();
      const style = window.getComputedStyle(node);
      if (style.display === "none" || style.visibility === "hidden") return;
      if (["script", "style", "noscript", "template"].includes(tag)) return;
      if (tag.match(/^h[1-6]$/)) {
        chunks.push(`\n[${tag.toUpperCase()}] ${node.textContent.trim()}\n`);
        return;
      }
      if (tag === "img") {
        const alt = node.getAttribute("alt");
        if (alt) chunks.push(`[Зображення: ${alt}]`);
        return;
      }
      if (tag === "a") {
        const text = node.textContent.trim();
        const href = node.getAttribute("href");
        if (text) chunks.push(`[Посилання: ${text}${href ? ` → ${href}` : ""}]`);
        return;
      }
      for (const child of node.childNodes) walkNode(child, chunks);
    }
    const chunks = [];
    walkNode(document.body, chunks);
    const text = chunks.join(" ").replace(/\s{3,}/g, "\n\n").trim();
    return Promise.resolve({ text, length: text.length });
  }

  /** get_headings — heading hierarchy for blind navigation */
  function actionGetHeadings() {
    const headings = [];
    document.querySelectorAll("h1,h2,h3,h4,h5,h6").forEach(h => {
      if (!isVisible(h)) return;
      headings.push({
        level:  parseInt(h.tagName[1], 10),
        tag:    h.tagName.toLowerCase(),
        text:   h.textContent.trim(),
        id:     h.id || null,
      });
    });
    return Promise.resolve({ headings, count: headings.length });
  }

  /** get_links — all visible links: where they go and their label */
  function actionGetLinks({ visibleOnly = true } = {}) {
    const links = [];
    document.querySelectorAll("a[href]").forEach(a => {
      if (visibleOnly && !isVisible(a)) return;
      links.push({
        text:   a.textContent.trim() || a.getAttribute("aria-label") || "[без тексту]",
        href:   a.href,
        title:  a.title || null,
        target: a.target || null,
      });
    });
    return Promise.resolve({ links, count: links.length });
  }

  /** get_images — all images with their descriptions */
  function actionGetImages({ visibleOnly = true } = {}) {
    const images = [];
    document.querySelectorAll("img, [role=img], svg[aria-label]").forEach(el => {
      if (visibleOnly && !isVisible(el)) return;
      images.push({
        alt:      el.getAttribute("alt") || null,
        src:      el.src || el.getAttribute("data-src") || null,
        title:    el.title || null,
        ariaLabel: el.getAttribute("aria-label") || null,
        hasAlt:   el.hasAttribute("alt"),
        width:    el.naturalWidth || el.clientWidth,
        height:   el.naturalHeight || el.clientHeight,
      });
    });
    return Promise.resolve({ images, count: images.length });
  }

  /**
   * get_forms — all form fields with their labels.
   * Critical for blind users to understand what to fill in.
   */
  function actionGetForms() {
    const fields = [];
    const FIELD_TAGS = "input:not([type=hidden]), textarea, select, [role=textbox], [role=combobox], [role=listbox]";
    document.querySelectorAll(FIELD_TAGS).forEach(el => {
      if (!isVisible(el)) return;

      // Find label via: aria-label → aria-labelledby → <label for> → parent <label>
      let label = el.getAttribute("aria-label") || "";
      if (!label && el.id) {
        const labelEl = document.querySelector(`label[for="${el.id}"]`);
        if (labelEl) label = labelEl.textContent.trim();
      }
      if (!label) {
        const parent = el.closest("label");
        if (parent) label = parent.textContent.trim();
      }
      if (!label) {
        const lb = el.getAttribute("aria-labelledby");
        if (lb) label = (document.getElementById(lb)?.textContent || "").trim();
      }

      // Error message
      const errId = el.getAttribute("aria-describedby") || el.getAttribute("aria-errormessage");
      const errorEl = errId ? document.getElementById(errId) : null;
      const error = errorEl ? errorEl.textContent.trim() : null;

      fields.push({
        tag:         el.tagName.toLowerCase(),
        type:        el.type || el.getAttribute("role") || "text",
        label:       label || el.placeholder || el.name || null,
        name:        el.name || null,
        id:          el.id || null,
        value:       el.value || null,
        placeholder: el.placeholder || null,
        required:    el.required || el.getAttribute("aria-required") === "true",
        disabled:    el.disabled || el.getAttribute("aria-disabled") === "true",
        invalid:     el.getAttribute("aria-invalid") === "true",
        error,
        options: el.tagName === "SELECT"
          ? Array.from(el.options).map(o => ({ value: o.value, text: o.text, selected: o.selected }))
          : null,
      });
    });
    return Promise.resolve({ fields, count: fields.length });
  }

  /**
   * get_landmarks — ARIA landmark regions.
   * Blind users navigate by landmarks (main, nav, search, etc.)
   */
  function actionGetLandmarks() {
    const LANDMARK_ROLES = ["banner","navigation","main","complementary","contentinfo",
                            "search","form","region","application"];
    const LANDMARK_TAGS  = { header: "banner", nav: "navigation", main: "main",
                              aside: "complementary", footer: "contentinfo" };

    const landmarks = [];
    document.querySelectorAll(
      "header,nav,main,aside,footer,[role]"
    ).forEach(el => {
      if (!isVisible(el)) return;
      const role = el.getAttribute("role") || LANDMARK_TAGS[el.tagName.toLowerCase()] || null;
      if (!role || !LANDMARK_ROLES.includes(role)) return;
      const label = el.getAttribute("aria-label") ||
                    (el.getAttribute("aria-labelledby") ? document.getElementById(el.getAttribute("aria-labelledby"))?.textContent?.trim() : null) ||
                    null;
      landmarks.push({
        role, label,
        tag:      el.tagName.toLowerCase(),
        id:       el.id || null,
        heading:  el.querySelector("h1,h2,h3,h4,h5,h6")?.textContent?.trim() || null,
      });
    });
    return Promise.resolve({ landmarks, count: landmarks.length });
  }

  /**
   * get_focused — what element currently has focus.
   * Blind users need to know where they are on the page.
   */
  function actionGetFocused() {
    const el = document.activeElement;
    if (!el || el === document.body) return Promise.resolve({ focused: null });
    return Promise.resolve({
      focused: {
        tag:      el.tagName.toLowerCase(),
        type:     el.type || null,
        id:       el.id || null,
        name:     el.name || null,
        text:     el.textContent?.trim().slice(0, 200) || null,
        value:    el.value || null,
        ariaLabel: el.getAttribute("aria-label") || null,
        role:     el.getAttribute("role") || null,
      },
    });
  }

  /**
   * find_all — find all elements matching a selector.
   * Returns array of descriptors (text, attrs) — for listing options, menu items, etc.
   */
  async function actionFindAll({ selector, limit = 50, timeoutMs = 3000 }) {
    if (!selector) throw new Error("find_all: 'selector' required");
    const el = await waitForElement(selector, timeoutMs);
    if (!el) return { items: [], count: 0 };

    const all = [...document.querySelectorAll(
      selector.startsWith("testid=")  ? `[data-testid="${selector.slice(7)}"]` :
      selector.startsWith("name=")    ? `[name="${selector.slice(5)}"]` :
      selector.startsWith("text=")    ? TEXT_TAGS.join(",") :
      selector
    )].filter(isVisible).slice(0, limit);

    const items = all.map(e => ({
      tag:      e.tagName.toLowerCase(),
      text:     e.textContent.trim().slice(0, 200),
      value:    e.value || null,
      id:       e.id || null,
      ariaLabel: e.getAttribute("aria-label") || null,
      href:     e.href || null,
      disabled: e.disabled || false,
    }));
    return { items, count: items.length };
  }

  /**
   * get_table — parse a <table> into a structured object.
   * Critical for blind users: screen readers need row/column context.
   */
  async function actionGetTable({ selector, timeoutMs = 5000 }) {
    const el = selector ? await waitForElement(selector, timeoutMs) : document.querySelector("table");
    if (!el) throw new Error(`get_table: table not found${selector ? `: ${selector}` : ""}`);
    const table = el.tagName === "TABLE" ? el : el.querySelector("table");
    if (!table) throw new Error("get_table: no <table> element found");

    const headers = [...(table.querySelectorAll("thead th, thead td") || [])].map(th => th.textContent.trim());
    const rows = [...table.querySelectorAll("tbody tr, tr")].map(tr => {
      return [...tr.querySelectorAll("td,th")].map(td => td.textContent.trim());
    }).filter(r => r.length > 0);

    return { headers, rows, rowCount: rows.length, colCount: headers.length || rows[0]?.length || 0 };
  }

  /**
   * get_aria_info — full ARIA info for a single element.
   * Name, role, description, state, live region, required, expanded…
   */
  async function actionGetAriaInfo({ selector, timeoutMs = 5000 }) {
    const el = selector ? await waitForElement(selector, timeoutMs) : document.activeElement;
    if (!el) throw new Error(`get_aria_info: element not found: ${selector}`);

    const describedBy = el.getAttribute("aria-describedby");
    const description = describedBy
      ? [...describedBy.split(" ")].map(id => document.getElementById(id)?.textContent?.trim()).filter(Boolean).join(". ")
      : null;

    return {
      role:        el.getAttribute("role") || el.tagName.toLowerCase(),
      name:        el.getAttribute("aria-label") || el.getAttribute("aria-labelledby")
                     ? document.getElementById(el.getAttribute("aria-labelledby"))?.textContent?.trim()
                     : el.textContent?.trim().slice(0, 200) || null,
      description,
      live:        el.getAttribute("aria-live") || null,
      atomic:      el.getAttribute("aria-atomic") || null,
      required:    el.getAttribute("aria-required") || null,
      invalid:     el.getAttribute("aria-invalid") || null,
      expanded:    el.getAttribute("aria-expanded") || null,
      selected:    el.getAttribute("aria-selected") || null,
      checked:     el.getAttribute("aria-checked") || null,
      disabled:    el.getAttribute("aria-disabled") || null,
      hidden:      el.getAttribute("aria-hidden") || null,
      level:       el.getAttribute("aria-level") || null,
      haspopup:    el.getAttribute("aria-haspopup") || null,
      valuemin:    el.getAttribute("aria-valuemin") || null,
      valuemax:    el.getAttribute("aria-valuemax") || null,
      valuenow:    el.getAttribute("aria-valuenow") || null,
      valuetext:   el.getAttribute("aria-valuetext") || null,
    };
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 👂 HEARING ACTIONS — for people without hearing
  // Управління медіа, витяг субтитрів, контроль гучності
  // ══════════════════════════════════════════════════════════════════════════

  /** get_media — info about all audio/video on the page */
  function actionGetMedia() {
    const mediaEls = [...document.querySelectorAll("video, audio")];
    if (!mediaEls.length) return Promise.resolve({ media: [], count: 0 });

    const media = mediaEls.map((el, i) => {
      const tracks = [...(el.textTracks || [])].map(t => ({
        kind:     t.kind,       // "subtitles" | "captions" | "descriptions"
        label:    t.label,
        language: t.language,
        mode:     t.mode,       // "showing" | "hidden" | "disabled"
      }));

      const sources = el.src
        ? [el.src]
        : [...el.querySelectorAll("source")].map(s => s.src);

      return {
        index:        i,
        tag:          el.tagName.toLowerCase(),
        src:          sources,
        duration:     el.duration || null,
        currentTime:  el.currentTime,
        paused:       el.paused,
        muted:        el.muted,
        volume:       el.volume,
        playbackRate: el.playbackRate,
        readyState:   el.readyState,   // 0=no data, 4=ready
        tracks,
        hasCaptions:  tracks.some(t => t.kind === "captions" || t.kind === "subtitles"),
        selector:     el.id ? `#${el.id}` : `${el.tagName.toLowerCase()}:nth-of-type(${i + 1})`,
      };
    });
    return Promise.resolve({ media, count: media.length });
  }

  async function actionPlayMedia({ selector, timeoutMs = 5000 }) {
    const el = selector
      ? await waitForElement(selector, timeoutMs)
      : document.querySelector("video") || document.querySelector("audio");
    if (!el) throw new Error(`play_media: media element not found${selector ? `: ${selector}` : ""}`);
    await el.play();
    return { playing: !el.paused, currentTime: el.currentTime };
  }

  async function actionPauseMedia({ selector, timeoutMs = 5000 }) {
    const el = selector
      ? await waitForElement(selector, timeoutMs)
      : document.querySelector("video") || document.querySelector("audio");
    if (!el) throw new Error(`pause_media: media element not found${selector ? `: ${selector}` : ""}`);
    el.pause();
    return { paused: el.paused, currentTime: el.currentTime };
  }

  async function actionSetVolume({ selector, volume, mute, timeoutMs = 5000 }) {
    const el = selector
      ? await waitForElement(selector, timeoutMs)
      : document.querySelector("video") || document.querySelector("audio");
    if (!el) throw new Error("set_volume: media element not found");
    if (volume !== undefined) el.volume = Math.max(0, Math.min(1, Number(volume)));
    if (mute !== undefined) el.muted = Boolean(mute);
    return { volume: el.volume, muted: el.muted };
  }

  /**
   * get_captions — extract visible caption / subtitle cues from a video.
   * For deaf users: "what did the video say?"
   */
  async function actionGetCaptions({ selector, kind = "captions", timeoutMs = 5000 }) {
    const el = selector
      ? await waitForElement(selector, timeoutMs)
      : document.querySelector("video");
    if (!el) throw new Error("get_captions: video element not found");

    const cues = [];
    const tracks = [...(el.textTracks || [])];

    for (const track of tracks) {
      const wantedKinds = kind === "any"
        ? ["captions","subtitles","descriptions","metadata"]
        : [kind];
      if (!wantedKinds.includes(track.kind)) continue;

      // Temporarily enable to get cues
      const prevMode = track.mode;
      track.mode = "showing";
      await sleep(80); // let browser parse VTT

      if (track.cues) {
        for (const cue of track.cues) {
          cues.push({
            start:    cue.startTime,
            end:      cue.endTime,
            text:     cue.text?.replace(/<[^>]+>/g, "").trim() || "",
            track:    track.label || track.language || track.kind,
          });
        }
      }

      if (prevMode !== "showing") track.mode = prevMode;
    }

    const transcript = cues.map(c => c.text).filter(Boolean).join("\n");
    return { cues, transcript, count: cues.length, hasCaptions: cues.length > 0 };
  }

  /**
   * enable_captions — turn on closed captions on a video.
   * Finds best track: matching language → any captions → any subtitles
   */
  async function actionEnableCaptions({ selector, language = "uk", timeoutMs = 5000 }) {
    const el = selector
      ? await waitForElement(selector, timeoutMs)
      : document.querySelector("video");
    if (!el) throw new Error("enable_captions: video element not found");

    const tracks = [...(el.textTracks || [])];
    if (!tracks.length) return { enabled: false, reason: "No text tracks available" };

    // Priority: exact lang match > any captions > any subtitles > first
    const byLang  = tracks.filter(t => t.language?.startsWith(language) && ["captions","subtitles"].includes(t.kind));
    const capts   = tracks.filter(t => t.kind === "captions");
    const subs    = tracks.filter(t => t.kind === "subtitles");
    const chosen  = byLang[0] || capts[0] || subs[0] || tracks[0];

    // Disable all others, enable chosen
    tracks.forEach(t => { t.mode = "disabled"; });
    chosen.mode = "showing";
    await sleep(80);

    return {
      enabled: true,
      track: { kind: chosen.kind, label: chosen.label, language: chosen.language },
    };
  }

  // ── Action dispatch map ────────────────────────────────────────────────────

  const ACTIONS = {
    // ── Base interaction ──────────────────────────────────────────────────────
    click:           actionClick,
    type:            actionType,
    select:          actionSelect,
    wait_for:        actionWaitFor,
    wait_for_hidden: actionWaitForHidden,
    assert:          actionAssert,
    get_text:        actionGetText,
    get_attr:        actionGetAttr,
    get_value:       actionGetValue,
    get_url:         actionGetUrl,
    get_title:       actionGetTitle,
    scroll:          actionScroll,
    hover:           actionHover,
    focus:           actionFocus,
    clear:           actionClear,
    key_press:       actionKeyPress,
    screenshot:      actionScreenshot,
    eval:            actionEval,

    // 🤲 Motor (hands) ─────────────────────────────────────────────────────────
    double_click:    actionDoubleClick,
    right_click:     actionRightClick,
    drag:            actionDrag,
    key_combo:       actionKeyCombo,  // "Ctrl+C", "Alt+Tab", "Ctrl+Shift+T"
    check:           actionCheck,
    uncheck:         actionUncheck,
    back:            actionBack,
    forward:         actionForward,

    // 👁  Vision (eyes) ─────────────────────────────────────────────────────────
    get_page_text:   actionGetPageText,   // read entire page as text
    get_headings:    actionGetHeadings,   // h1-h6 structure for navigation
    get_links:       actionGetLinks,      // all links with href + text
    get_images:      actionGetImages,     // all images with alt text
    get_forms:       actionGetForms,      // all form fields with labels + errors
    get_landmarks:   actionGetLandmarks,  // ARIA landmarks (main, nav, search…)
    get_focused:     actionGetFocused,    // currently focused element
    find_all:        actionFindAll,       // all matching elements as array
    get_table:       actionGetTable,      // parse table into rows/headers
    get_aria_info:   actionGetAriaInfo,   // full ARIA state of element

    // 👂 Hearing (ears) ─────────────────────────────────────────────────────────
    get_media:       actionGetMedia,      // info about all audio/video
    play_media:      actionPlayMedia,
    pause_media:     actionPauseMedia,
    set_volume:      actionSetVolume,
    get_captions:    actionGetCaptions,   // extract subtitle/caption text
    enable_captions: actionEnableCaptions,// turn on closed captions
  };

  // ── Execute with error wrapping ────────────────────────────────────────────

  async function execute(command) {
    const { action, ...params } = command;
    if (!action) return { ok: false, error: "Missing 'action' field" };

    const fn = ACTIONS[action];
    if (!fn) return { ok: false, error: `Unknown action: "${action}". Known: ${Object.keys(ACTIONS).join(", ")}` };

    try {
      const result = await fn(params);
      dbg(`✓ ${action}`, result);
      return { ok: true, result };
    } catch (e) {
      dbg(`✗ ${action}`, e.message);
      return { ok: false, error: e.message || String(e) };
    }
  }

  // ── Message listener ───────────────────────────────────────────────────────

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg.type === "HANDS_PING") {
      sendResponse({ pong: true });
      return false;
    }
    if (msg.type !== "HANDS_CMD") return false;
    execute(msg.command).then(sendResponse);
    return true; // async response
  });

  // ── Helpers ────────────────────────────────────────────────────────────────

  function sleep(ms) {
    return new Promise(r => setTimeout(r, Math.max(0, ms)));
  }

  dbg(`v2 loaded on ${location.href} — ${Object.keys(ACTIONS).length} actions ready`);
})();

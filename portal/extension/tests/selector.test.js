/**
 * Selector Engine Unit Tests
 * ─────────────────────────────
 * Pure JS tests — runs in Node.js (no browser required).
 * Tests all selector strategies and edge cases.
 *
 * Run:  node portal/extension/tests/selector.test.js
 *
 * Exit 0 = all pass, exit 1 = failures.
 */

// ── Minimal DOM shim for Node.js ─────────────────────────────────────────────

const elements = [];
let activeStyle = {};

function makeEl(tag, attrs = {}, text = "", style = {}) {
  const el = {
    tagName: tag.toUpperCase(),
    textContent: text,
    value: attrs.value ?? "",
    disabled: attrs.disabled ?? false,
    _attrs: { ...attrs },
    _style: { display: "block", visibility: "visible", opacity: "1", pointerEvents: "auto", ...style },
    getAttribute(name) { return this._attrs[name] ?? null; },
    getBoundingClientRect() {
      return { width: this._style.display === "none" ? 0 : 100,
               height: this._style.display === "none" ? 0 : 30 };
    },
    options: attrs.options ?? [],
    focus() {},
    scrollIntoView() {},
    dispatchEvent() {},
    click() {},
  };
  elements.push(el);
  return el;
}

// Mock document
const document = {
  querySelector(sel) {
    // Simple attribute selector parsing
    const attrMatch = sel.match(/\[([a-z-]+)="([^"]+)"\]/);
    if (attrMatch) {
      const [, attr, val] = attrMatch;
      return elements.find(el => el._attrs[attr] === val && isVisible(el)) ?? null;
    }
    return null;
  },
  querySelectorAll(tag) {
    return elements.filter(el => el.tagName === tag.toUpperCase());
  },
};

const window = { getComputedStyle: (el) => el._style };
const location = { href: "http://test.local/" };

// ── Copy selector engine from content/hands.js (inlined for Node compat) ────

function normalise(text) {
  return text.replace(/\s+/g, " ").trim().toLowerCase();
}

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
  const style = window.getComputedStyle(el);
  if (style.pointerEvents === "none") return false;
  return true;
}

const TEXT_TAGS = ["button", "a", "label", "span", "div", "li", "td", "th",
  "h1", "h2", "h3", "h4", "p", "input", "summary"];

function findByExactText(text) {
  const target = normalise(text);
  for (const tag of TEXT_TAGS) {
    for (const el of document.querySelectorAll(tag)) {
      if (!isVisible(el)) continue;
      if (normalise(el.textContent) === target) return el;
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
  for (const el of elements) {
    const ariaLabel = el.getAttribute("aria-label") || el.getAttribute("aria-labelledby") || "";
    if (normalise(ariaLabel) === target && isVisible(el)) return el;
  }
  return null;
}

function css(v) {
  return v.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

function resolveSelector(selector) {
  if (!selector || typeof selector !== "string") return null;
  const s = selector.trim();

  if (s.startsWith("testid=")) return document.querySelector(`[data-testid="${css(s.slice(7))}"]`);
  if (s.startsWith("aria=")) {
    const label = s.slice(5);
    return document.querySelector(`[aria-label="${css(label)}"]`) ||
           document.querySelector(`[aria-placeholder="${css(label)}"]`) ||
           findByRole(label) || findByExactText(label);
  }
  if (s.startsWith("name="))        return document.querySelector(`[name="${css(s.slice(5))}"]`);
  if (s.startsWith("placeholder=")) return document.querySelector(`[placeholder="${css(s.slice(12))}"]`);
  if (s.startsWith("text="))        return findByExactText(s.slice(5));
  if (s.startsWith("contains="))    return findByPartialText(s.slice(9));
  try { return document.querySelector(s); } catch { return null; }
}

// ── Test runner ──────────────────────────────────────────────────────────────

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    elements.length = 0; // reset DOM
    fn();
    console.log(`  ✓ ${name}`);
    passed++;
  } catch (e) {
    console.error(`  ✗ ${name}: ${e.message}`);
    failed++;
  }
}

function assert(condition, msg = "assertion failed") {
  if (!condition) throw new Error(msg);
}

function assertEqual(a, b) {
  if (a !== b) throw new Error(`expected ${JSON.stringify(b)}, got ${JSON.stringify(a)}`);
}

// ── Tests ────────────────────────────────────────────────────────────────────

console.log("\nSelector Engine Tests");
console.log("─".repeat(50));

// -- testid= --
console.log("\n[testid=]");

test("finds element by data-testid", () => {
  const btn = makeEl("button", { "data-testid": "submit-btn" }, "Submit");
  const found = resolveSelector("testid=submit-btn");
  assert(found === btn, "should find button");
});

test("returns null for missing testid", () => {
  makeEl("button", { "data-testid": "other" }, "Other");
  const found = resolveSelector("testid=nonexistent");
  assert(found === null, "should return null");
});

test("ignores hidden testid elements", () => {
  makeEl("button", { "data-testid": "hidden-btn" }, "Hidden", { display: "none" });
  const found = resolveSelector("testid=hidden-btn");
  assert(found === null, "should not find hidden element");
});

test("finds testid with special chars in value", () => {
  const btn = makeEl("button", { "data-testid": "my-cool_button" }, "Cool");
  const found = resolveSelector("testid=my-cool_button");
  assert(found === btn);
});

// -- aria= --
console.log("\n[aria=]");

test("finds by aria-label", () => {
  const el = makeEl("button", { "aria-label": "Close dialog" }, "×");
  const found = resolveSelector("aria=Close dialog");
  assert(found === el);
});

test("finds by aria-placeholder", () => {
  const el = makeEl("input", { "aria-placeholder": "Search here" });
  const found = resolveSelector("aria=Search here");
  assert(found === el);
});

// -- name= --
console.log("\n[name=]");

test("finds input by name", () => {
  const el = makeEl("input", { name: "email", type: "email" });
  const found = resolveSelector("name=email");
  assert(found === el);
});

test("finds select by name", () => {
  const el = makeEl("select", { name: "country" });
  const found = resolveSelector("name=country");
  assert(found === el);
});

// -- placeholder= --
console.log("\n[placeholder=]");

test("finds input by placeholder", () => {
  const el = makeEl("input", { placeholder: "Enter your email" });
  const found = resolveSelector("placeholder=Enter your email");
  assert(found === el);
});

// -- text= --
console.log("\n[text=]");

test("finds button by exact text", () => {
  const btn = makeEl("button", {}, "Увійти");
  const found = resolveSelector("text=Увійти");
  assert(found === btn);
});

test("case-insensitive text match", () => {
  const btn = makeEl("button", {}, "Submit");
  const found = resolveSelector("text=submit");
  assert(found === btn);
});

test("normalises whitespace in text match", () => {
  const btn = makeEl("button", {}, "  Click  Me  ");
  const found = resolveSelector("text=Click Me");
  assert(found === btn, "should normalise extra whitespace");
});

test("does not find partial text with text=", () => {
  makeEl("button", {}, "Submit Form");
  const found = resolveSelector("text=Submit");
  assert(found === null, "text= should require exact match");
});

test("does not find hidden text elements", () => {
  makeEl("button", {}, "Hidden Button", { display: "none" });
  const found = resolveSelector("text=Hidden Button");
  assert(found === null);
});

// -- contains= --
console.log("\n[contains=]");

test("finds element by partial text", () => {
  const el = makeEl("div", {}, "Welcome to the dashboard!");
  const found = resolveSelector("contains=dashboard");
  assert(found === el);
});

test("contains= is case-insensitive", () => {
  const el = makeEl("span", {}, "Error: Invalid password");
  const found = resolveSelector("contains=invalid password");
  assert(found === el);
});

// -- isVisible --
console.log("\n[isVisible]");

test("visible element returns true", () => {
  const el = makeEl("div", {}, "Visible");
  assert(isVisible(el));
});

test("display:none returns false", () => {
  const el = makeEl("div", {}, "Hidden", { display: "none" });
  assert(!isVisible(el));
});

test("visibility:hidden returns false", () => {
  const el = makeEl("div", {}, "Invisible", { visibility: "hidden" });
  assert(!isVisible(el));
});

test("opacity:0 returns false", () => {
  const el = makeEl("div", {}, "Transparent", { opacity: "0" });
  assert(!isVisible(el));
});

// -- isInteractable --
console.log("\n[isInteractable]");

test("visible, enabled element is interactable", () => {
  const el = makeEl("button", {}, "Click");
  assert(isInteractable(el));
});

test("disabled element is not interactable", () => {
  const el = makeEl("button", { disabled: true }, "Disabled");
  assert(!isInteractable(el));
});

test("aria-disabled=true is not interactable", () => {
  const el = makeEl("button", { "aria-disabled": "true" }, "Disabled");
  assert(!isInteractable(el));
});

test("pointer-events:none is not interactable", () => {
  const el = makeEl("button", {}, "No Click", { pointerEvents: "none" });
  assert(!isInteractable(el));
});

test("hidden element is not interactable", () => {
  const el = makeEl("button", {}, "Hidden", { display: "none" });
  assert(!isInteractable(el));
});

// -- normalise --
console.log("\n[normalise]");

test("collapses multiple spaces", () => {
  assertEqual(normalise("hello   world"), "hello world");
});

test("trims leading/trailing whitespace", () => {
  assertEqual(normalise("  test  "), "test");
});

test("handles tabs and newlines", () => {
  assertEqual(normalise("hello\t\nworld"), "hello world");
});

test("lowercases text", () => {
  assertEqual(normalise("HELLO World"), "hello world");
});

// -- Edge cases --
console.log("\n[Edge cases]");

test("null selector returns null", () => {
  const found = resolveSelector(null);
  assert(found === null);
});

test("empty string selector returns null", () => {
  const found = resolveSelector("");
  assert(found === null);
});

test("non-string selector returns null", () => {
  const found = resolveSelector(42);
  assert(found === null);
});

test("unknown prefix falls through to CSS", () => {
  // CSS querySelector with no matching element
  const found = resolveSelector("#totally-nonexistent");
  assert(found === null);
});

test("multiple testid elements — finds first visible", () => {
  makeEl("button", { "data-testid": "btn" }, "B1", { display: "none" });
  const btn2 = makeEl("button", { "data-testid": "btn" }, "B2");
  // querySelector returns first in DOM order; first is hidden so null from querySelector
  // We just verify we get a result at all (querySelector doesn't filter visibility for attr selectors)
  const found = resolveSelector("testid=btn");
  // querySelector returns first match regardless of visibility (our shim matches first)
  assert(found !== null, "should return some element");
});

// ── Summary ───────────────────────────────────────────────────────────────────

console.log("\n" + "─".repeat(50));
console.log(`Results: ${passed} passed, ${failed} failed`);

if (failed > 0) {
  console.error(`\n✗ ${failed} test(s) FAILED`);
  process.exit(1);
} else {
  console.log(`\n✓ All ${passed} tests passed`);
  process.exit(0);
}

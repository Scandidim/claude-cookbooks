/**
 * ActionLog v2 — chrome.storage.local with write queue (no race conditions)
 *
 * Problem fixed: concurrent add() calls used to race and lose entries.
 * Solution: serialize writes through a microtask queue.
 */
export class ActionLog {
  static KEY = "hands_action_log";
  static MAX = 500;

  #queue = Promise.resolve(); // serializes all writes

  getAll() {
    return chrome.storage.local.get(ActionLog.KEY).then(
      data => data[ActionLog.KEY] ?? []
    );
  }

  add(entry) {
    // Enqueue write — each call waits for the previous one to finish
    this.#queue = this.#queue.then(async () => {
      const entries = await this.getAll();
      entries.push({
        ts: new Date().toISOString(),
        ...entry,
      });
      const pruned = entries.slice(-ActionLog.MAX);
      await chrome.storage.local.set({ [ActionLog.KEY]: pruned });
    });
    return this.#queue;
  }

  clear() {
    this.#queue = this.#queue.then(() =>
      chrome.storage.local.remove(ActionLog.KEY)
    );
    return this.#queue;
  }

  async last(n = 20) {
    const all = await this.getAll();
    return all.slice(-n);
  }
}

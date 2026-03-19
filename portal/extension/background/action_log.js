/**
 * ActionLog — persists step results to chrome.storage.local
 * Max 500 entries; oldest entries are pruned automatically.
 */
export class ActionLog {
  static KEY = "hands_action_log";
  static MAX = 500;

  async getAll() {
    const data = await chrome.storage.local.get(ActionLog.KEY);
    return data[ActionLog.KEY] ?? [];
  }

  async add(entry) {
    const entries = await this.getAll();
    entries.push({ ts: new Date().toISOString(), ...entry });
    // Prune oldest
    const pruned = entries.slice(-ActionLog.MAX);
    await chrome.storage.local.set({ [ActionLog.KEY]: pruned });
  }

  async clear() {
    await chrome.storage.local.remove(ActionLog.KEY);
  }
}

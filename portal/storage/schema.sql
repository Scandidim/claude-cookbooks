-- AI Portal: Database Schema
-- Local SQLite storage for multi-agent portal system

CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    source      TEXT NOT NULL,         -- 'telegram', 'api', 'scheduler'
    source_id   TEXT,                  -- chat_id, user_id, etc.
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending, routing, running, done, failed
    agent       TEXT,                  -- assigned agent name
    input       TEXT NOT NULL,         -- raw user input
    output      TEXT,                  -- final artifact / response
    metadata    TEXT                   -- JSON: extra context
);

CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    source      TEXT NOT NULL,
    source_id   TEXT NOT NULL,         -- telegram chat_id etc.
    context     TEXT,                  -- JSON: conversation history
    active      INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS artifacts (
    id          TEXT PRIMARY KEY,
    task_id     TEXT REFERENCES tasks(id),
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    type        TEXT NOT NULL,         -- 'document', 'page', 'report', 'crm_lead', 'message'
    title       TEXT,
    content     TEXT,
    url         TEXT,                  -- external URL (Tilda page, Google Doc, etc.)
    metadata    TEXT                   -- JSON
);

CREATE TABLE IF NOT EXISTS logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    task_id     TEXT,
    agent       TEXT,
    level       TEXT DEFAULT 'info',   -- debug, info, warning, error
    message     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_status   ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_source   ON tasks(source, source_id);
CREATE INDEX IF NOT EXISTS idx_logs_task      ON logs(task_id);
CREATE INDEX IF NOT EXISTS idx_sessions_src   ON sessions(source, source_id);

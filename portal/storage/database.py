"""
Local SQLite database for the AI portal.
Stores tasks, sessions, artifacts, and agent logs.
"""

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent / "portal.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Create tables from schema if they don't exist."""
    schema = SCHEMA_PATH.read_text()
    with get_connection() as conn:
        conn.executescript(schema)


# ── Tasks ──────────────────────────────────────────────────────────────────────


def create_task(source: str, source_id: str, input_text: str, metadata: dict | None = None) -> str:
    task_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO tasks (id, created_at, updated_at, source, source_id, status, input, metadata)
               VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (task_id, now, now, source, source_id, input_text, json.dumps(metadata or {})),
        )
    return task_id


def update_task(task_id: str, **fields: Any) -> None:
    fields["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [task_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)


def get_task(task_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return dict(row) if row else None


def list_tasks(
    source_id: str | None = None, status: str | None = None, limit: int = 50
) -> list[dict]:
    query = "SELECT * FROM tasks WHERE 1=1"
    params: list[Any] = []
    if source_id:
        query += " AND source_id = ?"
        params.append(source_id)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


# ── Artifacts ──────────────────────────────────────────────────────────────────


def save_artifact(
    task_id: str,
    artifact_type: str,
    title: str,
    content: str = "",
    url: str = "",
    metadata: dict | None = None,
) -> str:
    artifact_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO artifacts (id, task_id, created_at, type, title, content, url, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                artifact_id,
                task_id,
                now,
                artifact_type,
                title,
                content,
                url,
                json.dumps(metadata or {}),
            ),
        )
    return artifact_id


def get_artifacts(task_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM artifacts WHERE task_id = ? ORDER BY created_at", (task_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── Sessions ───────────────────────────────────────────────────────────────────


def get_or_create_session(source: str, source_id: str) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE source = ? AND source_id = ? AND active = 1",
            (source, source_id),
        ).fetchone()
        if row:
            return dict(row)
        session_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO sessions (id, created_at, source, source_id, context) VALUES (?, ?, ?, ?, ?)",
            (session_id, now, source, source_id, json.dumps([])),
        )
        return {"id": session_id, "source": source, "source_id": source_id, "context": "[]"}


def update_session_context(session_id: str, context: list) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE sessions SET context = ? WHERE id = ?",
            (json.dumps(context), session_id),
        )


# ── Logs ───────────────────────────────────────────────────────────────────────


def log(task_id: str | None, agent: str, message: str, level: str = "info") -> None:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO logs (created_at, task_id, agent, level, message) VALUES (?, ?, ?, ?, ?)",
            (now, task_id, agent, level, message),
        )


def get_logs(task_id: str, limit: int = 100) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM logs WHERE task_id = ? ORDER BY created_at LIMIT ?",
            (task_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]

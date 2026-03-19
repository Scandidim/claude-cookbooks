"""
Orchestrator
────────────
The central brain of the AI portal.

Flow:
  1. Receives a raw user message (from Telegram, API, scheduler, etc.)
  2. Calls RegistrarAgent to classify intent and choose the right agent
  3. Dispatches to the correct specialist agent
  4. Optionally pushes the result to external services (Google, Tilda, KOMMO)
  5. Returns the final response string to the caller

Usage:
    from portal.orchestrator import Orchestrator
    orch = Orchestrator()
    result = orch.handle(source="telegram", source_id="12345678", text="Write me an ad for ...")
"""

from __future__ import annotations

import json

from portal import config  # noqa: F401 — ensures .env is loaded
from portal.agents import CRMConnectorAgent, ExecutorAgent, MarketBotAgent, RegistrarAgent
from portal.storage import (
    create_task,
    get_artifacts,
    init_db,
    log,
    save_artifact,
    update_task,
)

# Lazy imports for integrations (only used if configured)
_google = None
_tilda = None


def _get_google():
    global _google
    if _google is None and config.GOOGLE_SERVICE_ACCOUNT_FILE:
        from portal.integrations.google_workspace import GoogleWorkspace

        _google = GoogleWorkspace()
    return _google


def _get_tilda():
    global _tilda
    if _tilda is None and config.TILDA_PUBLIC_KEY:
        from portal.integrations.tilda import TildaAPI

        _tilda = TildaAPI()
    return _tilda


class Orchestrator:
    """Main portal orchestrator — single entry point for all agent tasks."""

    def __init__(self) -> None:
        init_db()
        self._registrar = RegistrarAgent()
        self._executor = ExecutorAgent()
        self._market_bot = MarketBotAgent()
        self._crm = CRMConnectorAgent()

    # ── Public API ─────────────────────────────────────────────────────────────

    def handle(self, source: str, source_id: str, text: str) -> str:
        """Process a user message end-to-end. Returns reply text."""
        task_id = create_task(source=source, source_id=source_id, input_text=text)
        log(task_id, "orchestrator", f"Task created from {source}/{source_id}")

        try:
            update_task(task_id, status="routing")
            routing = self._registrar.classify(task_id, text)
            agent_name = routing.get("agent", "executor")
            intent = routing.get("intent", text[:200])
            extracted = routing.get("extracted", {})

            update_task(task_id, status="running", agent=agent_name, metadata=json.dumps(routing))
            log(task_id, "orchestrator", f"Dispatching to '{agent_name}'")

            result = self._dispatch(task_id, agent_name, intent, text, extracted)

            update_task(task_id, status="done", output=result[:2000])
            log(task_id, "orchestrator", "Task completed")
            return result

        except Exception as e:
            update_task(task_id, status="failed", output=str(e))
            log(task_id, "orchestrator", f"Task failed: {e}", "error")
            return f"Sorry, an error occurred: {e}"

    def get_task_status(self, task_id: str) -> str:
        """Return a human-readable task status summary."""
        from portal.storage import get_task

        task = get_task(task_id)
        if not task:
            return f"Task {task_id} not found."
        artifacts = get_artifacts(task_id)
        lines = [
            f"Task: {task_id[:8]}...",
            f"Status: {task['status']}",
            f"Agent: {task.get('agent', '—')}",
            f"Input: {task['input'][:100]}",
        ]
        if task.get("output"):
            lines.append(f"Output preview: {task['output'][:200]}")
        if artifacts:
            lines.append(f"Artifacts: {len(artifacts)}")
            for a in artifacts:
                url_part = f" → {a['url']}" if a.get("url") else ""
                lines.append(f"  • [{a['type']}] {a['title'][:80]}{url_part}")
        return "\n".join(lines)

    # ── Dispatch ───────────────────────────────────────────────────────────────

    def _dispatch(
        self, task_id: str, agent_name: str, intent: str, text: str, extracted: dict
    ) -> str:
        if agent_name == "market_bot":
            return self._market_bot.run(task_id, intent, text, extracted)

        elif agent_name == "crm_action":
            return self._crm.run(task_id, intent, text, extracted)

        elif agent_name == "google_doc":
            result = self._executor.run(task_id, intent, text, extracted)
            self._push_to_google(task_id, intent, result)
            return result

        elif agent_name == "tilda_page":
            result = self._executor.run(task_id, intent, text, extracted)
            self._push_to_tilda(task_id, intent, result)
            return result

        elif agent_name == "chitchat":
            # Lightweight chitchat — use executor model
            return self._executor.run(task_id, intent, text, extracted)

        else:
            # Default: executor
            return self._executor.run(task_id, intent, text, extracted)

    # ── Optional push-to-external ──────────────────────────────────────────────

    def _push_to_google(self, task_id: str, title: str, content: str) -> None:
        google = _get_google()
        if not google:
            log(
                task_id,
                "orchestrator",
                "Google Workspace not configured — skipping upload",
                "warning",
            )
            return
        try:
            doc_url = google.create_doc(title=title, content=content)
            save_artifact(task_id=task_id, artifact_type="google_doc", title=title, url=doc_url)
            log(task_id, "orchestrator", f"Google Doc created: {doc_url}")
        except Exception as e:
            log(task_id, "orchestrator", f"Google upload failed: {e}", "error")

    def _push_to_tilda(self, task_id: str, title: str, content: str) -> None:
        tilda = _get_tilda()
        if not tilda:
            log(task_id, "orchestrator", "Tilda not configured — skipping upload", "warning")
            return
        try:
            page_url = tilda.create_page(title=title, content=content)
            save_artifact(task_id=task_id, artifact_type="tilda_page", title=title, url=page_url)
            log(task_id, "orchestrator", f"Tilda page created: {page_url}")
        except Exception as e:
            log(task_id, "orchestrator", f"Tilda upload failed: {e}", "error")

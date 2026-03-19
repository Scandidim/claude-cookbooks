"""
Executor Agent
──────────────
Produces ready artifacts from user instructions:
  • Written documents (reports, articles, scripts, briefs)
  • Structured data (JSON, CSV tables)
  • Code snippets
  • Any other text-based artifact

Returns the artifact text plus metadata so the Orchestrator can
save it to the DB and optionally push it to Google Docs / Tilda.
"""

from __future__ import annotations

import anthropic

from portal import config
from portal.storage import log, save_artifact

SYSTEM_PROMPT = """You are the Executor Agent — a highly skilled content creator.
Your job is to produce a complete, ready-to-use artifact based on the user's request.

Guidelines:
- Deliver the full artifact, not a plan or outline (unless explicitly asked)
- Use clear structure: headings, bullet points, tables where helpful
- Match the language of the user's request (Ukrainian, English, etc.)
- If the request is ambiguous, make reasonable assumptions and note them briefly
- End with: <artifact_type>document|report|code|table|other</artifact_type>
"""


class ExecutorAgent:
    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    def run(self, task_id: str, intent: str, user_input: str, extracted: dict) -> str:
        """Generate the artifact and save it. Returns artifact text."""
        log(task_id, "executor", f"Generating artifact for: {intent}")

        context = ""
        if extracted:
            context = f"\n\nExtracted context: {extracted}"

        response = self._client.messages.create(
            model=config.MODEL_EXECUTOR,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_input + context}],
            temperature=0.3,
        )
        artifact_text = response.content[0].text

        # Parse artifact type tag if present
        import re

        m = re.search(r"<artifact_type>(.*?)</artifact_type>", artifact_text, re.DOTALL)
        artifact_type = m.group(1).strip() if m else "document"
        clean_text = re.sub(
            r"<artifact_type>.*?</artifact_type>", "", artifact_text, flags=re.DOTALL
        ).strip()

        save_artifact(
            task_id=task_id,
            artifact_type=artifact_type,
            title=intent[:200],
            content=clean_text,
        )
        log(task_id, "executor", f"Artifact saved ({artifact_type}, {len(clean_text)} chars)")
        return clean_text

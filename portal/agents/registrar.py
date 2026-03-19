"""
Registrar Agent
───────────────
Receives raw user input, classifies the intent, extracts structured data,
and returns a routing decision for the Orchestrator.

Uses the cheapest model (Haiku) since this is a high-frequency classification step.
"""

import json
import re

import anthropic

from portal import config
from portal.storage import log

SYSTEM_PROMPT = """You are the Registrar Agent in an AI portal.
Your job is to analyse the user's request and return a JSON routing decision.

Available agent types:
- executor     → produce a concrete artifact (document, website page, report, image description)
- market_bot   → research markets, find opportunities, write ad copy, analyse competitors
- crm_action   → create/update leads or contacts in a CRM
- tilda_page   → create or update a Tilda website page
- google_doc   → create or update a Google Docs / Sheets document
- chitchat     → general conversation, questions, clarifications

Respond ONLY with valid JSON in this exact format:
{
  "agent": "<agent_type>",
  "intent": "<one sentence summary of what the user wants>",
  "priority": "high" | "normal" | "low",
  "extracted": { <any key data extracted from the input: name, topic, deadline, etc.> }
}"""


class RegistrarAgent:
    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    def classify(self, task_id: str, user_input: str) -> dict:
        """Classify the input and return routing data."""
        log(task_id, "registrar", f"Classifying: {user_input[:120]}")

        response = self._client.messages.create(
            model=config.MODEL_REGISTRAR,
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_input}],
            temperature=0.0,
        )
        raw = response.content[0].text.strip()

        # Extract JSON even if model adds extra text
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            log(task_id, "registrar", f"Bad JSON from model: {raw}", "warning")
            return {
                "agent": "executor",
                "intent": user_input[:200],
                "priority": "normal",
                "extracted": {},
            }

        result = json.loads(match.group())
        log(task_id, "registrar", f"Routed to: {result.get('agent')} — {result.get('intent')}")
        return result

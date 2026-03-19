"""
CRM Connector Agent
────────────────────
Handles KOMMO CRM actions:
  • Create leads from Telegram messages or user requests
  • Update contact data
  • Add notes and tasks
  • Search for existing contacts

Works by parsing user intent and calling the KOMMO REST API via
the kommo_crm integration module.
"""

from __future__ import annotations

import json
import re

import anthropic

from portal import config
from portal.storage import log, save_artifact

SYSTEM_PROMPT = """You are the CRM Connector Agent.
Parse the user's request and return a JSON action for KOMMO CRM.

Supported actions:
- create_lead   → create a new lead
- update_lead   → update existing lead
- create_contact → create a new contact
- add_note      → add a note to lead/contact
- search        → search leads or contacts

Respond ONLY with valid JSON:
{
  "action": "<action_name>",
  "data": {
    "name": "...",         // lead/contact name
    "phone": "...",        // optional
    "email": "...",        // optional
    "pipeline_id": null,   // null = default pipeline
    "status_id": null,     // null = first status
    "note": "...",         // for add_note or extra context
    "tags": [],            // optional list of tags
    "query": "..."         // for search action
  }
}"""


class CRMConnectorAgent:
    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    def run(self, task_id: str, intent: str, user_input: str, extracted: dict) -> str:
        """Parse intent and execute CRM action. Returns status message."""
        log(task_id, "crm_connector", f"CRM task: {intent}")

        # Use Claude to parse what CRM action is needed
        response = self._client.messages.create(
            model=config.MODEL_REGISTRAR,
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_input}],
            temperature=0.0,
        )
        raw = response.content[0].text.strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return "Could not parse CRM action from request."

        action_spec = json.loads(match.group())
        action = action_spec.get("action", "create_lead")
        data = action_spec.get("data", {})

        log(task_id, "crm_connector", f"CRM action: {action} — {data.get('name', '')}")

        # Execute via KOMMO integration
        result_msg = self._execute_crm(task_id, action, data)

        save_artifact(
            task_id=task_id,
            artifact_type="crm_lead",
            title=f"CRM: {action} — {data.get('name', 'unknown')}",
            content=result_msg,
            metadata={"action": action, "data": data},
        )
        return result_msg

    def _execute_crm(self, task_id: str, action: str, data: dict) -> str:
        """Call KOMMO API. Returns human-readable result."""
        if not config.KOMMO_ACCESS_TOKEN or not config.KOMMO_BASE_URL:
            return (
                f"[CRM] Action '{action}' queued (KOMMO not configured). "
                f"Data: {json.dumps(data, ensure_ascii=False)}"
            )

        from portal.integrations.kommo_crm import KommoCRM

        kommo = KommoCRM()

        try:
            if action == "create_lead":
                lead_id = kommo.create_lead(
                    name=data.get("name", "New Lead"),
                    phone=data.get("phone"),
                    email=data.get("email"),
                    note=data.get("note"),
                    tags=data.get("tags", []),
                )
                url = f"{config.KOMMO_BASE_URL}/leads/detail/{lead_id}"
                return f"Lead created: {data.get('name')} — {url}"

            elif action == "search":
                results = kommo.search(data.get("query", ""))
                if not results:
                    return "No contacts/leads found."
                lines = [f"• {r['name']} (id={r['id']})" for r in results[:10]]
                return "Search results:\n" + "\n".join(lines)

            elif action == "add_note":
                kommo.add_note(
                    entity_id=data.get("lead_id") or data.get("contact_id"),
                    note=data.get("note", ""),
                )
                return "Note added."

            else:
                return f"Action '{action}' received. Data: {json.dumps(data, ensure_ascii=False)}"

        except Exception as e:
            log(task_id, "crm_connector", f"KOMMO error: {e}", "error")
            return f"CRM error: {e}"

"""
KOMMO CRM Integration
─────────────────────
REST API wrapper for KOMMO (formerly amoCRM).

Docs: https://www.kommo.com/developers/content/crm-platform/crm-api/

Required env vars:
    KOMMO_BASE_URL      e.g. https://yourcompany.kommo.com
    KOMMO_ACCESS_TOKEN  long-lived access token (from OAuth or personal token)
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from portal import config


class KommoCRM:
    def __init__(self) -> None:
        base = config.KOMMO_BASE_URL.rstrip("/")
        self._base = f"{base}/api/v4"
        self._headers = {
            "Authorization": f"Bearer {config.KOMMO_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self._base}{path}"
        resp = httpx.get(url, headers=self._headers, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, payload: list | dict) -> dict:
        url = f"{self._base}{path}"
        resp = httpx.post(url, headers=self._headers, content=json.dumps(payload), timeout=15)
        resp.raise_for_status()
        return resp.json()

    def _patch(self, path: str, payload: list | dict) -> dict:
        url = f"{self._base}{path}"
        resp = httpx.patch(url, headers=self._headers, content=json.dumps(payload), timeout=15)
        resp.raise_for_status()
        return resp.json()

    # ── Leads ──────────────────────────────────────────────────────────────────

    def create_lead(
        self,
        name: str,
        phone: str | None = None,
        email: str | None = None,
        note: str | None = None,
        tags: list[str] | None = None,
        pipeline_id: int | None = None,
        status_id: int | None = None,
    ) -> int:
        """Create a lead (with embedded contact if phone/email given). Returns lead id."""
        payload: dict[str, Any] = {"name": name}
        if pipeline_id:
            payload["pipeline_id"] = pipeline_id
        if status_id:
            payload["status_id"] = status_id

        embedded: dict[str, Any] = {}
        if phone or email:
            contact: dict[str, Any] = {"name": name, "custom_fields_values": []}
            if phone:
                contact["custom_fields_values"].append(
                    {
                        "field_code": "PHONE",
                        "values": [{"value": phone, "enum_code": "WORK"}],
                    }
                )
            if email:
                contact["custom_fields_values"].append(
                    {
                        "field_code": "EMAIL",
                        "values": [{"value": email, "enum_code": "WORK"}],
                    }
                )
            embedded["contacts"] = [contact]

        if tags:
            embedded["tags"] = [{"name": t} for t in tags]

        if embedded:
            payload["_embedded"] = embedded

        result = self._post("/leads/complex", [payload])
        lead_id: int = result[0]["id"]

        if note:
            self.add_note(entity_id=lead_id, note=note, entity_type="leads")

        return lead_id

    def search(self, query: str, entity: str = "leads") -> list[dict]:
        """Search leads or contacts. Returns list of {id, name}."""
        try:
            data = self._get(f"/{entity}", params={"query": query, "limit": 10})
            items = data.get("_embedded", {}).get(entity, [])
            return [{"id": i["id"], "name": i.get("name", "")} for i in items]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 204:
                return []
            raise

    def add_note(self, entity_id: int, note: str, entity_type: str = "leads") -> None:
        """Add a text note to a lead or contact."""
        payload = [{"note_type": "common", "params": {"text": note}}]
        self._post(f"/{entity_type}/{entity_id}/notes", payload)

    def update_lead(self, lead_id: int, **fields: Any) -> None:
        """Update lead fields (name, status_id, price, etc.)."""
        self._patch(f"/leads/{lead_id}", [{"id": lead_id, **fields}])

    # ── Contacts ───────────────────────────────────────────────────────────────

    def create_contact(self, name: str, phone: str | None = None, email: str | None = None) -> int:
        """Create a contact. Returns contact id."""
        payload: dict[str, Any] = {"name": name, "custom_fields_values": []}
        if phone:
            payload["custom_fields_values"].append(
                {
                    "field_code": "PHONE",
                    "values": [{"value": phone, "enum_code": "WORK"}],
                }
            )
        if email:
            payload["custom_fields_values"].append(
                {
                    "field_code": "EMAIL",
                    "values": [{"value": email, "enum_code": "WORK"}],
                }
            )
        result = self._post("/contacts", [payload])
        return result["_embedded"]["contacts"][0]["id"]

    # ── Pipelines ──────────────────────────────────────────────────────────────

    def list_pipelines(self) -> list[dict]:
        """Return all pipelines with their statuses."""
        data = self._get("/leads/pipelines")
        return data.get("_embedded", {}).get("pipelines", [])

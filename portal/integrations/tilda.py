"""
Tilda Integration
─────────────────
Tilda Publishing API wrapper.

API docs: https://help.tilda.cc/api

Required env vars:
    TILDA_PUBLIC_KEY   — from Tilda account settings
    TILDA_SECRET_KEY   — from Tilda account settings

Note: Tilda API allows reading project/page data and publishing pages.
To CREATE pages programmatically you typically:
  1. Use a Tilda template page as base
  2. Update content via the Zero Block API or page settings
  3. Publish via the API

The most common portal use-case is to update a page's content
and republish it.
"""

from __future__ import annotations

import hashlib
import hmac
import time

import httpx

from portal import config

TILDA_API = "https://api.tildacdn.info/v1"


class TildaAPI:
    def __init__(self) -> None:
        self._public = config.TILDA_PUBLIC_KEY
        self._secret = config.TILDA_SECRET_KEY
        if not self._public or not self._secret:
            raise OSError("TILDA_PUBLIC_KEY and TILDA_SECRET_KEY must be set")

    def _sign(self, params: dict) -> dict:
        """Add publickey, timestamp, and HMAC signature to params."""
        ts = str(int(time.time()))
        signed_params = {"publickey": self._public, "timestamp": ts, **params}
        # Build the signature string: sorted key=value pairs
        msg = "&".join(f"{k}={v}" for k, v in sorted(signed_params.items()))
        sig = hmac.new(self._secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
        signed_params["signature"] = sig
        return signed_params

    def _get(self, endpoint: str, params: dict | None = None) -> dict:
        signed = self._sign(params or {})
        resp = httpx.get(f"{TILDA_API}/{endpoint}", params=signed, timeout=15)
        resp.raise_for_status()
        return resp.json()

    # ── Projects ───────────────────────────────────────────────────────────────

    def list_projects(self) -> list[dict]:
        """Return all Tilda projects."""
        data = self._get("getprojectslist")
        return data.get("result", [])

    def get_project(self, project_id: str) -> dict:
        """Get project info."""
        data = self._get("getproject", {"projectid": project_id})
        return data.get("result", {})

    # ── Pages ──────────────────────────────────────────────────────────────────

    def list_pages(self, project_id: str) -> list[dict]:
        """List all pages in a project."""
        data = self._get("getpageslist", {"projectid": project_id})
        return data.get("result", [])

    def get_page(self, page_id: str) -> dict:
        """Get full page data including HTML."""
        data = self._get("getpage", {"pageid": page_id})
        return data.get("result", {})

    def get_page_full(self, page_id: str) -> dict:
        """Get full page export (html + css + js)."""
        data = self._get("getpagefull", {"pageid": page_id})
        return data.get("result", {})

    def publish_page(self, page_id: str) -> bool:
        """Publish/republish a page."""
        data = self._get("publishpage", {"pageid": page_id})
        return data.get("status") == "ok"

    # ── High-level helper ──────────────────────────────────────────────────────

    def create_page(self, title: str, content: str, project_id: str | None = None) -> str:
        """
        High-level helper: save content to a Tilda page and publish it.

        Since Tilda doesn't support creating pages from scratch via API,
        this method:
        1. Lists pages in the first (or specified) project
        2. Logs that the content is ready to be pasted manually OR
           uses a pre-configured template page_id from env

        For full automation, configure TILDA_TEMPLATE_PAGE_ID in .env
        and use Zero Block API to inject content.

        Returns a placeholder URL (real URL requires Zero Block setup).
        """
        import os

        template_page_id = os.environ.get("TILDA_TEMPLATE_PAGE_ID", "")
        if template_page_id:
            # In a full implementation: update Zero Block content, then publish
            self.publish_page(template_page_id)
            page_data = self.get_page(template_page_id)
            return page_data.get("alias", f"https://your-tilda-site.com/page{template_page_id}")

        # Fallback: return a note that the content is ready
        projects = self.list_projects()
        proj = projects[0] if projects else {}
        return (
            f"[Tilda] Content ready for manual publishing.\n"
            f"Project: {proj.get('title', 'N/A')} (id={proj.get('id', 'N/A')})\n"
            f"Title: {title}\n"
            f"Content length: {len(content)} chars\n"
            f"Set TILDA_TEMPLATE_PAGE_ID in .env for auto-publishing."
        )

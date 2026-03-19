"""
Browser Hands — Python Client v2
──────────────────────────────────
High-level async API wrapping hands_server primitives.

Fixes from audit v1:
  - get_log() now works (calls server.get_log())
  - smoke_login_form uses assert_() correctly
  - pipeline() method for atomic multi-step execution
  - All 18 actions have typed methods
  - screenshot() returns dataUrl string

Usage:
    import asyncio
    from portal.hands_client import HandsClient

    async def main():
        c = HandsClient()
        await c.navigate("https://example.com")
        await c.type("testid=email", "user@example.com")
        await c.click("text=Увійти")
        title = await c.get_title()
        print(title)

    asyncio.run(main())
"""

from __future__ import annotations

from typing import Any

from portal import hands_server as _srv


class HandsClient:
    """High-level browser automation API. All methods are async."""

    # ── Navigation ─────────────────────────────────────────────────────────────

    async def navigate(self, url: str, timeout: float = 25.0) -> dict:
        return await _srv.send_command({"action": "navigate", "url": url}, timeout=timeout)

    async def get_url(self, timeout: float = 5.0) -> str:
        r = await _srv.send_command({"action": "get_url"}, timeout=timeout)
        return r.get("result", {}).get("url", "")

    async def get_title(self, timeout: float = 5.0) -> str:
        r = await _srv.send_command({"action": "get_title"}, timeout=timeout)
        return r.get("result", {}).get("title", "")

    # ── Interaction ─────────────────────────────────────────────────────────────

    async def click(self, selector: str, timeout: float = 10.0) -> dict:
        return await _srv.send_command({"action": "click", "selector": selector}, timeout=timeout)

    async def type(
        self, selector: str, text: str, clear: bool = True, timeout: float = 10.0
    ) -> dict:
        return await _srv.send_command(
            {"action": "type", "selector": selector, "text": text, "clear": clear},
            timeout=timeout,
        )

    async def select(self, selector: str, value: str, timeout: float = 10.0) -> dict:
        return await _srv.send_command(
            {"action": "select", "selector": selector, "value": value}, timeout=timeout
        )

    async def clear(self, selector: str, timeout: float = 10.0) -> dict:
        return await _srv.send_command({"action": "clear", "selector": selector}, timeout=timeout)

    async def hover(self, selector: str, timeout: float = 10.0) -> dict:
        return await _srv.send_command({"action": "hover", "selector": selector}, timeout=timeout)

    async def focus(self, selector: str, timeout: float = 10.0) -> dict:
        return await _srv.send_command({"action": "focus", "selector": selector}, timeout=timeout)

    async def key_press(self, key: str, selector: str | None = None, timeout: float = 10.0) -> dict:
        cmd: dict[str, Any] = {"action": "key_press", "key": key}
        if selector:
            cmd["selector"] = selector
        return await _srv.send_command(cmd, timeout=timeout)

    async def scroll(
        self, selector: str | None = None, x: int = 0, y: int = 400, timeout: float = 5.0
    ) -> dict:
        cmd: dict[str, Any] = {"action": "scroll", "x": x, "y": y}
        if selector:
            cmd["selector"] = selector
        return await _srv.send_command(cmd, timeout=timeout)

    # ── Reading ─────────────────────────────────────────────────────────────────

    async def get_text(self, selector: str, timeout: float = 10.0) -> str:
        r = await _srv.send_command({"action": "get_text", "selector": selector}, timeout=timeout)
        return r.get("result", {}).get("text", "")

    async def get_attr(self, selector: str, attr: str, timeout: float = 10.0) -> str | None:
        r = await _srv.send_command(
            {"action": "get_attr", "selector": selector, "attr": attr}, timeout=timeout
        )
        return r.get("result", {}).get("value")

    async def get_value(self, selector: str, timeout: float = 10.0) -> str | None:
        r = await _srv.send_command({"action": "get_value", "selector": selector}, timeout=timeout)
        return r.get("result", {}).get("value")

    # ── Assertions & waiting ────────────────────────────────────────────────────

    async def wait_for(self, selector: str, timeout: float = 15.0) -> dict:
        return await _srv.send_command(
            {"action": "wait_for", "selector": selector, "timeoutMs": int(timeout * 1000)},
            timeout=timeout + 2,
        )

    async def wait_for_hidden(self, selector: str, timeout: float = 15.0) -> dict:
        return await _srv.send_command(
            {"action": "wait_for_hidden", "selector": selector, "timeoutMs": int(timeout * 1000)},
            timeout=timeout + 2,
        )

    async def assert_(  # noqa: UP005
        self,
        selector: str,
        text: str | None = None,
        contains: str | None = None,
        exists: bool = True,
        timeout: float = 10.0,
    ) -> dict:
        cmd: dict[str, Any] = {"action": "assert", "selector": selector, "exists": exists}
        if text is not None:
            cmd["text"] = text
        if contains is not None:
            cmd["contains"] = contains
        return await _srv.send_command(cmd, timeout=timeout)

    # ── Utilities ───────────────────────────────────────────────────────────────

    async def screenshot(self, timeout: float = 10.0) -> str:
        """Take a screenshot. Returns base64 PNG data URL."""
        r = await _srv.send_command({"action": "screenshot"}, timeout=timeout)
        return r.get("result", {}).get("dataUrl", "")

    async def eval(self, code: str, timeout: float = 5.0) -> Any:
        """Run a JS expression in a sandboxed Worker. Returns string result."""
        r = await _srv.send_command({"action": "eval", "code": code}, timeout=timeout)
        return r.get("result", {}).get("result")

    # ── Pipeline ────────────────────────────────────────────────────────────────

    async def pipeline(
        self, commands: list[dict[str, Any]], continue_on_error: bool = False, timeout: float = 60.0
    ) -> list[dict]:
        """
        Execute multiple commands in sequence atomically.
        Stops on first failure unless continue_on_error=True.

        Example:
            results = await client.pipeline([
                {"action": "navigate", "url": "https://example.com"},
                {"action": "type",  "selector": "name=email", "text": "u@x.com"},
                {"action": "click", "selector": "text=Login"},
                {"action": "assert", "selector": "testid=dashboard"},
            ])
        """
        return await _srv.send_pipeline(
            commands, timeout=timeout, continue_on_error=continue_on_error
        )

    # ── Log access ──────────────────────────────────────────────────────────────

    async def get_log(self, limit: int = 100) -> list[dict]:
        """Get the extension action log from chrome.storage."""
        return await _srv.get_log(limit=limit)

    async def clear_log(self) -> None:
        """Clear the extension action log."""
        await _srv.clear_log()

    async def get_status(self) -> dict:
        """Return info about the currently active browser tab."""
        return await _srv.get_status()

    # ── Smoke tests ─────────────────────────────────────────────────────────────

    async def smoke_login_form(
        self,
        url: str,
        email_selector: str = "name=email",
        password_selector: str = "name=password",  # noqa: S107
        submit_selector: str = "input[type=submit]",
        email: str = "test@example.com",
        password: str = "",  # noqa: S107 — pass real password at call site
        success_selector: str = "testid=dashboard",
    ) -> bool:
        """
        Smoke test: navigate → type credentials → submit → assert success element.
        Pass real credentials at call site.
        Returns True if all steps pass.
        """
        results = await self.pipeline(
            [
                {"action": "navigate", "url": url},
                {"action": "wait_for", "selector": email_selector, "timeoutMs": 10000},
                {"action": "type", "selector": email_selector, "text": email},
                {"action": "type", "selector": password_selector, "text": password},
                {"action": "click", "selector": submit_selector},
                {
                    "action": "assert",
                    "selector": success_selector,
                    "exists": True,
                    "timeoutMs": 15000,
                },
            ]
        )
        return all(r.get("ok") for r in results)

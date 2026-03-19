"""
Browser Hands — Python Client
──────────────────────────────
High-level async API for controlling the browser from Python/portal code.

Usage:
    import asyncio
    from portal.hands_client import HandsClient

    async def main():
        client = HandsClient()
        await client.navigate("https://kommo.com/login")
        await client.type("name=email", "user@example.com")
        await client.type("name=password", "secret")
        await client.click("text=Увійти")
        await client.assert_("testid=dashboard", exists=True)
        log = await client.get_log()
        print(log)

    asyncio.run(main())
"""

from __future__ import annotations

from typing import Any

from portal.hands_server import send_command


class HandsClient:
    """
    Thin wrapper around send_command for clean call syntax.
    Works when hands_server is already running in the same event loop.
    """

    async def navigate(self, url: str, timeout: float = 20.0) -> dict:
        return await send_command({"action": "navigate", "url": url}, timeout=timeout)

    async def click(self, selector: str, timeout: float = 10.0) -> dict:
        return await send_command({"action": "click", "selector": selector}, timeout=timeout)

    async def type(
        self, selector: str, text: str, clear: bool = True, timeout: float = 10.0
    ) -> dict:
        return await send_command(
            {"action": "type", "selector": selector, "text": text, "clear": clear},
            timeout=timeout,
        )

    async def select(self, selector: str, value: str, timeout: float = 10.0) -> dict:
        return await send_command(
            {"action": "select", "selector": selector, "value": value}, timeout=timeout
        )

    async def wait_for(self, selector: str, timeout: float = 15.0) -> dict:
        return await send_command(
            {"action": "wait_for", "selector": selector, "timeoutMs": int(timeout * 1000)},
            timeout=timeout + 2,
        )

    async def assert_(
        self, selector: str, text: str | None = None, exists: bool = True, timeout: float = 10.0
    ) -> dict:
        cmd: dict[str, Any] = {"action": "assert", "selector": selector, "exists": exists}
        if text is not None:
            cmd["text"] = text
        return await send_command(cmd, timeout=timeout)

    async def get_text(self, selector: str, timeout: float = 10.0) -> str:
        result = await send_command({"action": "get_text", "selector": selector}, timeout=timeout)
        return result.get("result", {}).get("text", "")

    async def get_attr(self, selector: str, attr: str, timeout: float = 10.0) -> str | None:
        result = await send_command(
            {"action": "get_attr", "selector": selector, "attr": attr}, timeout=timeout
        )
        return result.get("result", {}).get("value")

    async def scroll(
        self, selector: str | None = None, x: int = 0, y: int = 400, timeout: float = 5.0
    ) -> dict:
        cmd: dict[str, Any] = {"action": "scroll", "x": x, "y": y}
        if selector:
            cmd["selector"] = selector
        return await send_command(cmd, timeout=timeout)

    async def eval(self, code: str, timeout: float = 5.0) -> Any:
        result = await send_command({"action": "eval", "code": code}, timeout=timeout)
        return result.get("result", {}).get("result")

    # ── Smoke test ─────────────────────────────────────────────────────────────

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
        Smoke test: navigate → type email → type password → click submit → assert dashboard.
        Returns True if all steps pass. Pass real credentials at call site.
        """
        await self.navigate(url)
        await self.wait_for(email_selector)
        await self.type(email_selector, email)
        await self.type(password_selector, password)
        await self.click(submit_selector)
        result = await self.assert_(success_selector, exists=True, timeout=15.0)  # noqa: UP005
        return result.get("ok", False)

    async def get_log(self) -> list[dict]:
        """Retrieve action log from chrome.storage via background."""
        # Log is stored in extension storage; access from Python is via WS message
        # For now return empty — full impl needs a GET_LOG WS message type
        return []

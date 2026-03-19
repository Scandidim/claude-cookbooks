"""
Browser Hands — WebSocket Bridge Server v2
───────────────────────────────────────────
Runs on ws://localhost:8765. The Chrome extension connects here.
Portal Python code sends commands via send_command() / HandsClient.

Fixes from audit v1:
  - Pending futures rejected on WebSocket close (no more 30s waits)
  - GET_LOG / CLEAR_LOG WS message types implemented
  - Pipeline (batch command) support
  - GET_STATUS support
  - Configurable host/port via env vars
  - Proper exception chaining (B904)

Usage:
    # Start server (keep running):
    python -m portal.hands_server

    # In another script/task:
    from portal.hands_client import HandsClient
    import asyncio

    async def main():
        c = HandsClient()
        await c.navigate("https://example.com")
        await c.click("testid=submit")

    asyncio.run(main())
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import Any

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
except ImportError as e:
    raise ImportError("Install websockets: uv add websockets") from e

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Hands] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("hands_server")

HOST = os.environ.get("HANDS_HOST", "localhost")
PORT = int(os.environ.get("HANDS_PORT", "8765"))

# Connected extension clients: {client_id: websocket}
_clients: dict[str, WebSocketServerProtocol] = {}

# Pending response futures: {requestId: asyncio.Future}
_pending: dict[str, asyncio.Future] = {}


async def handler(ws: WebSocketServerProtocol, _path: str = "/") -> None:
    client_id = str(uuid.uuid4())[:8]
    _clients[client_id] = ws
    log.info(f"Extension connected: {client_id} — total: {len(_clients)}")

    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                log.warning(f"Bad JSON from {client_id}: {raw[:200]}")
                continue

            mtype = msg.get("type")

            if mtype == "HELLO":
                log.info(f"HELLO from {client_id}: agent={msg.get('agent')} v={msg.get('version')}")

            elif mtype in ("HANDS_RESULT", "PIPELINE_RESULT", "LOG_DATA", "LOG_CLEARED", "STATUS"):
                req_id = msg.get("requestId")
                if req_id and req_id in _pending:
                    fut = _pending.pop(req_id)
                    if not fut.done():
                        fut.set_result(msg)
                else:
                    log.debug(f"Unmatched response: {mtype} requestId={req_id}")

    except websockets.ConnectionClosed as e:
        log.info(f"Extension disconnected: {client_id} — code={e.code}")
    finally:
        _clients.pop(client_id, None)
        # Reject all pending futures that were waiting on this client
        for req_id, fut in list(_pending.items()):
            if not fut.done():
                fut.set_exception(
                    ConnectionError(f"Extension {client_id} disconnected mid-command")
                )
                _pending.pop(req_id, None)


async def _send(payload: dict, timeout: float = 30.0) -> dict:
    """Send a message to the first connected extension and await its response."""
    if not _clients:
        raise ConnectionError("No extension connected. Load Browser Hands in Chrome/Firefox first.")

    ws = next(iter(_clients.values()))
    request_id = str(uuid.uuid4())

    loop = asyncio.get_event_loop()
    fut: asyncio.Future = loop.create_future()
    _pending[request_id] = fut

    payload["requestId"] = request_id
    await ws.send(json.dumps(payload))
    log.debug(f"→ {payload.get('type')} {payload}")

    try:
        result = await asyncio.wait_for(asyncio.shield(fut), timeout=timeout)
        log.debug(f"← {result}")
        return result
    except TimeoutError as e:
        _pending.pop(request_id, None)
        raise TimeoutError(f"No response for {payload.get('type')} after {timeout}s") from e


async def send_command(command: dict[str, Any], timeout: float = 30.0) -> dict:
    """Execute a single browser action. Returns {ok, result, error}."""
    result = await _send({"type": "HANDS_CMD", "command": command}, timeout=timeout)
    return result


async def send_pipeline(
    commands: list[dict], timeout: float = 60.0, continue_on_error: bool = False
) -> list[dict]:
    """Execute a list of commands atomically (stops on first failure by default)."""
    result = await _send(
        {"type": "HANDS_PIPELINE", "commands": commands, "continueOnError": continue_on_error},
        timeout=timeout,
    )
    return result.get("results", [])


async def get_log(limit: int = 100, timeout: float = 5.0) -> list[dict]:
    """Retrieve action log from the extension's chrome.storage."""
    result = await _send({"type": "GET_LOG", "limit": limit}, timeout=timeout)
    return result.get("entries", [])


async def clear_log(timeout: float = 5.0) -> None:
    """Clear the extension's action log."""
    await _send({"type": "CLEAR_LOG"}, timeout=timeout)


async def get_status(timeout: float = 5.0) -> dict:
    """Get current active tab info from the extension."""
    return await _send({"type": "GET_STATUS"}, timeout=timeout)


async def start_server() -> None:
    log.info(f"Browser Hands server starting on ws://{HOST}:{PORT}")
    async with websockets.serve(handler, HOST, PORT):
        log.info("Listening. Load the extension in Chrome then press ⚡ Підключити портал")
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(start_server())

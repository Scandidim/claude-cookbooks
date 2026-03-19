"""
Browser Hands — WebSocket Bridge Server
─────────────────────────────────────────
Runs locally on ws://localhost:8765.
The Chrome extension connects to this server and receives HANDS_CMD messages.
The portal orchestrator (or any Python code) sends commands here.

Usage:
    # Start server
    python -m portal.hands_server

    # Send a command from Python
    from portal.hands_client import HandsClient
    async with HandsClient() as hands:
        await hands.navigate("https://example.com")
        await hands.type("testid=email", "user@example.com")
        await hands.click("testid=submit")
        await hands.assert_("testid=dashboard")
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
except ImportError as e:
    raise ImportError("Install websockets: uv add websockets") from e

logging.basicConfig(level=logging.INFO, format="%(asctime)s [Hands] %(message)s")
log = logging.getLogger("hands_server")

HOST = "localhost"
PORT = 8765

# Connected extension clients {id: websocket}
_clients: dict[str, WebSocketServerProtocol] = {}
# Pending responses {requestId: Future}
_pending: dict[str, asyncio.Future] = {}


async def handler(ws: WebSocketServerProtocol, path: str = "/") -> None:
    client_id = str(uuid.uuid4())[:8]
    _clients[client_id] = ws
    log.info(f"Extension connected: {client_id}")
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            mtype = msg.get("type")

            if mtype == "HELLO":
                log.info(f"HELLO from {client_id}: {msg}")

            elif mtype == "HANDS_RESULT":
                req_id = msg.get("requestId")
                if req_id and req_id in _pending:
                    fut = _pending.pop(req_id)
                    if not fut.done():
                        fut.set_result(msg)

    except websockets.ConnectionClosed:
        pass
    finally:
        _clients.pop(client_id, None)
        log.info(f"Extension disconnected: {client_id}")


async def send_command(command: dict[str, Any], timeout: float = 30.0) -> dict:
    """Send a command to the first connected extension client. Returns result."""
    if not _clients:
        raise RuntimeError("No extension connected. Load the Browser Hands extension in Chrome.")

    ws = next(iter(_clients.values()))
    request_id = str(uuid.uuid4())

    loop = asyncio.get_event_loop()
    fut: asyncio.Future = loop.create_future()
    _pending[request_id] = fut

    await ws.send(json.dumps({"type": "HANDS_CMD", "requestId": request_id, "command": command}))
    log.info(f"→ {command.get('action')} {command}")

    try:
        result = await asyncio.wait_for(fut, timeout=timeout)
        log.info(f"← {result}")
        return result
    except TimeoutError as e:
        _pending.pop(request_id, None)
        raise TimeoutError(f"No response for command {command} after {timeout}s") from e


async def start_server() -> None:
    log.info(f"Browser Hands server on ws://{HOST}:{PORT}")
    async with websockets.serve(handler, HOST, PORT):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(start_server())

#!/usr/bin/env python3
"""
Oblique Strategies – server.py
Jeden port obsługuje zarówno HTTP (pliki statyczne) jak i WebSocket (/ws).
Działa lokalnie i na Render.com.

Uruchomienie lokalne:
    python3 server.py
    Otwórz: http://localhost:8000

Na Render: port ustawiany automatycznie przez zmienną środowiskową PORT.
"""

import asyncio
import json
import logging
import os
from pathlib import Path

from aiohttp import web
import aiohttp

# ── KONFIGURACJA ────────────────────────────────────────────────────────────

PORT       = int(os.environ.get("PORT", 8000))
STATIC_DIR = Path(__file__).parent

# ── LOGGING ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("oblique")

# ── STAN GLOBALNY ───────────────────────────────────────────────────────────

clients: set = set()

# ── WEBSOCKET ───────────────────────────────────────────────────────────────

async def ws_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    clients.add(ws)
    log.info(f"WS  połączono  {request.remote}")

    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    log.warning(f"WS  złe JSON: {msg.data!r}")
                    continue

                action = data.get("action")

                if action == "result":
                    index = int(data.get("index", 0))
                    log.info(f"WS  wynik spinu → scena {index + 1}")

                elif action == "spin":
                    log.info("WS  trigger spin z WebSocket")
                    await broadcast({"action": "spin"})

                else:
                    log.debug(f"WS  nieznana akcja: {data}")

            elif msg.type == aiohttp.WSMsgType.ERROR:
                log.warning(f"WS  błąd: {ws.exception()}")

    finally:
        clients.discard(ws)
        log.info(f"WS  rozłączono {request.remote}")

    return ws

async def broadcast(data: dict):
    if not clients:
        return
    payload = json.dumps(data)
    await asyncio.gather(
        *[c.send_str(payload) for c in list(clients)],
        return_exceptions=True,
    )

# ── HTTP – pliki statyczne ───────────────────────────────────────────────────

async def handle_index(request):
    return web.FileResponse(STATIC_DIR / "index.html")

async def handle_static(request):
    path = request.match_info["path"]
    file_path = STATIC_DIR / path
    if file_path.is_file():
        return web.FileResponse(file_path)
    return web.Response(status=404, text="Not found")

# ── APP ─────────────────────────────────────────────────────────────────────

def make_app():
    app = web.Application()
    app.router.add_get("/ws", ws_handler)           # WebSocket endpoint
    app.router.add_get("/", handle_index)            # strona główna
    app.router.add_get("/{path:.+}", handle_static)  # segmenty, JSON, itp.
    return app

# ── MAIN ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info(f"Startuje na porcie {PORT}…")
    log.info("─" * 50)
    log.info(f"HTTP  → http://localhost:{PORT}")
    log.info(f"WS    → ws://localhost:{PORT}/ws")
    log.info("─" * 50)
    web.run_app(make_app(), host="0.0.0.0", port=PORT, print=None)

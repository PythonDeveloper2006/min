import asyncio, os, logging
import websockets
from http import HTTPStatus

# чтобы не спамило "opening handshake failed" трейсами
logging.getLogger("websockets").setLevel(logging.WARNING)

PORT = int(os.getenv("PORT", "80"))
clients = set()

async def ws_handler(ws, path=None):  # path оставлен для совместимости
    clients.add(ws)
    try:
        async for msg in ws:
            await asyncio.gather(*(c.send(msg) for c in clients if c is not ws))
    finally:
        clients.discard(ws)

async def process_request(path, request_headers):
    # Если это НЕ WebSocket upgrade (браузер/healthcheck) — ответим обычным HTTP 200 "ok"
    if request_headers.get("Upgrade", "").lower() != "websocket":
        body = b"ok"
        return (
            HTTPStatus.OK,
            [("Content-Type", "text/plain"), ("Content-Length", str(len(body)))],
            body,
        )
    return None  # иначе продолжаем WebSocket handshake

async def main():
    async with websockets.serve(
        ws_handler, "0.0.0.0", PORT,
        process_request=process_request,
        ping_interval=20, ping_timeout=20,
    ):
        await asyncio.Future()

if __name__ == "__main__":
    print(f"server start:{PORT}")
    asyncio.run(main())

print('''
ПРОГРАММА ЗАПУЩЕНА
ПРОГРАММА ЗАПУЩЕНА
ПРОГРАММА ЗАПУЩЕНА
ПРОГРАММА ЗАПУЩЕНА
ПРОГРАММА ЗАПУЩЕНА
ПРОГРАММА ЗАПУЩЕНА
ПРОГРАММА ЗАПУЩЕНА
''')

import asyncio, websockets, os

import logging

class DropHandshakeNoise(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not (
            "opening handshake failed" in msg
            or "did not receive a valid HTTP request" in msg
        )

ws_logger = logging.getLogger("websockets")
ws_logger.addFilter(DropHandshakeNoise())
ws_logger.setLevel(logging.INFO)


PORT = int(os.getenv('PORT', 80))
clients = set()

async def handler(ws):
    print("connect")
    clients.add(ws)
    try:
        async for msg in ws:
            print("recv:", msg)
            await asyncio.gather(
                *(c.send(msg) for c in clients if c != ws)
            )
    except Exception as e:
        print("error:", e)
    finally:
        clients.remove(ws)
        print("disconnect")

async def main():
    print(f"server start:{PORT}")
    async with websockets.serve(handler, "0.0.0.0", PORT):
        await asyncio.Future()

asyncio.run(main())

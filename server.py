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

import sys
import logging
from websockets.exceptions import InvalidMessage

# важно: настроить логирование до запуска сервера
logging.basicConfig(stream=sys.stdout, level=logging.INFO, force=True)

class DropWsNoise(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()

        # по тексту
        if ("opening handshake failed" in msg
            or "did not receive a valid HTTP request" in msg
            or "connection closed while reading HTTP request line" in msg):
            return False

        # по типу исключения (traceback)
        if record.exc_info and record.exc_info[1]:
            exc = record.exc_info[1]
            if isinstance(exc, (EOFError, InvalidMessage)):
                return False

        return True

root = logging.getLogger()
for h in root.handlers:
    h.addFilter(DropWsNoise())

# на всякий случай: поднять порог именно для websockets
for name in ("websockets", "websockets.server", "websockets.asyncio.server"):
    logging.getLogger(name).setLevel(logging.ERROR)



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

if __name__ == "__main__":
    import asyncio, websockets, os

    PORT = int(os.getenv("PORT", 80))
    clients = set()

    async def process_request(*args):
        # если пришёл обычный HTTP (healthcheck/браузер), отвечаем 200 OK
        # и websockets не будет ругаться на "opening handshake failed"
        headers = args[1] if len(args) == 2 else getattr(args[1], "headers", {})
        if str(headers.get("Upgrade", "")).lower() != "websocket":
            body = b"OK"
            return 200, [("Content-Type", "text/plain"),
                         ("Content-Length", str(len(body)))], body
        return None

    async def handler(ws):
        print("connect")
        clients.add(ws)
        try:
            async for msg in ws:
                print("recv:", msg)
                await asyncio.gather(
                    *(c.send(msg) for c in clients if c != ws),
                    return_exceptions=True,
                )
        except Exception as e:
            print("error:", e)
        finally:
            clients.discard(ws)
            print("disconnect")

    async def main():
        print(f"server start:{PORT}")
        async with websockets.serve(
            handler, "0.0.0.0", PORT, process_request=process_request
        ):
            await asyncio.Future()

    asyncio.run(main())

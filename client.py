# import urllib.request
#
# url = "https://whale-app-t34ml.ondigitalocean.app/вот тут что ли надо каждый раз писать свое сообщение? разве это так делается?"
# print(urllib.request.urlopen(url).read().decode())

if __name__ == "__main__":
    import asyncio, websockets

    async def reader(ws):
        async for msg in ws:
            print("\n<", msg)

    async def writer(ws):
        while True:
            msg = await asyncio.to_thread(input, "> ")
            await ws.send(msg)

    async def main():
        async with websockets.connect("ws://127.0.0.1:9000") as ws:
            await asyncio.gather(
                reader(ws),
                writer(ws),
            )

    asyncio.run(main())

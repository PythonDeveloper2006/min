# import os
# import http.server
# import socketserver
#
# from http import HTTPStatus
#
#
# class Handler(http.server.SimpleHTTPRequestHandler):
#     def do_GET(self):
#         self.send_response(HTTPStatus.OK)
#         self.end_headers()
#         msg = 'Ты написал %s' % (self.path)
#         self.wfile.write(msg.encode())
#
#
# port = int(os.getenv('PORT', 80))
# print('Listening on port %s' % (port))
# httpd = socketserver.TCPServer(('', port), Handler)
# httpd.serve_forever()


import asyncio, websockets

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
    print("server start:9000")
    async with websockets.serve(handler, "0.0.0.0", 9000):
        await asyncio.Future()

asyncio.run(main())

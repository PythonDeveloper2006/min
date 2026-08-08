"""Small read-only API for Nether Roads Map."""

from __future__ import annotations

import json
import logging
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
MAP_PATH = BASE_DIR / "map.json"
PORT = int(os.environ.get("PORT", "8080"))
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("nether-roads-api")


def load_map() -> dict:
    with MAP_PATH.open("r", encoding="utf-8") as map_file:
        payload = json.load(map_file)
    if not isinstance(payload, dict) or not isinstance(payload.get("routes"), list) or not isinstance(payload.get("markers"), list):
        raise ValueError("map.json must contain routes and markers arrays")
    return payload


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "NetherRoadsMapAPI/1.0"

    def _send_json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", CORS_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_json(HTTPStatus.NO_CONTENT, {})

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return

        if self.path == "/api/map":
            try:
                payload = load_map()
            except (OSError, ValueError, json.JSONDecodeError) as error:
                logger.exception("Could not load map data: %s", error)
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "map_data_unavailable"})
                return
            self._send_json(HTTPStatus.OK, payload)
            return

        if self.path == "/":
            self._send_json(
                HTTPStatus.OK,
                {
                    "service": "nether-roads-map-api",
                    "status": "ok",
                    "endpoints": ["/api/map", "/healthz"],
                },
            )
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def log_message(self, format_string: str, *args: object) -> None:
        logger.info("%s - %s", self.address_string(), format_string % args)


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), ApiHandler)
    logger.info("Nether Roads Map API listening on port %s", PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopping server")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

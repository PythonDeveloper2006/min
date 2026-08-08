"""Nether Roads Map API with GitHub-backed JSON persistence."""

from __future__ import annotations

import base64
import copy
import datetime as dt
import hmac
import json
import logging
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
MAP_PATH = BASE_DIR / "map.json"
PORT = int(os.environ.get("PORT", "8080"))
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*")
MAP_ADMIN_KEY = os.environ.get("MAP_ADMIN_KEY", "").strip()
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.environ.get("GITHUB_REPO", "PythonDeveloper2006/min").strip()
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main").strip()
GITHUB_MAP_PATH = os.environ.get("GITHUB_MAP_PATH", "map.json").strip().strip("/")
MAX_BODY_BYTES = 1_000_000
MAP_LOCK = threading.RLock()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("nether-roads-api")


def load_map() -> dict:
    with MAP_PATH.open("r", encoding="utf-8") as map_file:
        payload = json.load(map_file)
    return validate_map(payload)


def validate_map(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("map payload must be an object")
    routes = payload.get("routes")
    markers = payload.get("markers")
    if not isinstance(routes, list) or not isinstance(markers, list):
        raise ValueError("map payload must contain routes and markers arrays")

    route_ids: set[str] = set()
    for route in routes:
        if not isinstance(route, dict):
            raise ValueError("each route must be an object")
        validate_item(route, route_ids, "route")
        if route.get("axis") not in {"x", "z"}:
            raise ValueError("route axis must be x or z")
        if route.get("sign") not in {-1, 1}:
            raise ValueError("route sign must be -1 or 1")
        if not isinstance(route.get("color"), str) or not route["color"].startswith("#"):
            raise ValueError("route color must be a hex color")

    marker_ids: set[str] = set()
    for marker in markers:
        if not isinstance(marker, dict):
            raise ValueError("each marker must be an object")
        validate_item(marker, marker_ids, "marker")
        if marker.get("type") not in {"farm", "portal"}:
            raise ValueError("marker type must be farm or portal")

    return copy.deepcopy(payload)


def validate_item(item: dict, ids: set[str], item_type: str) -> None:
    item_id = item.get("id")
    name = item.get("name")
    if not isinstance(item_id, str) or not item_id.strip() or item_id in ids:
        raise ValueError(f"{item_type} ids must be unique non-empty strings")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"{item_type} name must be a non-empty string")
    if not is_number(item.get("x")) or not is_number(item.get("z")):
        raise ValueError(f"{item_type} coordinates must be numbers")
    ids.add(item_id)


def is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def serialize_map(payload: dict) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def github_api_url() -> str:
    repo = urllib.parse.quote(GITHUB_REPO, safe="/")
    path = urllib.parse.quote(GITHUB_MAP_PATH, safe="/")
    return f"https://api.github.com/repos/{repo}/contents/{path}"


def github_request(url: str, method: str = "GET", body: dict | None = None) -> dict:
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN is not configured")
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "User-Agent": "nether-roads-map-api",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    encoded_body = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        encoded_body = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=encoded_body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def commit_map_to_github(payload: dict) -> str | None:
    api_url = github_api_url()
    branch_query = urllib.parse.urlencode({"ref": GITHUB_BRANCH})
    metadata = github_request(f"{api_url}?{branch_query}")
    sha = metadata.get("sha")
    if not isinstance(sha, str) or not sha:
        raise RuntimeError("GitHub did not return the current map file SHA")
    commit_body = {
        "message": "Update Nether Roads map data",
        "content": base64.b64encode(serialize_map(payload)).decode("ascii"),
        "branch": GITHUB_BRANCH,
        "sha": sha,
    }
    result = github_request(api_url, method="PUT", body=commit_body)
    commit = result.get("commit") if isinstance(result, dict) else None
    return commit.get("html_url") if isinstance(commit, dict) else None


def write_local_map(payload: dict) -> None:
    temporary_path = MAP_PATH.with_suffix(".json.tmp")
    temporary_path.write_bytes(serialize_map(payload))
    temporary_path.replace(MAP_PATH)


def with_server_metadata(payload: dict, current: dict) -> dict:
    result = validate_map(payload)
    result["version"] = int(current.get("version", 0)) + 1
    result["updatedAt"] = dt.datetime.now(dt.timezone.utc).isoformat()
    result.setdefault("dimension", current.get("dimension", "minecraft:the_nether"))
    return result


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "NetherRoadsMapAPI/2.0"

    def _send_json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", CORS_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Map-Admin-Key")
        self.end_headers()
        if status != HTTPStatus.NO_CONTENT:
            self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_json(HTTPStatus.NO_CONTENT, {})

    def do_GET(self) -> None:  # noqa: N802
        path = urllib.parse.urlsplit(self.path).path
        if path == "/healthz":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return

        if path == "/api/map":
            try:
                with MAP_LOCK:
                    payload = load_map()
            except (OSError, ValueError, json.JSONDecodeError) as error:
                logger.exception("Could not load map data: %s", error)
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "map_data_unavailable"})
                return
            self._send_json(HTTPStatus.OK, payload)
            return

        if path == "/":
            self._send_json(
                HTTPStatus.OK,
                {
                    "service": "nether-roads-map-api",
                    "status": "ok",
                    "storage": "github",
                    "endpoints": ["/api/map", "/healthz"],
                },
            )
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_PUT(self) -> None:  # noqa: N802
        path = urllib.parse.urlsplit(self.path).path
        if path != "/api/map":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return

        provided_key = self.headers.get("X-Map-Admin-Key", "")
        if not MAP_ADMIN_KEY or not hmac.compare_digest(provided_key, MAP_ADMIN_KEY):
            self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "editor_key_required"})
            return
        if not GITHUB_TOKEN:
            self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "github_storage_not_configured"})
            return

        try:
            body_length = int(self.headers.get("Content-Length", "0"))
            if body_length <= 0 or body_length > MAX_BODY_BYTES:
                raise ValueError("invalid request body size")
            incoming = json.loads(self.rfile.read(body_length).decode("utf-8"))
            with MAP_LOCK:
                current = load_map()
                payload = with_server_metadata(incoming, current)
                commit_url = commit_map_to_github(payload)
                write_local_map(payload)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_map", "message": str(error)})
            return
        except urllib.error.HTTPError as error:
            logger.exception("GitHub rejected map update: %s", error)
            status = HTTPStatus.CONFLICT if error.code == HTTPStatus.CONFLICT else HTTPStatus.BAD_GATEWAY
            self._send_json(status, {"error": "github_write_failed", "status": error.code})
            return
        except (OSError, RuntimeError) as error:
            logger.exception("Could not persist map update: %s", error)
            self._send_json(HTTPStatus.BAD_GATEWAY, {"error": "github_write_failed"})
            return

        response = copy.deepcopy(payload)
        response["save"] = {"storage": "github", "commit": commit_url}
        self._send_json(HTTPStatus.OK, response)

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

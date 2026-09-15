"""Authenticated loopback control server for the GUI, CLI, and MCP bridge."""
from __future__ import annotations

import hmac
import json
import os
import secrets
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable


def control_info_path() -> Path:
    """Return the per-user discovery file used by local control clients."""
    appdata = os.environ.get("LOCALAPPDATA")
    root = Path(appdata) if appdata else Path.home() / ".autoclicktimer"
    return root / "AutoClickTimer" / "control.json"


class ControlServer:
    """Small authenticated HTTP server bound to localhost only."""

    def __init__(self, handler: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self._handler = handler
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._token = ""
        self._info_path = control_info_path()

    @property
    def endpoint(self) -> str:
        if self._httpd is None:
            return ""
        return f"http://127.0.0.1:{self._httpd.server_port}"

    def start(self) -> str:
        if self._httpd is not None:
            return self.endpoint

        self._token = secrets.token_urlsafe(32)
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), _RequestHandler)
        self._httpd.daemon_threads = True
        self._httpd.control_server = self  # type: ignore[attr-defined]
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="AutoClickTimerControl",
            daemon=True,
        )
        self._thread.start()
        self._write_info()
        return self.endpoint

    def stop(self) -> None:
        httpd = self._httpd
        self._httpd = None
        if httpd is not None:
            httpd.shutdown()
            httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

        try:
            info = json.loads(self._info_path.read_text(encoding="utf-8"))
            if hmac.compare_digest(str(info.get("token", "")), self._token):
                self._info_path.unlink(missing_ok=True)
        except (OSError, ValueError, TypeError):
            pass

    def authorized(self, supplied_token: str) -> bool:
        return bool(supplied_token) and hmac.compare_digest(supplied_token, self._token)

    def dispatch(self, payload: dict[str, Any], source: str) -> dict[str, Any]:
        payload = dict(payload)
        payload["source"] = source
        try:
            result = self._handler(payload)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        if not isinstance(result, dict):
            return {"ok": False, "error": "Control handler returned an invalid response"}
        return result

    def _write_info(self) -> None:
        self._info_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "endpoint": self.endpoint,
            "token": self._token,
            "pid": os.getpid(),
            "protocol": "autoclicktimer-v1",
        }
        temp_path = self._info_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(temp_path, self._info_path)


class _RequestHandler(BaseHTTPRequestHandler):
    server: ThreadingHTTPServer

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json({"ok": True, "protocol": "autoclicktimer-v1"})
            return
        if self.path != "/v1/status":
            self._send_json({"ok": False, "error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        control = self._control()
        if not self._check_auth(control):
            return
        self._send_json(control.dispatch({"command": "status"}, "CLI"))

    def do_POST(self) -> None:
        control = self._control()
        if not self._check_auth(control):
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > 64 * 1024:
            self._send_json({"ok": False, "error": "Invalid request size"}, HTTPStatus.BAD_REQUEST)
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json({"ok": False, "error": "Request body must be valid JSON"}, HTTPStatus.BAD_REQUEST)
            return
        if not isinstance(payload, dict):
            self._send_json({"ok": False, "error": "Request body must be an object"}, HTTPStatus.BAD_REQUEST)
            return

        if self.path == "/v1/command":
            source = self.headers.get("X-AutoClick-Source", "CLI").upper()
            if source not in {"CLI", "MCP"}:
                source = "CLI"
            self._send_json(control.dispatch(payload, source))
            return
        if self.path == "/mcp":
            response = self._mcp_dispatch(control, payload)
            if response is not None:
                self._send_json(response)
            else:
                self.send_response(HTTPStatus.NO_CONTENT)
                self.end_headers()
            return
        self._send_json({"ok": False, "error": "Not found"}, HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _control(self) -> ControlServer:
        return self.server.control_server  # type: ignore[attr-defined,return-value]

    def _check_auth(self, control: ControlServer) -> bool:
        auth = self.headers.get("Authorization", "")
        token = self.headers.get("X-AutoClick-Token", "")
        if not token and auth.lower().startswith("bearer "):
            token = auth[7:].strip()
        if control.authorized(token):
            return True
        self._send_json({"ok": False, "error": "Unauthorized"}, HTTPStatus.UNAUTHORIZED)
        return False

    def _mcp_dispatch(self, control: ControlServer, payload: dict[str, Any]) -> dict[str, Any] | None:
        request_id = payload.get("id")
        method = payload.get("method")
        if method == "notifications/initialized":
            return None
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "AutoClickTimer", "version": "1"},
                },
            }
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": MCP_TOOLS},
            }
        if method == "tools/call":
            params = payload.get("params") or {}
            if not isinstance(params, dict):
                return self._mcp_error(request_id, "params must be an object", -32602)
            name = params.get("name")
            arguments = params.get("arguments") or {}
            command = MCP_COMMANDS.get(name)
            if command is None or not isinstance(arguments, dict):
                return self._mcp_error(request_id, "Unknown tool or invalid arguments", -32602)
            command_payload = dict(arguments)
            command_payload["command"] = command
            result = control.dispatch(command_payload, "MCP")
            if not result.get("ok", False):
                return self._mcp_error(request_id, str(result.get("error", "Command failed")), -32000)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result)}]},
            }
        return self._mcp_error(request_id, f"Unsupported method: {method}")

    @staticmethod
    def _mcp_error(request_id: Any, message: str, code: int = -32601) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


MCP_COMMANDS = {
    "queue_status": "status",
    "queue_add": "add",
    "queue_start": "start",
    "queue_stop": "stop",
    "queue_reset": "reset",
    "queue_clear": "clear",
    "power_status": "power_get",
    "power_set": "power_set",
}

MCP_TOOLS = [
    {"name": "queue_status", "description": "Show queue status", "inputSchema": {"type": "object", "properties": {}}},
    {
        "name": "queue_add",
        "description": "Add one queue item",
        "inputSchema": {
            "type": "object",
            "properties": {
                "item": {
                    "type": "object",
                    "properties": {
                        "total": {"type": "integer", "minimum": 1},
                        "action": {"type": "string", "enum": ["enter", "click", "type", "sleep", "shutdown"]},
                        "prompt": {"type": "string"},
                        "label": {"type": "string"},
                        "sleep_cfg": {"type": "object"},
                        "target_window": {"type": "string"},
                        "require_foreground": {"type": "boolean"},
                    },
                    "required": ["total", "action"],
                }
            },
            "required": ["item"],
        },
    },
    {
        "name": "queue_start",
        "description": "Start the queue",
        "inputSchema": {"type": "object", "properties": {"delay_minutes": {"type": "integer", "minimum": 0}}},
    },
    {"name": "queue_stop", "description": "Stop the queue", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "queue_reset", "description": "Reset queue items", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "queue_clear", "description": "Clear the queue", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "power_status", "description": "Read Windows power settings", "inputSchema": {"type": "object", "properties": {}}},
    {
        "name": "power_set",
        "description": "Apply Windows power settings",
        "inputSchema": {
            "type": "object",
            "properties": {
                "settings": {
                    "type": "object",
                    "properties": {
                        "plugged_in": {
                            "type": "object",
                            "properties": {
                                "lid_action": {"type": "string"},
                                "power_button_action": {"type": "string"},
                                "display_timeout": {"type": "string"},
                                "sleep_timeout": {"type": "string"},
                            },
                            "required": ["lid_action", "power_button_action", "display_timeout", "sleep_timeout"],
                        },
                        "on_battery": {
                            "type": "object",
                            "properties": {
                                "lid_action": {"type": "string"},
                                "power_button_action": {"type": "string"},
                                "display_timeout": {"type": "string"},
                                "sleep_timeout": {"type": "string"},
                            },
                            "required": ["lid_action", "power_button_action", "display_timeout", "sleep_timeout"],
                        },
                    },
                    "required": ["plugged_in", "on_battery"],
                }
            },
            "required": ["settings"],
        },
    },
]

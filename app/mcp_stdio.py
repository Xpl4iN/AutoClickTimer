"""Minimal MCP stdio adapter that forwards tools to the running GUI."""
from __future__ import annotations

import json
import sys
from typing import Any

from app.control_client import ControlClientError, request
from app.control_server import MCP_COMMANDS as COMMANDS, MCP_TOOLS as TOOLS


def run() -> int:
    for line in sys.stdin:
        try:
            payload = json.loads(line)
            response = dispatch(payload)
        except (json.JSONDecodeError, TypeError) as exc:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


def dispatch(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Request must be an object"}}
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
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method != "tools/call":
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Unsupported method: {method}"}}

    params = payload.get("params") or {}
    if not isinstance(params, dict):
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": "params must be an object"}}
    name = params.get("name")
    command = COMMANDS.get(name)
    arguments = params.get("arguments") or {}
    if command is None or not isinstance(arguments, dict):
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": "Unknown tool or invalid arguments"}}
    try:
        command_payload = dict(arguments)
        command_payload["command"] = command
        result = request(command_payload, source="MCP")
    except ControlClientError as exc:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": str(exc)}}
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]},
    }

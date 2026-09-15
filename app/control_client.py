"""CLI client for the running AutoClickTimer GUI."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from app.control_server import control_info_path


class ControlClientError(RuntimeError):
    pass


def request(payload: dict[str, Any], source: str = "CLI") -> dict[str, Any]:
    try:
        info = json.loads(control_info_path().read_text(encoding="utf-8"))
        endpoint = str(info["endpoint"])
        token = str(info["token"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ControlClientError("AutoClickTimer is not running or its control file is unavailable") from exc

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{endpoint}/v1/command",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-AutoClick-Token": token,
            "X-AutoClick-Source": source.upper(),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8"))
        except (OSError, ValueError):
            detail = {"error": str(exc)}
        raise ControlClientError(str(detail.get("error", "Control request failed"))) from exc
    except (OSError, ValueError) as exc:
        raise ControlClientError(f"Could not reach AutoClickTimer: {exc}") from exc

    if not isinstance(result, dict) or not result.get("ok", False):
        raise ControlClientError(str(result.get("error", "Control request failed")))
    return result

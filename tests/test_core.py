from __future__ import annotations

import json
import datetime
import time
import urllib.error
import urllib.request
import unittest

from app.control_server import ControlServer
from app.mcp_stdio import dispatch
from app.executor import ExecutorCallbacks, QueueExecutor
from app.models import Item
from app.power_manager import PowerManager


class ModelTests(unittest.TestCase):
    def test_item_profile_round_trip(self) -> None:
        item = Item.from_dict(
            {
                "total": 90,
                "action": "sleep",
                "sleep_cfg": {"pre_sleep_grace": 10, "post_wake_delay": 20},
            }
        )
        restored = Item.from_dict(item.to_dict())
        self.assertEqual(restored.total, 90)
        self.assertEqual(restored.sleep_cfg.post_wake_delay, 20)

    def test_item_rejects_unknown_action(self) -> None:
        with self.assertRaises(ValueError):
            Item.from_dict({"total": 1, "action": "unknown"})

    def test_item_parses_string_false_safely(self) -> None:
        item = Item.from_dict({"total": 1, "action": "enter", "require_foreground": "false"})
        self.assertFalse(item.require_foreground)

    def test_type_action_requires_prompt(self) -> None:
        with self.assertRaises(ValueError):
            Item.from_dict({"total": 1, "action": "type"})


class PowerMappingTests(unittest.TestCase):
    def test_cli_timeout_mappings(self) -> None:
        self.assertEqual(PowerManager.timeout_key(0), "never")
        self.assertEqual(PowerManager.timeout_key(1), "1_min")
        self.assertEqual(PowerManager.timeout_key(120), "120_min")
        self.assertEqual(PowerManager.display_timeout_key(120), "60_min")
        with self.assertRaises(ValueError):
            PowerManager.timeout_key(-1)


class ControlServerTests(unittest.TestCase):
    def test_authenticated_command_and_mcp_list(self) -> None:
        server = ControlServer(lambda payload: {"ok": True, "source": payload["source"], "command": payload["command"]})
        server.start()
        try:
            request = urllib.request.Request(
                f"{server.endpoint}/v1/command",
                data=json.dumps({"command": "status"}).encode(),
                method="POST",
                headers={"Content-Type": "application/json", "X-AutoClick-Token": server._token},
            )
            with urllib.request.urlopen(request) as response:
                body = json.loads(response.read().decode())
            self.assertEqual(body["source"], "CLI")

            mcp_request = urllib.request.Request(
                f"{server.endpoint}/mcp",
                data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).encode(),
                method="POST",
                headers={"Content-Type": "application/json", "X-AutoClick-Token": server._token},
            )
            with urllib.request.urlopen(mcp_request) as response:
                mcp_body = json.loads(response.read().decode())
            self.assertTrue(mcp_body["result"]["tools"])

            source_request = urllib.request.Request(
                f"{server.endpoint}/v1/command",
                data=json.dumps({"command": "status"}).encode(),
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "X-AutoClick-Token": server._token,
                    "X-AutoClick-Source": "MCP",
                },
            )
            with urllib.request.urlopen(source_request) as response:
                source_body = json.loads(response.read().decode())
            self.assertEqual(source_body["source"], "MCP")
        finally:
            server.stop()
    def test_unauthenticated_command_is_rejected(self) -> None:
        server = ControlServer(lambda payload: {"ok": True})
        server.start()
        try:
            request = urllib.request.Request(
                f"{server.endpoint}/v1/command",
                data=b'{"command":"status"}',
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(request)
        finally:
            server.stop()

    def test_mcp_rejects_malformed_params(self) -> None:
        response = dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": []})
        self.assertEqual(response["error"]["code"], -32602)

    def test_mcp_error_codes_match_stdio(self) -> None:
        server = ControlServer(lambda payload: {"ok": False, "error": "bad command"})
        server.start()
        try:
            request = urllib.request.Request(
                f"{server.endpoint}/mcp",
                data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "queue_status"}}).encode(),
                method="POST",
                headers={"Content-Type": "application/json", "X-AutoClick-Token": server._token},
            )
            with urllib.request.urlopen(request) as response:
                body = json.loads(response.read().decode())
            self.assertEqual(body["error"]["code"], -32000)
        finally:
            server.stop()


class ExecutorTests(unittest.TestCase):
    def test_cancelled_scheduled_start_notifies_stopped(self) -> None:
        events: list[str] = []
        callbacks = ExecutorCallbacks(
            on_tick=lambda item: None,
            on_step_start=lambda item, index, total: None,
            on_step_done=lambda item: None,
            on_all_done=lambda count: events.append("done"),
            on_stopped=lambda: events.append("stopped"),
            on_log=lambda message: None,
            on_failsafe=lambda: events.append("failsafe"),
        )
        executor = QueueExecutor(callbacks)
        executor.start([Item(1, "enter")], datetime.datetime.now() + datetime.timedelta(seconds=10))
        time.sleep(0.1)
        executor.stop()
        assert executor._thread is not None
        executor._thread.join(timeout=2)
        self.assertEqual(events, ["stopped"])


if __name__ == "__main__":
    unittest.main()

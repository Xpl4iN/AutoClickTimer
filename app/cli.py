"""Command-line interface for controlling a running AutoClickTimer window."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from app.control_client import ControlClientError, request
from app.models import Item, SleepConfig
from app.power_manager import PowerManager


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autoclicktimer.py --cli")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("status", "list"):
        sub.add_parser(name, help="show queue and control status")
    sub.add_parser("stop", help="stop the active queue")
    sub.add_parser("reset", help="reset all queue items")
    sub.add_parser("clear", help="clear the queue")

    add = sub.add_parser("add", help="add one action to the queue")
    add.add_argument("--action", choices=("enter", "click", "type", "sleep", "shutdown"), required=True)
    add.add_argument("--duration", "--after", dest="total", type=int, required=True, help="delay in seconds")
    add.add_argument("--label", default="")
    add.add_argument("--prompt", default="")
    add.add_argument("--pre-sleep-grace", type=int, default=5)
    add.add_argument("--post-wake-delay", type=int, default=30)
    add.add_argument("--target-window", default="")
    add.add_argument("--foreground", action="store_true", help="bring the target window to the foreground")

    schedule = sub.add_parser("schedule-enter", help="add an Enter action and start the queue")
    schedule.add_argument("--after", type=int, required=True, help="delay in seconds")
    schedule.add_argument("--label", default="Scheduled Enter")

    start = sub.add_parser("start", help="start the current queue")
    start.add_argument("--delay-minutes", type=int, default=0)

    power = sub.add_parser("power", help="read or change power-plan timeouts")
    power_sub = power.add_subparsers(dest="power_command", required=True)
    power_sub.add_parser("get", help="show power settings")
    power_set = power_sub.add_parser("set", help="set idle sleep timeout in minutes; zero means never")
    power_set.add_argument("--ac-sleep", type=int)
    power_set.add_argument("--battery-sleep", "--dc-sleep", dest="dc_sleep", type=int)
    power_set.add_argument("--ac-display", type=int)
    power_set.add_argument("--battery-display", "--dc-display", dest="dc_display", type=int)

    return parser


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command in ("status", "list"):
            result = request({"command": "status"})
        elif args.command == "add":
            if args.action == "type" and not args.prompt.strip():
                raise ValueError("--prompt is required for type actions")
            item = Item(
                total=args.total,
                action=args.action,
                prompt=args.prompt,
                label=args.label,
                sleep_cfg=SleepConfig(args.pre_sleep_grace, args.post_wake_delay),
                target_window=args.target_window,
                require_foreground=args.foreground,
            )
            result = request({"command": "add", "item": item.to_dict()})
        elif args.command == "schedule-enter":
            item = Item(total=args.after, action="enter", label=args.label)
            result = request({"command": "add", "item": item.to_dict()})
            if result.get("ok"):
                result = request({"command": "start"})
        elif args.command == "start":
            result = request({"command": "start", "delay_minutes": args.delay_minutes})
        elif args.command in ("stop", "reset", "clear"):
            result = request({"command": args.command})
        elif args.command == "power":
            if args.power_command == "get":
                result = request({"command": "power_get"})
            else:
                result = _power_set(args)
        else:
            parser.error("unknown command")
            return 2
    except (ControlClientError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _power_set(args: argparse.Namespace) -> dict[str, Any]:
    if all(value is None for value in (args.ac_sleep, args.dc_sleep, args.ac_display, args.dc_display)):
        raise ValueError("provide at least one power timeout")
    current = request({"command": "power_get"})
    settings = current.get("settings", {})
    for source, sleep_minutes, display_minutes in (
        ("plugged_in", args.ac_sleep, args.ac_display),
        ("on_battery", args.dc_sleep, args.dc_display),
    ):
        values = settings.get(source, {})
        if sleep_minutes is not None:
            values["sleep_timeout"] = PowerManager.timeout_key(sleep_minutes)
        if display_minutes is not None:
            values["display_timeout"] = PowerManager.display_timeout_key(display_minutes)
        settings[source] = values
    return request({"command": "power_set", "settings": settings})

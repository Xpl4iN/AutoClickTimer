"""
app/models.py -- Pure data layer.

Defines Item (a queue entry) and SleepConfig (configurable sleep parameters).
No UI imports allowed here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ActionType = Literal["enter", "click", "type", "sleep", "shutdown"]

ACTION_LABELS: dict[str, str] = {
    "enter": "Enter drücken",
    "click": "Linksklick",
    "type": "Prompt senden",
    "sleep": "Sleep & Wake",
    "shutdown": "Herunterfahren",
}


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str) and value.strip().lower() in {"true", "1", "yes", "on"}:
        return True
    if isinstance(value, str) and value.strip().lower() in {"false", "0", "no", "off", ""}:
        return False
    raise ValueError("require_foreground must be a boolean")


@dataclass
class SleepConfig:
    """Configurable timing parameters for the Sleep & Wake action."""

    # Seconds to wait after registering the wake task and before issuing suspend.
    # Gives the user time to position the mouse / close windows.
    pre_sleep_grace: int = 5

    # Seconds to wait after the PC wakes before the next queue item begins.
    post_wake_delay: int = 30

    def __post_init__(self) -> None:
        self.pre_sleep_grace = max(0, int(self.pre_sleep_grace))
        self.post_wake_delay = max(0, int(self.post_wake_delay))


@dataclass
class Item:
    """One entry in the automation queue."""

    total: int                          # Duration in seconds (wait time or sleep time)
    action: ActionType                  # What to do when the timer expires
    prompt: str = ""                    # Text payload for the "type" action
    label: str = ""                     # Human-readable display name
    sleep_cfg: SleepConfig = field(default_factory=SleepConfig)
    target_window: str = ""             # The window title to target (empty means global)
    require_foreground: bool = False    # Whether to force the target window to foreground

    # ---- Runtime state (not constructor arguments) ----
    status: str = field(default="waiting", init=False, repr=False)
    rem: int = field(init=False, repr=False)
    phase: str = field(default="", init=False, repr=False)
    phase_total: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        self.total = max(0, int(self.total))
        self.rem = self.total
        self.phase_total = self.total
        if not self.label:
            self.label = ACTION_LABELS.get(self.action, self.action)

    def to_dict(self) -> dict[str, Any]:
        """Return the user-configurable fields for profiles and remote control."""
        return {
            "total": self.total,
            "action": self.action,
            "prompt": self.prompt,
            "label": self.label,
            "sleep_cfg": {
                "pre_sleep_grace": self.sleep_cfg.pre_sleep_grace,
                "post_wake_delay": self.sleep_cfg.post_wake_delay,
            },
            "target_window": self.target_window,
            "require_foreground": self.require_foreground,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Item":
        """Build an item from a profile or a validated remote command payload."""
        if not isinstance(data, dict):
            raise ValueError("Item must be an object")

        action = str(data.get("action", ""))
        if action not in ACTION_LABELS:
            raise ValueError(f"Unsupported action: {action or '<missing>'}")

        try:
            total = int(data.get("total", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError("total must be an integer") from exc
        if total <= 0:
            raise ValueError("total must be greater than zero")

        raw_cfg = data.get("sleep_cfg") or {}
        if not isinstance(raw_cfg, dict):
            raise ValueError("sleep_cfg must be an object")
        sleep_cfg = SleepConfig(
            pre_sleep_grace=raw_cfg.get("pre_sleep_grace", 5),
            post_wake_delay=raw_cfg.get("post_wake_delay", 30),
        )
        prompt = str(data.get("prompt", ""))
        if action == "type" and not prompt.strip():
            raise ValueError("prompt is required for type actions")

        return cls(
            total=total,
            action=action,  # type: ignore[arg-type]
            prompt=prompt,
            label=str(data.get("label", "")),
            sleep_cfg=sleep_cfg,
            target_window=str(data.get("target_window", "")),
            require_foreground=_parse_bool(data.get("require_foreground", False)),
        )

    def reset(self) -> None:
        """Return item to its initial waiting state."""
        self.status = "waiting"
        self.rem = self.total
        self.phase = ""
        self.phase_total = self.total

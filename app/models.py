"""
app/models.py -- Pure data layer.

Defines Item (a queue entry) and SleepConfig (configurable sleep parameters).
No UI imports allowed here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ActionType = Literal["enter", "click", "type", "sleep", "shutdown"]

ACTION_LABELS: dict[str, str] = {
    "enter": "Enter druecken",
    "click": "Linksklick",
    "type": "Prompt senden",
    "sleep": "Sleep & Wake",
    "shutdown": "Herunterfahren",
}


@dataclass
class SleepConfig:
    """Configurable timing parameters for the Sleep & Wake action."""

    # Seconds to wait after registering the wake task and before issuing suspend.
    # Gives the user time to position the mouse / close windows.
    pre_sleep_grace: int = 5

    # Seconds to wait after the PC wakes before the next queue item begins.
    post_wake_delay: int = 30


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
        self.rem = self.total
        self.phase_total = self.total
        if not self.label:
            self.label = ACTION_LABELS.get(self.action, self.action)

    def reset(self) -> None:
        """Return item to its initial waiting state."""
        self.status = "waiting"
        self.rem = self.total
        self.phase = ""
        self.phase_total = self.total

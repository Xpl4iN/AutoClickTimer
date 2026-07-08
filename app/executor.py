"""
app/executor.py -- Background queue runner.

QueueExecutor owns the worker thread and dispatches actions.
It NEVER touches CTk widgets directly -- all state changes go through
the ExecutorCallbacks, which the App wires to root.after(0, fn).

Public API:
    executor = QueueExecutor(callbacks)
    executor.start(queue)   # starts background thread
    executor.stop()         # signals stop; thread exits at next checkpoint
    executor.running        # property
"""
from __future__ import annotations

import time
import threading
from dataclasses import dataclass
from typing import Callable, List, Optional

import pyautogui
import pyperclip

from app.models import Item
from app.sleep_manager import SleepManager, MAX_RETRIES as SLEEP_MAX_RETRIES

MAX_ACTION_RETRIES = 3
_ACTION_RETRY_DELAY = 1.0   # seconds between action retries


def _fmt(seconds: int) -> str:
    s = max(0, seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


@dataclass
class ExecutorCallbacks:
    """
    All callbacks are invoked from the worker thread.
    The App must wrap each in root.after(0, fn) before passing to ensure
    they run on the Tk main thread.
    """
    on_tick: Callable[[Item], None]                  # item.rem / phase updated (~2.5 Hz)
    on_step_start: Callable[[Item, int, int], None]  # (item, 0-based index, queue length)
    on_step_done: Callable[[Item], None]             # item finished cleanly
    on_all_done: Callable[[int], None]               # all items done; arg = queue length
    on_stopped: Callable[[], None]                   # user called stop()
    on_log: Callable[[str], None]                    # emit a log line
    on_failsafe: Callable[[], None]                  # pyautogui failsafe triggered


class QueueExecutor:
    def __init__(self, callbacks: ExecutorCallbacks) -> None:
        self._cb = callbacks
        self._stop_ev = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._sleep_mgr = SleepManager(callbacks.on_log)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, queue: List[Item]) -> None:
        if self.running:
            return
        for item in queue:
            item.reset()
        self._stop_ev.clear()
        self._thread = threading.Thread(
            target=self._run, args=(list(queue),), daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the worker to stop at the next cancellation checkpoint."""
        self._stop_ev.set()

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------

    def _run(self, queue: List[Item]) -> None:
        try:
            for i, item in enumerate(queue):
                if self._stop_ev.is_set():
                    break

                item.status = "running"
                self._cb.on_step_start(item, i, len(queue))
                self._cb.on_log(
                    f"Schritt {i + 1}/{len(queue)}: [{item.label}] -- {_fmt(item.total)}"
                )

                if item.action == "sleep":
                    completed = self._handle_sleep(item)
                else:
                    completed = self._countdown(item, item.total)
                    if completed:
                        self._dispatch_with_retry(item)

                if self._stop_ev.is_set():
                    break

                item.rem = 0
                item.status = "done"
                self._cb.on_step_done(item)
                self._cb.on_log(f"Schritt {i + 1} abgeschlossen.")

        except pyautogui.FailSafeException:
            self._cb.on_log("WARNUNG Failsafe ausgeloest -- Abbruch!")
            self._cb.on_failsafe()
            return

        if not self._stop_ev.is_set():
            self._cb.on_all_done(len(queue))
        else:
            self._cb.on_stopped()

    # ------------------------------------------------------------------
    # Sleep item handler
    # ------------------------------------------------------------------

    def _handle_sleep(self, item: Item) -> bool:
        """
        Three-phase handler for sleep items:
          Phase 1 -- grace countdown (PC still awake, user can abort)
          Phase 2 -- suspend (with retry); or awake fallback if all retries fail
          Phase 3 -- post-wake delay countdown
        Returns True if the whole sleep sequence completed, False if stopped.
        """
        cfg = item.sleep_cfg

        # ---- Phase 1: pre-sleep grace countdown ----
        self._cb.on_log(
            f"  -> Vorbereitung: {cfg.pre_sleep_grace}s Wartezeit bevor PC in Ruhezustand geht."
        )
        item.phase = "grace"
        item.phase_total = cfg.pre_sleep_grace
        if not self._countdown(item, cfg.pre_sleep_grace):
            return False

        if self._stop_ev.is_set():
            return False

        # ---- Phase 2: suspend ----
        item.phase = "sleeping"
        item.phase_total = item.total
        item.rem = item.total
        self._cb.on_tick(item)
        self._cb.on_log(
            f"  -> Ruhezustand wird eingeleitet fuer {_fmt(item.total)}..."
        )

        slept = self._sleep_mgr.execute_with_retry(
            total_seconds=item.total,
            pre_grace=0,   # grace already handled in phase 1
        )

        if slept:
            # ---- Phase 3: post-wake delay ----
            item.phase = "post_wake"
            item.phase_total = cfg.post_wake_delay
            self._cb.on_log(
                f"  -> Aufgewacht. Post-Wake Verzoegerung: {cfg.post_wake_delay}s"
            )
            self._countdown(item, cfg.post_wake_delay)
        else:
            # ---- Fallback: stay awake, count down full sleep duration ----
            self._cb.on_log(
                f"  -> Ruhezustand nach {SLEEP_MAX_RETRIES} Versuchen fehlgeschlagen. "
                f"Bleibe wach und zaehle {_fmt(item.total)} herunter, "
                f"damit die naechste Aktion zur richtigen Zeit ausgefuehrt wird."
            )
            item.phase = "awake_fallback"
            item.phase_total = item.total
            self._countdown(item, item.total)

        return not self._stop_ev.is_set()

    # ------------------------------------------------------------------
    # Countdown
    # ------------------------------------------------------------------

    def _countdown(self, item: Item, duration: int) -> bool:
        """
        Count down 'duration' seconds, updating item.rem every ~0.4s.
        Uses time.monotonic() which continues across system sleep/wake.
        Returns True if completed, False if stop_ev fired.
        """
        t0 = time.monotonic()
        while not self._stop_ev.is_set():
            elapsed = time.monotonic() - t0
            item.rem = max(0, duration - int(elapsed))
            self._cb.on_tick(item)
            if elapsed >= duration:
                return True
            time.sleep(0.4)
        return False

    # ------------------------------------------------------------------
    # Action dispatch
    # ------------------------------------------------------------------

    def _dispatch_with_retry(self, item: Item) -> None:
        """
        Try to execute item's action up to MAX_ACTION_RETRIES times.
        Logs every failure. If all retries fail, logs and continues the queue.
        Propagates FailSafeException without retrying.
        """
        for attempt in range(1, MAX_ACTION_RETRIES + 1):
            try:
                _dispatch_action(item)
                self._cb.on_log(f"  -> Aktion '{item.action}' ausgefuehrt.")
                return
            except pyautogui.FailSafeException:
                raise  # let outer handler catch this
            except Exception as exc:
                self._cb.on_log(
                    f"  WARNUNG Aktions-Versuch {attempt}/{MAX_ACTION_RETRIES} fehlgeschlagen: {exc}"
                )
                if attempt < MAX_ACTION_RETRIES:
                    time.sleep(_ACTION_RETRY_DELAY)

        self._cb.on_log(
            f"  FEHLER Aktion nach {MAX_ACTION_RETRIES} Versuchen nicht ausfuehrbar -- uebersprungen."
        )


# ------------------------------------------------------------------
# Pure action dispatch (no retry, no UI coupling)
# ------------------------------------------------------------------

def _dispatch_action(item: Item) -> None:
    """Execute the physical action for item. May raise any exception."""
    time.sleep(0.2)  # brief stabilisation delay
    if item.action == "enter":
        pyautogui.press("enter")
    elif item.action == "click":
        pyautogui.click()
    elif item.action == "type":
        pyperclip.copy(item.prompt)
        time.sleep(0.3)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.35)
        pyautogui.press("enter")
    elif item.action == "sleep":
        pass  # sleep items don't dispatch a physical action

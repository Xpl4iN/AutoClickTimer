"""
app/sleep_manager.py -- OS-level sleep and wake scheduling.

Encapsulates all powercfg, schtasks, and PowerShell suspend calls.
The only public API is:

    SleepManager(log_fn).execute_with_retry(total_seconds, pre_grace) -> bool

Returns True if the PC actually slept and woke, False after MAX_RETRIES failures.
"""
from __future__ import annotations

import base64
import datetime
import subprocess
import time
from typing import Callable


# Minimum elapsed time (seconds above pre_grace) needed to confirm the PC
# actually entered suspend. Keep at 30s so tests with very short durations
# are not accidentally classified as successes.
_MIN_CONFIRM_BUFFER = 30

MAX_RETRIES = 3
_RETRY_DELAY = 2   # seconds between retries
_POST_SUSPEND_WAIT = 5  # seconds we sleep() after Popen -- will be suspended with the PC


def _encode_ps(script: str) -> str:
    """Encode a PowerShell script as UTF-16LE base64 for -EncodedCommand."""
    return base64.b64encode(script.encode("utf-16le")).decode("ascii")


class SleepError(Exception):
    """Raised when a sleep attempt cannot be completed."""


class SleepManager:
    TASK_NAME = "SleepWakeTask"

    def __init__(self, log_fn: Callable[[str], None]) -> None:
        self._log = log_fn

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute_with_retry(self, total_seconds: int, pre_grace: int = 0) -> bool:
        """
        Attempt to put the PC to sleep for total_seconds.

        pre_grace: extra seconds to wait before issuing suspend on each attempt.
                   (The executor's phase-1 grace countdown already runs before
                   this is called, so pass 0 unless you want additional per-attempt
                   settling time.)

        Returns True if the PC successfully slept and woke, False if all
        MAX_RETRIES attempts failed. Logs every attempt and failure.
        """
        for attempt in range(1, MAX_RETRIES + 1):
            self._log(f"  -> Sleep attempt {attempt}/{MAX_RETRIES}...")
            try:
                self._configure_power()
                wake_at = datetime.datetime.now() + datetime.timedelta(seconds=total_seconds)
                self._schedule_wake(wake_at)
                slept = self._suspend_and_detect(pre_grace, total_seconds)
                if not slept:
                    raise SleepError(
                        f"PC returned after only ~{_POST_SUSPEND_WAIT + pre_grace}s "
                        f"-- suspend did not occur"
                    )
                self._log("  -> PC woke successfully.")
                return True
            except SleepError as exc:
                self._log(f"  WARNING Attempt {attempt}/{MAX_RETRIES} failed: {exc}")
                if attempt < MAX_RETRIES:
                    self._log(f"  -> Retrying in {_RETRY_DELAY}s...")
                    time.sleep(_RETRY_DELAY)
        return False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _configure_power(self) -> None:
        """Enable RTC wake timers and disable unattended sleep timeout."""
        pairs = [
            ("SETACVALUEINDEX", "RTCWAKE", "1"),
            ("SETDCVALUEINDEX", "RTCWAKE", "1"),
            ("SETACVALUEINDEX", "7bc4a2f9-d8fc-4469-b07b-33eb785aaca0", "0"),
            ("SETDCVALUEINDEX", "7bc4a2f9-d8fc-4469-b07b-33eb785aaca0", "0"),
        ]
        for verb, setting, value in pairs:
            r = subprocess.run(
                ["powercfg", f"/{verb}", "SCHEME_CURRENT", "SUB_SLEEP", setting, value],
                capture_output=True,
            )
            if r.returncode != 0:
                stderr = r.stderr.decode(errors="ignore").strip()
                self._log(f"  WARNING powercfg {setting}: {stderr or 'non-zero exit'}")

        subprocess.run(["powercfg", "/SETACTIVE", "SCHEME_CURRENT"], capture_output=True)

    def _schedule_wake(self, wake_at: datetime.datetime) -> None:
        """Register a SYSTEM scheduled task to wake and unlock the session at wake_at."""
        task_name = self.TASK_NAME
        wake_str = wake_at.strftime("%Y-%m-%dT%H:%M:%S")

        # Remove any existing task with the same name
        subprocess.run(["schtasks", "/Delete", "/TN", task_name, "/F"], capture_output=True)

        # Session-reconnect payload: reconnects the active session to the console
        # so the desktop is unlocked after wake.
        ps_payload = (
            f"$sid = (Get-Process explorer -ErrorAction SilentlyContinue "
            f"| Select-Object -First 1).SessionId; "
            f"if ($sid -ne $null) {{ tscon $sid /dest:console }}; "
            f"Unregister-ScheduledTask -TaskName '{task_name}' -Confirm:$false"
        )

        register_ps = (
            f"$a = New-ScheduledTaskAction "
            f"-Execute 'powershell.exe' "
            f"-Argument '-NoProfile -WindowStyle Hidden -EncodedCommand {_encode_ps(ps_payload)}'; "
            f"$t = New-ScheduledTaskTrigger -Once -At '{wake_str}'; "
            f"$s = New-ScheduledTaskSettingsSet -WakeToRun -AllowStartIfOnBatteries; "
            f"Register-ScheduledTask -TaskName '{task_name}' "
            f"-Action $a -Trigger $t -Settings $s "
            f"-User 'NT AUTHORITY\\SYSTEM' -Force"
        )

        r = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-WindowStyle", "Hidden",
                "-EncodedCommand", _encode_ps(register_ps),
            ],
            capture_output=True,
        )
        if r.returncode != 0:
            stderr = r.stderr.decode(errors="ignore").strip()
            raise SleepError(f"Failed to register wake task: {stderr}")

    def _suspend_and_detect(self, pre_grace: int, expected_sleep: int) -> bool:
        """
        Optionally wait pre_grace seconds, then issue a suspend command.

        After the PC wakes, execution resumes here (Python is suspended along
        with the rest of the system during S3 sleep). We detect whether a real
        sleep occurred by checking total elapsed time.

        Returns True if elapsed time confirms the PC slept, False otherwise.
        """
        t_start = time.monotonic()

        if pre_grace > 0:
            time.sleep(pre_grace)

        suspend_ps = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "[System.Windows.Forms.Application]::SetSuspendState("
            "[System.Windows.Forms.PowerState]::Suspend, $false, $false)"
        )
        subprocess.Popen(
            [
                "powershell.exe", "-NoProfile", "-WindowStyle", "Hidden",
                "-EncodedCommand", _encode_ps(suspend_ps),
            ]
        )

        # time.sleep() here will itself be suspended when the PC enters S3.
        # When the PC wakes, this sleep() resumes and eventually returns,
        # after which we measure how long we were actually gone.
        time.sleep(_POST_SUSPEND_WAIT)

        elapsed = time.monotonic() - t_start
        threshold = pre_grace + _MIN_CONFIRM_BUFFER
        return elapsed >= threshold

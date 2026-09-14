"""
Windows power-plan settings used by the Power and Lid dialog.

The values are kept as small, UI-independent data objects so the UI can be
tested without a Windows desktop. `powercfg` remains the source of truth for
the active power plan.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass


ACTION_VALUES: dict[str, int] = {
    "do_nothing": 0,
    "sleep": 1,
    "hibernate": 2,
    "shutdown": 3,
}

DISPLAY_TIMEOUTS: dict[str, int] = {
    "never": 0,
    "1_min": 60,
    "5_min": 300,
    "10_min": 600,
    "15_min": 900,
    "30_min": 1800,
    "60_min": 3600,
}


@dataclass
class PowerSourceSettings:
    lid_action: str = "sleep"
    power_button_action: str = "sleep"
    display_timeout: str = "15_min"


@dataclass
class PowerSettings:
    plugged_in: PowerSourceSettings
    on_battery: PowerSourceSettings


class PowerSettingsError(RuntimeError):
    """Raised when Windows cannot read or write the active power plan."""


class PowerManager:
    """Read and write lid, power-button, and display timeout settings."""

    _SETTING_PATHS = {
        "lid_action": ("SUB_BUTTONS", "LIDACTION"),
        "power_button_action": ("SUB_BUTTONS", "PBUTTONACTION"),
        "display_timeout": ("SUB_VIDEO", "VIDEOIDLE"),
    }

    def read_settings(self) -> PowerSettings:
        return PowerSettings(
            plugged_in=self._read_source("ac"),
            on_battery=self._read_source("dc"),
        )

    def apply_settings(self, settings: PowerSettings) -> None:
        failures: list[str] = []
        for source, values in (("ac", settings.plugged_in), ("dc", settings.on_battery)):
            for key, value in (
                ("lid_action", values.lid_action),
                ("power_button_action", values.power_button_action),
                ("display_timeout", values.display_timeout),
            ):
                if key == "display_timeout":
                    numeric_value = DISPLAY_TIMEOUTS.get(value)
                else:
                    numeric_value = ACTION_VALUES.get(value)
                if numeric_value is None:
                    failures.append(f"Unknown {key} value: {value}")
                    continue

                subgroup, setting = self._SETTING_PATHS[key]
                result = self._run(
                    "powercfg",
                    f"/SET{source.upper()}VALUEINDEX",
                    "SCHEME_CURRENT",
                    subgroup,
                    setting,
                    str(numeric_value),
                )
                if result.returncode != 0:
                    failures.append(self._error_text(result, setting))

        active_result = self._run("powercfg", "/SETACTIVE", "SCHEME_CURRENT")
        if active_result.returncode != 0:
            failures.append(self._error_text(active_result, "SETACTIVE"))

        if failures:
            raise PowerSettingsError("; ".join(failures))

    def _read_source(self, source: str) -> PowerSourceSettings:
        values: dict[str, str] = {}
        for key, (subgroup, setting) in self._SETTING_PATHS.items():
            result = self._run("powercfg", "/QUERY", "SCHEME_CURRENT", subgroup, setting)
            if result.returncode != 0:
                raise PowerSettingsError(self._error_text(result, setting))
            raw_value = self._parse_value(result.stdout, source)
            if raw_value is None:
                raise PowerSettingsError(f"Could not read {source.upper()} value for {setting}")

            if key == "display_timeout":
                values[key] = self._timeout_key(raw_value)
            else:
                values[key] = self._action_key(raw_value)

        return PowerSourceSettings(**values)

    @staticmethod
    def _run(*args: str) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                list(args),
                capture_output=True,
                text=True,
                errors="replace",
                check=False,
            )
        except OSError as exc:
            raise PowerSettingsError(str(exc)) from exc

    @staticmethod
    def _parse_value(output: str, source: str) -> int | None:
        source_name = "AC" if source == "ac" else "DC"
        pattern = rf"Current\s+{source_name}\s+Power\s+Setting\s+Index\s*:\s*0x([0-9a-f]+)"
        match = re.search(pattern, output, re.IGNORECASE)
        if not match:
            return None
        return int(match.group(1), 16)

    @staticmethod
    def _action_key(value: int) -> str:
        for key, numeric_value in ACTION_VALUES.items():
            if value == numeric_value:
                return key
        return "do_nothing"

    @staticmethod
    def _timeout_key(value: int) -> str:
        for key, numeric_value in DISPLAY_TIMEOUTS.items():
            if value == numeric_value:
                return key
        # Preserve arbitrary existing plans as the nearest visible choice.
        if value <= 60:
            return "1_min"
        if value <= 300:
            return "5_min"
        if value <= 600:
            return "10_min"
        if value <= 900:
            return "15_min"
        if value <= 1800:
            return "30_min"
        return "60_min"

    @staticmethod
    def _error_text(result: subprocess.CompletedProcess[str], setting: str) -> str:
        detail = (result.stderr or result.stdout or "non-zero exit").strip()
        return f"powercfg {setting}: {detail}"

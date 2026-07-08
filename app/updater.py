"""
app/updater.py -- GitHub release-based auto-updater.

Public API:
    checker = UpdateChecker(repo, current_version)
    info    = checker.check()                        # None = up to date / error
    checker.download_and_apply(info, on_log)         # downloads, then restarts

All network I/O is synchronous -- run check() and download_and_apply() from a
daemon thread so the UI stays responsive.

Self-replace strategy (Windows):
  1. Download new EXE to <current_exe>.new
  2. Write a tiny .bat that waits 2 s, copies .new over current exe, relaunches
  3. Launch the bat with CREATE_NO_WINDOW, then os._exit(0)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional


GITHUB_API = "https://api.github.com/repos/{repo}/releases/latest"
_HEADERS   = {"User-Agent": "AutoClickTimer-Updater/1.0"}


@dataclass
class UpdateInfo:
    tag:          str   # e.g. "v1.1.0"
    version:      str   # e.g. "1.1.0"
    download_url: str   # direct URL to the new .exe
    release_url:  str   # GitHub Releases page URL


def _parse_ver(s: str) -> tuple:
    """'1.2.3' -> (1, 2, 3) for simple tuple comparison."""
    try:
        return tuple(int(x) for x in s.lstrip("v").split("."))
    except Exception:
        return (0,)


class UpdateChecker:
    def __init__(self, repo: str, current_version: str) -> None:
        self._repo    = repo
        self._current = _parse_ver(current_version)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self) -> Optional[UpdateInfo]:
        """
        Query the GitHub API for the latest release.
        Returns UpdateInfo if a newer version exists, None otherwise.
        Silently swallows all network/parse errors.
        """
        try:
            req = urllib.request.Request(
                GITHUB_API.format(repo=self._repo), headers=_HEADERS
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())

            tag        = data.get("tag_name", "")
            version    = tag.lstrip("v")
            latest_ver = _parse_ver(version)

            if latest_ver <= self._current:
                return None

            # Find the first .exe asset
            exe_asset = next(
                (a for a in data.get("assets", []) if a["name"].lower().endswith(".exe")),
                None,
            )
            if not exe_asset:
                return None

            return UpdateInfo(
                tag=tag,
                version=version,
                download_url=exe_asset["browser_download_url"],
                release_url=data.get("html_url", ""),
            )
        except Exception:
            return None

    def download_and_apply(
        self,
        info: UpdateInfo,
        on_log: Callable[[str], None],
    ) -> None:
        """
        Download the new EXE and trigger a self-replace restart.
        Only works when running as a frozen PyInstaller EXE (sys.frozen=True).
        Calls on_log() with progress messages -- wrap in root.after(0,...) before
        passing if calling from a background thread.
        """
        if not getattr(sys, "frozen", False):
            on_log("Automatische Updates funktionieren nur in der kompilierten EXE-Version.")
            return

        current_exe = sys.executable
        tmp_path    = current_exe + ".new"
        bat_path    = current_exe + ".update.bat"

        # ---- Download ----
        on_log(f"Herunterladen von Version {info.version}...")
        try:
            _downloaded = [0]

            def _progress(count: int, block: int, total: int) -> None:
                if total > 0:
                    pct = min(100, count * block * 100 // total)
                    # Log every ~5 %
                    prev = (count - 1) * block * 100 // total if count else 0
                    if pct // 5 != prev // 5 or pct == 100:
                        on_log(f"  ... {pct}%")

            urllib.request.urlretrieve(info.download_url, tmp_path, _progress)
            on_log("Download abgeschlossen. Update wird vorbereitet...")
        except Exception as exc:
            on_log(f"  FEHLER Download fehlgeschlagen: {exc}")
            _cleanup(tmp_path)
            return

        # ---- Write updater batch ----
        bat = (
            "@echo off\n"
            "timeout /t 2 /nobreak > nul\n"
            f'copy /y "{tmp_path}" "{current_exe}"\n'
            "if errorlevel 1 (\n"
            f'  echo Update fehlgeschlagen. Bitte {tmp_path} manuell ersetzen.\n'
            "  pause\n"
            "  goto :eof\n"
            ")\n"
            f'del "{tmp_path}"\n'
            f'start "" "{current_exe}"\n'
            'del "%~f0"\n'
        )
        try:
            with open(bat_path, "w") as fh:
                fh.write(bat)
        except Exception as exc:
            on_log(f"  FEHLER Batch-Datei konnte nicht erstellt werden: {exc}")
            _cleanup(tmp_path)
            return

        on_log("Neustart zum Anwenden des Updates...")
        try:
            subprocess.Popen(
                ["cmd.exe", "/c", bat_path],
                creationflags=subprocess.CREATE_NO_WINDOW,
                close_fds=True,
            )
        except Exception as exc:
            on_log(f"  FEHLER Batch-Datei konnte nicht gestartet werden: {exc}")
            _cleanup(tmp_path, bat_path)
            return

        os._exit(0)   # release file lock so the batch can copy


def _cleanup(*paths: str) -> None:
    for p in paths:
        try:
            os.remove(p)
        except Exception:
            pass

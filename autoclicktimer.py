#!/usr/bin/env python3
"""
AutoClick Timer -- entry point.

Installs missing dependencies, requests administrator privileges (required
for the Sleep & Wake scheduled-task feature), then launches the UI.
"""
import sys
import subprocess
import os


def _ensure_deps() -> None:
    """Auto-install missing Python packages."""
    for pkg in ["pyautogui", "pyperclip", "customtkinter"]:
        try:
            __import__(pkg)
        except ImportError:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


def _elevate() -> None:
    """Re-launch with administrator privileges if not already elevated."""
    try:
        import ctypes
        if ctypes.windll.shell32.IsUserAnAdmin():
            return  # already admin
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(f'"{a}"' for a in sys.argv), None, 1
        )
        sys.exit(0)
    except Exception:
        pass  # Non-Windows or UAC blocked -- continue without elevation


# Ensure the package root (directory containing this file) is on sys.path
# so that "from app.xxx import ..." resolves regardless of how the script
# is launched (directly, via PyInstaller, or as a module).
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

_ensure_deps()
_elevate()

import customtkinter as ctk  # noqa: E402
from app.ui.app_window import AppWindow  # noqa: E402

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    app = AppWindow()
    app.mainloop()

"""
app/ui/log_panel.py -- Self-contained log widget.

Interface:
    panel = LogPanel(parent_frame)
    panel.append("message")   # thread-safe via root.after; call from any thread
    panel.grid_configure(...)  # forward grid config to outer frame
"""
from __future__ import annotations

import time
import customtkinter as ctk

from app.ui.theme import (
    SURFACE, OUTLINE, ON_SURF_M,
    FONT_LABEL, FONT_MONO,
)


class LogPanel:
    """Scrollable log textbox with timestamp prefixes."""

    def __init__(self, parent: ctk.CTkFrame) -> None:
        self._frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._frame.grid_columnconfigure(0, weight=1)
        self._frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self._frame, text="LOG", font=FONT_LABEL, text_color=ON_SURF_M
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))

        self._box = ctk.CTkTextbox(
            self._frame,
            fg_color=SURFACE,
            border_width=1,
            border_color=OUTLINE,
            font=FONT_MONO,
            text_color=ON_SURF_M,
            height=36,  # minimum -- expands via grid weight
        )
        self._box.grid(row=1, column=0, sticky="nsew")
        self._box.configure(state="disabled")

    def grid(self, **kwargs) -> None:
        self._frame.grid(**kwargs)

    def grid_configure(self, **kwargs) -> None:
        self._frame.grid_configure(**kwargs)

    def append(self, msg: str) -> None:
        """Append a timestamped line. Must be called from the Tk main thread."""
        self._box.configure(state="normal")
        self._box.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self._box.see("end")
        self._box.configure(state="disabled")

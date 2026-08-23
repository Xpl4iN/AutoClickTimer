"""
app/ui/log_panel.py -- Self-contained collapsible log widget.

Interface:
    panel = LogPanel(parent_frame)
    panel.append("message")    # thread-safe via root.after; call from any thread
    panel.grid(...)            # grid placement
    panel.grid_configure(...)  # forward grid config to outer frame
"""
from __future__ import annotations

import time
import customtkinter as ctk

from app.ui.theme import (
    SURFACE, SURFACE_L, SURFACE_H, OUTLINE, PRIMARY, PRIMARY_HOV,
    ON_SURF, ON_SURF_M, ERROR,
    FONT_LABEL, FONT_MONO, FONT_SMALL, FONT_BODY, FONT_BOLD,
)


class LogPanel:
    """Collapsible log drawer with latest message status preview."""

    def __init__(self, parent: ctk.CTkFrame) -> None:
        self._is_expanded = False
        self._log_count = 0

        self._frame = ctk.CTkFrame(
            parent, fg_color=SURFACE,
            border_width=1, border_color=OUTLINE, corner_radius=12,
        )
        self._frame.grid_columnconfigure(0, weight=1)
        self._frame.grid_rowconfigure(0, weight=0)
        self._frame.grid_rowconfigure(1, weight=1)

        # ---- Header / Toolbar ----
        self._header = ctk.CTkFrame(self._frame, fg_color="transparent", height=34)
        self._header.grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 6))
        self._header.grid_columnconfigure(1, weight=1)

        # Toggle button with text and counter
        self._toggle_btn = ctk.CTkButton(
            self._header,
            text="Log ▲",
            width=70, height=26,
            font=FONT_SMALL,
            fg_color=SURFACE_L,
            hover_color=SURFACE_H,
            border_width=1,
            border_color=OUTLINE,
            text_color=ON_SURF,
            corner_radius=6,
            command=self.toggle,
        )
        self._toggle_btn.grid(row=0, column=0, padx=(0, 8), sticky="w")

        # Latest message preview label
        self._preview_lbl = ctk.CTkLabel(
            self._header,
            text="Bereit. Keine Aktionen ausgefuehrt.",
            font=FONT_SMALL,
            text_color=ON_SURF_M,
            anchor="w",
        )
        self._preview_lbl.grid(row=0, column=1, sticky="ew", padx=(0, 6))

        # Clear log button
        self._clear_btn = ctk.CTkButton(
            self._header,
            text="Leeren",
            width=50, height=26,
            font=FONT_SMALL,
            fg_color="transparent",
            hover_color="#2e1414",
            border_width=1,
            border_color=OUTLINE,
            text_color=ON_SURF_M,
            corner_radius=6,
            command=self.clear,
        )
        self._clear_btn.grid(row=0, column=2, sticky="e")

        # ---- Scrollable Text Box (hidden when collapsed) ----
        self._box = ctk.CTkTextbox(
            self._frame,
            fg_color=SURFACE_L,
            border_width=1,
            border_color=OUTLINE,
            font=FONT_MONO,
            text_color=ON_SURF,
            height=120,
            corner_radius=8,
        )
        self._box.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self._box.configure(state="disabled")

        # Start collapsed by default
        self._box.grid_remove()

    def grid(self, **kwargs) -> None:
        self._frame.grid(**kwargs)

    def grid_configure(self, **kwargs) -> None:
        self._frame.grid_configure(**kwargs)

    def toggle(self) -> None:
        """Toggle between expanded and collapsed state."""
        self._is_expanded = not self._is_expanded
        arrow = "▼" if self._is_expanded else "▲"
        count_str = f" ({self._log_count})" if self._log_count > 0 else ""
        if self._is_expanded:
            self._box.grid()
            self._toggle_btn.configure(text=f"Log{count_str} {arrow}")
        else:
            self._box.grid_remove()
            self._toggle_btn.configure(text=f"Log{count_str} {arrow}")

    def append(self, msg: str) -> None:
        """Append a timestamped line. Must be called from the Tk main thread."""
        ts = time.strftime('%H:%M:%S')
        formatted = f"[{ts}] {msg}"
        self._log_count += 1

        # Update preview label
        self._preview_lbl.configure(text=formatted)

        # Update toggle button text with count
        arrow = "▼" if self._is_expanded else "▲"
        self._toggle_btn.configure(text=f"Log ({self._log_count}) {arrow}")

        # Update full textbox
        self._box.configure(state="normal")
        self._box.insert("end", f"{formatted}\n")
        self._box.see("end")
        self._box.configure(state="disabled")

    def clear(self) -> None:
        """Clear the log content and reset counter."""
        self._box.configure(state="normal")
        self._box.delete("1.0", "end")
        self._box.configure(state="disabled")
        self._log_count = 0
        self._preview_lbl.configure(text="Log geleert.")
        arrow = "▼" if self._is_expanded else "▲"
        self._toggle_btn.configure(text=f"Log {arrow}")


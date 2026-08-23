"""
app/ui/queue_panel.py -- Scrollable queue + control buttons.

Interface:
    panel = QueuePanel(parent, on_start, on_stop, on_reset, on_clear, on_remove, is_running)
    panel.render(queue)               -- full re-render (call on structural changes)
    panel.update_row(item)            -- lightweight tick update for a single row
    panel.set_status(msg)             -- update the status label
    panel.set_controls_enabled(running: bool) -- toggle button states
"""
from __future__ import annotations

from typing import Callable, List, Optional, Tuple

import customtkinter as ctk

from app.models import Item
from app.ui.i18n import t, register_listener
from app.ui.theme import (
    SURFACE, SURFACE_L, SURFACE_H, OUTLINE,
    PRIMARY, PRIMARY_HOV, ON_SURF, ON_SURF_M, ERROR, SUCCESS, WARNING,
    FONT_BOLD, FONT_BODY, FONT_SMALL, FONT_LABEL, FONT_COUNT, FONT_NUM,
    fmt,
)

# Tuple stored per rendered row: (Item, row_frame, countdown_lbl, progress_bar, status_lbl)
_RowRef = Tuple[Item, ctk.CTkFrame, ctk.CTkLabel, ctk.CTkProgressBar, ctk.CTkLabel]


def _phase_display(item: Item) -> Tuple[str, str, str]:
    """
    Returns (status_text, countdown_text, countdown_color) based on item state and phase.
    """
    if item.status == "done":
        return t("status_done"), t("status_done"), SUCCESS
    if item.status == "waiting":
        return t("status_waiting"), fmt(item.total), ON_SURF_M
    # running
    if item.action == "sleep":
        phase_map = {
            "grace":          (t("status_grace"), fmt(item.rem), WARNING),
            "sleeping":       (t("status_sleeping"), t("status_sleeping"), PRIMARY),
            "post_wake":      (t("status_post_wake"), fmt(item.rem), SUCCESS),
            "awake_fallback": (t("status_awake_fallback"), fmt(item.rem), WARNING),
        }
        return phase_map.get(item.phase, (t("status_running"), fmt(item.rem), PRIMARY))
    return t("status_running"), fmt(item.rem), PRIMARY


def _phase_progress(item: Item) -> float:
    if item.status == "done":
        return 1.0
    if item.status == "waiting" or item.phase_total == 0:
        return 0.0
    elapsed = item.phase_total - item.rem
    return max(0.0, min(1.0, elapsed / item.phase_total))


class QueuePanel:
    def __init__(
        self,
        parent: ctk.CTkFrame,
        on_start:  Callable[[], None],
        on_stop:   Callable[[], None],
        on_reset:  Callable[[], None],
        on_clear:  Callable[[], None],
        on_remove: Callable[[Item], None],
        is_running: Callable[[], bool],
        on_save: Callable[[], None] = lambda: None,
        on_load: Callable[[], None] = lambda: None,
        on_start_later: Callable[[], None] = lambda: None,
    ) -> None:
        self._on_remove  = on_remove
        self._is_running = is_running
        self._rows: List[_RowRef] = []
        self._rendering = False
        self._current_queue: Optional[List[Item]] = None

        self._build_queue_area(parent)
        self._build_controls(parent, on_start, on_stop, on_reset, on_clear, on_save, on_load, on_start_later)
        register_listener(self.retranslate)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def retranslate(self, lang: str = "de") -> None:
        self._hdr_lbl.configure(text=t("queue_header"))
        self._empty_lbl.configure(text=t("empty_queue"))
        self._start_btn.configure(text=t("start_btn"))
        self._start_later_btn.configure(text=t("start_later_btn"))
        self._stop_btn.configure(text=t("stop_btn"))
        self._reset_btn.configure(text=t("reset_btn"))
        self._clear_btn.configure(text=t("clear_btn"))
        self._save_btn.configure(text=t("save_btn"))
        self._load_btn.configure(text=t("load_btn"))
        if self._current_queue is not None:
            self.render(self._current_queue)

    def render(self, queue: List[Item]) -> None:
        """Full re-render of all queue rows. Call on structural changes."""
        self._current_queue = queue
        if self._rendering:
            return
        self._rendering = True
        try:
            # pack_forget() before destroy() is required for CTkScrollableFrame:
            # destroy() removes the widget from Tk's tree but the canvas backing
            # the scrollable frame does not automatically repaint. pack_forget()
            # removes the widget from the layout pass, and update_idletasks()
            # forces the canvas to flush its pending draw queue.
            for ref in self._rows:
                try:
                    ref[1].pack_forget()
                    ref[1].destroy()
                except Exception:
                    pass
            self._rows.clear()
            self._scroll.update_idletasks()   # flush canvas redraws

            if not queue:
                self._empty_lbl.pack(pady=32)
                return
            self._empty_lbl.pack_forget()

            for i, item in enumerate(queue):
                self._rows.append(self._build_row(item, i))
        finally:
            self._rendering = False

    def update_row(self, item: Item) -> None:
        """Lightweight update -- refreshes countdown, progress, and status for one row."""
        for ref in self._rows:
            if ref[0] is item:
                _, row_frame, countdown_lbl, prog_bar, status_lbl = ref
                try:
                    if row_frame.winfo_exists():
                        status_text, cd_text, cd_color = _phase_display(item)
                        countdown_lbl.configure(text=cd_text, text_color=cd_color)
                        prog_bar.set(_phase_progress(item))
                        prog_color = SUCCESS if item.status == "done" else PRIMARY
                        prog_bar.configure(progress_color=prog_color)
                        status_lbl.configure(text=status_text)
                except Exception:
                    pass
                break

    def set_status(self, msg: str) -> None:
        self._stat.configure(text=msg)

    def set_controls_enabled(self, running: bool) -> None:
        if running:
            self._start_btn.configure(state="disabled")
            self._start_later_btn.configure(state="disabled")
            self._stop_btn.configure(state="normal")
            self._save_btn.configure(state="disabled")
            self._load_btn.configure(state="disabled")
        else:
            self._start_btn.configure(state="normal")
            self._start_later_btn.configure(state="normal")
            self._stop_btn.configure(state="normal")
            self._save_btn.configure(state="normal")
            self._load_btn.configure(state="normal")

    # ------------------------------------------------------------------
    # Build helpers
    # ------------------------------------------------------------------

    def _build_queue_area(self, parent: ctk.CTkFrame) -> None:
        outer = ctk.CTkFrame(parent, fg_color="transparent")
        outer.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        outer.grid_rowconfigure(1, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        self._hdr_lbl = ctk.CTkLabel(outer, text=t("queue_header"), font=FONT_LABEL, text_color=ON_SURF_M)
        self._hdr_lbl.grid(row=0, column=0, sticky="w", pady=(0, 4))

        self._scroll = ctk.CTkScrollableFrame(
            outer, fg_color=SURFACE, border_width=1, border_color=OUTLINE,
            corner_radius=12, height=48,
        )
        self._scroll.grid(row=1, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

        self._empty_lbl = ctk.CTkLabel(
            self._scroll,
            text=t("empty_queue"),
            font=FONT_BODY, text_color=ON_SURF_M,
        )
        self._empty_lbl.pack(pady=32)

    def _build_controls(
        self,
        parent: ctk.CTkFrame,
        on_start: Callable,
        on_stop: Callable,
        on_reset: Callable,
        on_clear: Callable,
        on_save: Callable,
        on_load: Callable,
        on_start_later: Callable,
    ) -> None:
        self._controls = ctk.CTkFrame(parent, fg_color="transparent")
        self._controls.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        self._controls.grid_columnconfigure(5, weight=1)

        self._start_btn = ctk.CTkButton(
            self._controls, text=t("start_btn"), command=on_start,
            fg_color=PRIMARY, hover_color=PRIMARY_HOV, text_color="white",
            width=80, font=FONT_BOLD, corner_radius=8,
        )
        self._start_btn.grid(row=0, column=0, padx=(0, 4))
        
        self._start_later_btn = ctk.CTkButton(
            self._controls, text=t("start_later_btn"), command=on_start_later,
            fg_color=SURFACE_L, hover_color=PRIMARY_HOV, text_color=ON_SURF,
            width=70, font=FONT_BODY, corner_radius=8, border_width=1, border_color=PRIMARY,
        )
        self._start_later_btn.grid(row=0, column=1, padx=(0, 8))

        self._stop_btn = ctk.CTkButton(
            self._controls, text=t("stop_btn"), command=on_stop,
            fg_color=SURFACE, border_width=1, border_color=OUTLINE,
            hover_color=SURFACE_H, text_color=ON_SURF, width=60,
            font=FONT_BODY, corner_radius=8,
        )
        self._stop_btn.grid(row=0, column=2, padx=(0, 4))

        self._reset_btn = ctk.CTkButton(
            self._controls, text=t("reset_btn"), command=on_reset,
            fg_color=SURFACE, border_width=1, border_color=OUTLINE,
            hover_color=SURFACE_H, text_color=ON_SURF, width=60,
            font=FONT_BODY, corner_radius=8,
        )
        self._reset_btn.grid(row=0, column=3, padx=(0, 4))

        self._clear_btn = ctk.CTkButton(
            self._controls, text=t("clear_btn"), command=on_clear,
            fg_color=SURFACE, border_width=1, border_color=OUTLINE,
            hover_color="#2e1414", text_color=ERROR, width=60,
            font=FONT_BODY, corner_radius=8,
        )
        self._clear_btn.grid(row=0, column=4)

        self._stat = ctk.CTkLabel(
            self._controls, text="", font=FONT_BODY, text_color=ON_SURF_M,
        )
        self._stat.grid(row=0, column=5, sticky="ew")
        
        self._save_btn = ctk.CTkButton(
            self._controls, text=t("save_btn"), command=on_save,
            fg_color=SURFACE, hover_color=SURFACE_H, text_color=ON_SURF,
            width=90, font=FONT_BODY, corner_radius=8, border_width=1, border_color=OUTLINE,
        )
        self._save_btn.grid(row=0, column=6, padx=(8, 4))
        
        self._load_btn = ctk.CTkButton(
            self._controls, text=t("load_btn"), command=on_load,
            fg_color=SURFACE, hover_color=SURFACE_H, text_color=ON_SURF,
            width=70, font=FONT_BODY, corner_radius=8, border_width=1, border_color=OUTLINE,
        )
        self._load_btn.grid(row=0, column=7)

    def _build_row(self, item: Item, index: int) -> _RowRef:
        is_run  = item.status == "running"
        is_done = item.status == "done"
        bc = PRIMARY if is_run else (SUCCESS if is_done else OUTLINE)

        row = ctk.CTkFrame(
            self._scroll, fg_color=SURFACE_L,
            border_width=1, border_color=bc, corner_radius=10,
        )
        row.pack(fill="x", pady=(0, 6), padx=4)
        row.grid_columnconfigure(1, weight=1)

        # Number badge
        nb_bg = PRIMARY if is_run else (SUCCESS if is_done else SURFACE_H)
        nb_fg = "#fff" if (is_run or is_done) else ON_SURF_M
        ctk.CTkLabel(
            row, text=str(index + 1),
            fg_color=nb_bg, text_color=nb_fg,
            font=("Segoe UI", 10, "bold"),
            width=24, height=24, corner_radius=12,
        ).grid(row=0, column=0, rowspan=2, padx=(10, 6), pady=10, sticky="n")

        # Info
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.grid(row=0, column=1, sticky="w", pady=10)
        ctk.CTkLabel(info, text=item.label, font=FONT_BOLD, text_color=ON_SURF).pack(anchor="w")

        meta = f"{fmt(item.total)} - {item.action}"
        if item.action == "sleep":
            cfg = item.sleep_cfg
            meta += f" (Vorbereitung: {cfg.pre_sleep_grace}s, Post-Wake: {cfg.post_wake_delay}s)"
        elif item.action == "type" and item.prompt:
            snippet = item.prompt[:40] + ("..." if len(item.prompt) > 40 else "")
            meta += f' - "{snippet}"'
        ctk.CTkLabel(info, text=meta, font=FONT_SMALL, text_color=ON_SURF_M).pack(anchor="w")

        # Right column: status + countdown
        right = ctk.CTkFrame(row, fg_color="transparent")
        right.grid(row=0, column=2, padx=12, pady=10, sticky="e")

        status_text, cd_text, cd_color = _phase_display(item)
        status_lbl = ctk.CTkLabel(right, text=status_text, text_color=ON_SURF_M, font=FONT_SMALL)
        status_lbl.pack(anchor="e")
        countdown_lbl = ctk.CTkLabel(right, text=cd_text, text_color=cd_color, font=FONT_COUNT)
        countdown_lbl.pack(anchor="e")

        # Delete button (hidden while running)
        if not self._is_running():
            del_btn = ctk.CTkButton(
                row, text="X", width=24, height=24,
                fg_color="transparent", text_color=ON_SURF_M,
                hover_color="#2e1414", corner_radius=6,
            )
            del_btn.configure(command=lambda it=item: self._on_remove(it))
            del_btn.grid(row=0, column=3, padx=10, pady=10)
        else:
            # Reserve space so the row width does not collapse and shift the layout
            placeholder = ctk.CTkFrame(row, width=24, height=24, fg_color="transparent")
            placeholder.grid(row=0, column=3, padx=10, pady=10)

        # Progress bar
        prog_color = SUCCESS if is_done else PRIMARY
        prog = ctk.CTkProgressBar(
            row, height=4, progress_color=prog_color, fg_color=SURFACE_H,
        )
        prog.set(_phase_progress(item))
        prog.grid(row=2, column=0, columnspan=4, sticky="ew", padx=10, pady=(0, 8))

        return (item, row, countdown_lbl, prog, status_lbl)

    # ------------------------------------------------------------------
    # Responsive layout helpers (called by AppWindow)
    # ------------------------------------------------------------------

    def configure_slim(self) -> None:
        """Rearrange controls for narrow (single-column) layout."""
        self._start_btn.grid_configure(row=0, column=0, padx=2, pady=2, sticky="ew")
        self._start_later_btn.grid_configure(row=0, column=1, padx=2, pady=2, sticky="ew")
        self._stop_btn.grid_configure(row=1, column=0, padx=2, pady=2, sticky="ew")
        self._reset_btn.grid_configure(row=1, column=1, padx=2, pady=2, sticky="ew")
        self._clear_btn.grid_configure(row=2, column=0, padx=2, pady=2, sticky="ew")
        self._stat.grid_configure(row=3, column=0, columnspan=2, pady=(4, 0), sticky="w")
        self._save_btn.grid_configure(row=2, column=1, padx=2, pady=2, sticky="ew")
        self._load_btn.grid_configure(row=4, column=1, padx=2, pady=2, sticky="ew") # Actually, better grouping: Save/Load on row 4
        self._save_btn.grid_configure(row=4, column=0, padx=2, pady=2, sticky="ew")
        
        self._controls.grid_columnconfigure((0, 1), weight=1)
        self._controls.grid_columnconfigure((2, 3, 4, 5, 6, 7), weight=0)

    def configure_wide(self) -> None:
        """Rearrange controls for wide (two-column) layout."""
        self._start_btn.grid_configure(row=0, column=0, padx=(0, 4), pady=(0, 6), sticky="ew")
        self._start_later_btn.grid_configure(row=0, column=1, padx=(0, 4), pady=(0, 6), sticky="ew")
        self._stop_btn.grid_configure(row=0, column=2, padx=(0, 4), pady=(0, 6), sticky="ew")
        self._reset_btn.grid_configure(row=0, column=3, padx=(0, 4), pady=(0, 6), sticky="ew")
        self._clear_btn.grid_configure(row=0, column=4, padx=0, pady=(0, 6), sticky="ew")
        
        self._save_btn.grid_configure(row=1, column=0, columnspan=2, padx=(0, 4), pady=0, sticky="ew")
        self._load_btn.grid_configure(row=1, column=2, columnspan=2, padx=(0, 4), pady=0, sticky="ew")
        self._stat.grid_configure(row=1, column=4, columnspan=4, padx=(8, 0), pady=0, sticky="w")
        
        self._controls.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        self._controls.grid_columnconfigure((5, 6, 7), weight=0)

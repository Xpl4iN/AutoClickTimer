"""
app/ui/form_panel.py -- Add-item form + preset card.

Interface:
    FormPanel(parent, on_add)

    on_add(item: Item)  -- called when the user clicks Add or a preset button.
                           May be called twice in quick succession for presets
                           that add a sleep + action pair.

Internal sub-sections (all private):
  _build_form_card   -- mode, time inputs, action selector, prompt area,
                        sleep config inputs, label + add button
  _build_presets_card -- preset combination buttons
"""
from __future__ import annotations

import datetime
from typing import Callable

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

from app.models import Item, SleepConfig, ACTION_LABELS
from app.ui.theme import (
    BG_COLOR, SURFACE, SURFACE_L, SURFACE_H, OUTLINE,
    PRIMARY, PRIMARY_HOV, ON_SURF, ON_SURF_M, ERROR,
    FONT_BOLD, FONT_BODY, FONT_SMALL, FONT_LABEL, FONT_NUM,
    fmt, fmt_short,
)


def _is_admin() -> bool:
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


class FormPanel:
    """
    Left-side form card + presets card.
    Occupies rows 0 and 1 of the left panel grid.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        on_add: Callable[[Item], None],
    ) -> None:
        self._on_add = on_add

        # ---- StringVars ----
        self._mode    = tk.StringVar(value="duration")
        self._sv_h    = tk.StringVar(value="0")
        self._sv_m    = tk.StringVar(value="0")
        self._sv_s    = tk.StringVar(value="0")
        now = datetime.datetime.now()
        self._clk_h   = tk.StringVar(value=str(now.hour))
        self._clk_m   = tk.StringVar(value=str(now.minute))
        self._clk_s   = tk.StringVar(value="0")
        self._sv_lbl  = tk.StringVar()
        self._sv_grace    = tk.StringVar(value="5")
        self._sv_postwake = tk.StringVar(value="30")

        self._build_form_card(parent)
        self._build_presets_card(parent)

    # ------------------------------------------------------------------
    # Form card
    # ------------------------------------------------------------------

    def _build_form_card(self, parent: ctk.CTkFrame) -> None:
        card = ctk.CTkFrame(
            parent, fg_color=SURFACE,
            border_width=1, border_color=OUTLINE, corner_radius=12,
        )
        card.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        card.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # ---- Mode selector ----
        mf = ctk.CTkFrame(card, fg_color="transparent")
        mf.grid(row=0, column=0, columnspan=4, sticky="w", padx=16, pady=(12, 6))

        ctk.CTkLabel(mf, text="Modus:", font=FONT_SMALL, text_color=ON_SURF_M).pack(
            side="left", padx=(0, 12)
        )
        for text, val in [("Timer (Dauer)", "duration"), ("Uhrzeit", "clock")]:
            ctk.CTkRadioButton(
                mf, text=text, variable=self._mode, value=val,
                command=self._on_mode_change,
                fg_color=PRIMARY, hover_color=PRIMARY_HOV,
                text_color=ON_SURF, font=FONT_BODY,
            ).pack(side="left", padx=(0, 16))

        # ---- Dynamic time inputs ----
        self._inputs_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._inputs_frame.grid(row=1, column=0, columnspan=4, sticky="ew", padx=16, pady=6)
        self._inputs_frame.grid_columnconfigure((0, 1, 2), weight=1)
        self._render_inputs()

        # ---- Action selector ----
        af = ctk.CTkFrame(card, fg_color="transparent")
        af.grid(row=2, column=0, columnspan=4, sticky="ew", padx=16, pady=6)

        ctk.CTkLabel(af, text="Aktion", font=FONT_SMALL, text_color=ON_SURF_M).pack(
            anchor="w", pady=(0, 4)
        )
        self._act_seg = ctk.CTkSegmentedButton(
            af,
            values=["Enter", "Linksklick", "Prompt senden", "Sleep & Wake"],
            command=self._on_action_change,
            fg_color=SURFACE_L, selected_color=PRIMARY,
            selected_hover_color=PRIMARY_HOV,
            text_color=ON_SURF, unselected_color=SURFACE_L,
            unselected_hover_color=SURFACE_H, font=FONT_BODY,
        )
        self._act_seg.pack(fill="x")
        self._act_seg.set("Enter")

        # ---- Prompt text area (hidden unless "Prompt senden") ----
        self._prompt_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._prompt_frame.grid(row=3, column=0, columnspan=4, sticky="ew", padx=16, pady=6)
        self._prompt_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self._prompt_frame,
            text="Prompt-Text (eingefuegt + Enter gesendet)",
            font=FONT_SMALL, text_color=ON_SURF_M,
        ).grid(row=0, column=0, sticky="w", pady=(0, 2))
        self._prompt_box = ctk.CTkTextbox(
            self._prompt_frame, height=60,
            fg_color=SURFACE_L, border_color=OUTLINE, border_width=1,
            text_color=ON_SURF,
        )
        self._prompt_box.grid(row=1, column=0, sticky="ew")
        self._prompt_frame.grid_remove()

        # ---- Sleep config inputs (hidden unless "Sleep & Wake") ----
        self._sleep_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._sleep_frame.grid(row=4, column=0, columnspan=4, sticky="ew", padx=16, pady=6)
        self._sleep_frame.grid_columnconfigure((1, 3), weight=1)

        ctk.CTkLabel(
            self._sleep_frame, text="Sleep-Konfiguration",
            font=FONT_LABEL, text_color=ON_SURF_M,
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))

        ctk.CTkLabel(
            self._sleep_frame, text="Wartezeit vor Schlaf (Sek.):",
            font=FONT_SMALL, text_color=ON_SURF_M,
        ).grid(row=1, column=0, sticky="w", padx=(0, 8))
        ctk.CTkEntry(
            self._sleep_frame, textvariable=self._sv_grace,
            fg_color=SURFACE_L, border_color=OUTLINE, text_color=ON_SURF,
            justify="center", font=FONT_NUM, width=70,
        ).grid(row=1, column=1, sticky="w", padx=(0, 16))

        ctk.CTkLabel(
            self._sleep_frame, text="Post-Wake-Verzoegerung (Sek.):",
            font=FONT_SMALL, text_color=ON_SURF_M,
        ).grid(row=1, column=2, sticky="w", padx=(0, 8))
        ctk.CTkEntry(
            self._sleep_frame, textvariable=self._sv_postwake,
            fg_color=SURFACE_L, border_color=OUTLINE, text_color=ON_SURF,
            justify="center", font=FONT_NUM, width=70,
        ).grid(row=1, column=3, sticky="w")
        self._sleep_frame.grid_remove()

        # ---- Label + Add button ----
        lf = ctk.CTkFrame(card, fg_color="transparent")
        lf.grid(row=5, column=0, columnspan=4, sticky="ew", padx=16, pady=(6, 12))
        lf.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(lf, text="Bezeichnung:", font=FONT_SMALL, text_color=ON_SURF_M).grid(
            row=0, column=0, sticky="w", padx=(0, 10)
        )
        ctk.CTkEntry(
            lf, textvariable=self._sv_lbl,
            fg_color=SURFACE_L, border_color=OUTLINE, text_color=ON_SURF, width=120,
        ).grid(row=0, column=1, sticky="ew", padx=(0, 12))

        ctk.CTkButton(
            lf, text="+ Zur Warteschlange", command=self._on_add_clicked,
            fg_color=PRIMARY, hover_color=PRIMARY_HOV, text_color="white",
            width=148, font=FONT_BOLD, corner_radius=8,
        ).grid(row=0, column=2, sticky="e")

    # ------------------------------------------------------------------
    # Presets card
    # ------------------------------------------------------------------

    def _build_presets_card(self, parent: ctk.CTkFrame) -> None:
        card = ctk.CTkFrame(
            parent, fg_color=SURFACE,
            border_width=1, border_color=OUTLINE, corner_radius=12,
        )
        card.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        card.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            card, text="PRESETS (Zeit oben eintragen)",
            font=FONT_LABEL, text_color=ON_SURF_M,
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(10, 4))

        ctk.CTkButton(
            card, text="Sleep & Wake + Enter",
            command=lambda: self._add_preset_combination("enter"),
            fg_color=SURFACE_L, hover_color=PRIMARY_HOV,
            border_width=1, border_color=OUTLINE,
            text_color=ON_SURF, font=FONT_BODY,
        ).grid(row=1, column=0, padx=(16, 6), pady=(0, 12), sticky="ew")

        ctk.CTkButton(
            card, text="Sleep & Wake + Klick",
            command=lambda: self._add_preset_combination("click"),
            fg_color=SURFACE_L, hover_color=PRIMARY_HOV,
            border_width=1, border_color=OUTLINE,
            text_color=ON_SURF, font=FONT_BODY,
        ).grid(row=1, column=1, padx=(6, 16), pady=(0, 12), sticky="ew")

    # ------------------------------------------------------------------
    # Time input rendering
    # ------------------------------------------------------------------

    def _render_inputs(self) -> None:
        for w in self._inputs_frame.winfo_children():
            w.destroy()

        if self._mode.get() == "duration":
            fields = [("Stunden", self._sv_h), ("Minuten", self._sv_m), ("Sekunden", self._sv_s)]
            for col, (lbl, var) in enumerate(fields):
                f = ctk.CTkFrame(self._inputs_frame, fg_color="transparent")
                f.grid(row=0, column=col, sticky="ew", padx=(0, 8))
                ctk.CTkLabel(f, text=lbl, font=FONT_SMALL, text_color=ON_SURF_M).pack(
                    anchor="w", pady=(0, 2)
                )
                ctk.CTkEntry(
                    f, textvariable=var,
                    fg_color=SURFACE_L, border_color=OUTLINE,
                    text_color=ON_SURF, justify="center",
                    font=FONT_NUM, width=60,
                ).pack(fill="x")
            pr_row = 1
        else:
            fields = [("Stunde", self._clk_h), ("Minute", self._clk_m), ("Sekunde", self._clk_s)]
            for col, (lbl, var) in enumerate(fields):
                f = ctk.CTkFrame(self._inputs_frame, fg_color="transparent")
                f.grid(row=0, column=col, sticky="ew", padx=(0, 8))
                ctk.CTkLabel(f, text=lbl, font=FONT_SMALL, text_color=ON_SURF_M).pack(
                    anchor="w", pady=(0, 2)
                )
                ctk.CTkEntry(
                    f, textvariable=var,
                    fg_color=SURFACE_L, border_color=OUTLINE,
                    text_color=ON_SURF, justify="center",
                    font=FONT_NUM, width=60,
                ).pack(fill="x")
                var.trace_add("write", self._update_clock_preview)
            self._clk_preview = ctk.CTkLabel(
                self._inputs_frame, text="",
                font=FONT_SMALL, text_color=PRIMARY,
            )
            self._clk_preview.grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))
            self._update_clock_preview()
            pr_row = 2

        # ---- Quick time presets row ----
        pf = ctk.CTkFrame(self._inputs_frame, fg_color="transparent")
        pf.grid(row=pr_row, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        pf.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=1)

        presets = [
            (15, "m", "15m"), (30, "m", "30m"),
            (1,  "h", "1h"),  (2,  "h", "2h"),
            (3,  "h", "3h"),  (4,  "h", "4h"),
            (5,  "h", "5h"),  (6,  "h", "6h"),
            (8,  "h", "8h"),  (10, "h", "10h"),
            (12, "h", "12h"), (24, "h", "24h"),
        ]
        for idx, (amount, unit, lbl) in enumerate(presets):
            r, c = divmod(idx, 6)
            ctk.CTkButton(
                pf, text=lbl,
                command=lambda a=amount, u=unit: self._set_time_preset(a, u),
                fg_color=SURFACE_L, hover_color=PRIMARY_HOV,
                border_width=1, border_color=OUTLINE,
                text_color=ON_SURF, height=24, font=FONT_SMALL,
            ).grid(row=r, column=c, padx=2, pady=2, sticky="ew")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_mode_change(self) -> None:
        self._render_inputs()

    def _on_action_change(self, choice: str) -> None:
        if choice == "Prompt senden":
            self._prompt_frame.grid()
        else:
            self._prompt_frame.grid_remove()

        if choice == "Sleep & Wake":
            self._sleep_frame.grid()
        else:
            self._sleep_frame.grid_remove()

    def _update_clock_preview(self, *_) -> None:
        if self._mode.get() != "clock":
            return
        try:
            h = int(self._clk_h.get() or 0)
            m = int(self._clk_m.get() or 0)
            s = int(self._clk_s.get() or 0)
            now = datetime.datetime.now()
            target = now.replace(hour=h, minute=m, second=s, microsecond=0)
            if target <= now:
                target += datetime.timedelta(days=1)
            delta = int((target - now).total_seconds())
            self._clk_preview.configure(
                text=f"-> in {fmt_short(delta)} (um {target.strftime('%H:%M:%S')})"
            )
        except Exception:
            if hasattr(self, "_clk_preview"):
                self._clk_preview.configure(text="")

    def _set_time_preset(self, amount: int, unit: str) -> None:
        if self._mode.get() == "duration":
            self._sv_h.set("0")
            self._sv_m.set("0")
            self._sv_s.set("0")
            if unit == "h":
                self._sv_h.set(str(amount))
            else:
                self._sv_m.set(str(amount))
        else:
            now = datetime.datetime.now()
            delta = datetime.timedelta(hours=amount) if unit == "h" else datetime.timedelta(minutes=amount)
            target = now + delta
            self._clk_h.set(str(target.hour))
            self._clk_m.set(str(target.minute))
            self._clk_s.set(str(target.second))
            self._update_clock_preview()

    def _on_add_clicked(self) -> None:
        item = self._build_item()
        if item is None:
            return
        self._sv_lbl.set("")
        self._prompt_box.delete("1.0", tk.END)
        self._on_add(item)

    def _add_preset_combination(self, post_action: str) -> None:
        total = self._get_total_seconds()
        if total is None:
            return

        if not _is_admin():
            messagebox.showerror(
                "Administrator",
                "Sleep & Wake benoetigt Administratorrechte. "
                "Bitte als Administrator neu starten.",
            )
            return

        sleep_cfg = self._get_sleep_config()
        sleep_item = Item(total, "sleep", sleep_cfg=sleep_cfg, label="Ruhezustand")

        post_label = (
            "Enter nach Aufwachen" if post_action == "enter" else "Linksklick nach Aufwachen"
        )
        post_item = Item(2, post_action, label=post_label)  # type: ignore[arg-type]

        self._on_add(sleep_item)
        self._on_add(post_item)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_total_seconds(self) -> int | None:
        """Parse time inputs; show error dialog and return None on failure."""
        try:
            if self._mode.get() == "duration":
                h = int(self._sv_h.get() or 0)
                m = int(self._sv_m.get() or 0)
                s = int(self._sv_s.get() or 0)
                total = h * 3600 + m * 60 + s
                if total <= 0:
                    messagebox.showerror("Fehler", "Zeit > 0 erforderlich.")
                    return None
                return total
            else:
                h = int(self._clk_h.get() or 0)
                m = int(self._clk_m.get() or 0)
                s = int(self._clk_s.get() or 0)
                now = datetime.datetime.now()
                target = now.replace(hour=h, minute=m, second=s, microsecond=0)
                if target <= now:
                    target += datetime.timedelta(days=1)
                total = int((target - now).total_seconds())
                if total <= 0:
                    messagebox.showerror("Fehler", "Zielzeit liegt in der Vergangenheit.")
                    return None
                return total
        except ValueError:
            messagebox.showerror("Fehler", "Ungueltige Zeit-Eingabe.")
            return None

    def _get_sleep_config(self) -> SleepConfig:
        try:
            grace = max(0, int(self._sv_grace.get() or "5"))
        except ValueError:
            grace = 5
        try:
            post = max(0, int(self._sv_postwake.get() or "30"))
        except ValueError:
            post = 30
        return SleepConfig(pre_sleep_grace=grace, post_wake_delay=post)

    def _build_item(self) -> Item | None:
        total = self._get_total_seconds()
        if total is None:
            return None

        action_map = {
            "Enter": "enter",
            "Linksklick": "click",
            "Prompt senden": "type",
            "Sleep & Wake": "sleep",
        }
        action = action_map.get(self._act_seg.get(), "enter")

        if action == "sleep" and not _is_admin():
            messagebox.showerror(
                "Administrator",
                "Sleep & Wake benoetigt Administratorrechte.",
            )
            return None

        prompt = ""
        if action == "type":
            prompt = self._prompt_box.get("1.0", "end-1c").strip()
            if not prompt:
                messagebox.showerror("Fehler", "Prompt-Text fehlt.")
                return None

        sleep_cfg = self._get_sleep_config() if action == "sleep" else SleepConfig()
        return Item(
            total=total,
            action=action,  # type: ignore[arg-type]
            prompt=prompt,
            label=self._sv_lbl.get().strip(),
            sleep_cfg=sleep_cfg,
        )

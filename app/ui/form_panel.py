"""
app/ui/form_panel.py -- Add-item form + preset gallery with segmented navigation.

Interface:
    FormPanel(parent, on_add)

    on_add(item: Item)  -- called when the user clicks Add or a preset button.
                           May be called twice in quick succession for presets
                           that add a sleep + action pair.

Internal sub-sections (all private):
  _build_form_card     -- mode, time inputs, action selector, prompt area,
                          sleep config inputs, target window, label + add button
  _build_presets_card  -- preset combination cards
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


def _get_open_windows() -> list[str]:
    import ctypes
    EnumWindows = ctypes.windll.user32.EnumWindows
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
    GetWindowText = ctypes.windll.user32.GetWindowTextW
    GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW
    IsWindowVisible = ctypes.windll.user32.IsWindowVisible

    titles = ["(Global / Aktives Fenster)"]

    def foreach_window(hwnd, lParam):
        if IsWindowVisible(hwnd):
            length = GetWindowTextLength(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                GetWindowText(hwnd, buff, length + 1)
                title = buff.value
                if title and title not in titles:
                    titles.append(title)
        return True

    EnumWindows(EnumWindowsProc(foreach_window), 0)
    return titles


class FormPanel:
    """
    Left-side form panel with segmented navigation (Aktion erstellen / Vorlagen).
    Occupies row 0 of the left panel grid.
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

        # Action StringVar
        self._action_val = tk.StringVar(value="Enter")

        # Sleep config StringVars
        self._sleep_mode  = tk.StringVar(value="duration")
        self._sv_grace_h  = tk.StringVar(value="0")
        self._sv_grace_m  = tk.StringVar(value="0")
        self._sv_grace_s  = tk.StringVar(value="5")
        self._clk_grace_h = tk.StringVar(value=str(now.hour))
        self._clk_grace_m = tk.StringVar(value=str(now.minute))
        self._clk_grace_s = tk.StringVar(value=str(now.second))
        self._sv_postwake = tk.StringVar(value="30")

        self._target_window = tk.StringVar(value="(Global / Aktives Fenster)")
        self._require_foreground = tk.BooleanVar(value=False)

        # Preset tab StringVars
        self._preset_mode = tk.StringVar(value="duration")
        self._psv_h = tk.StringVar(value="0")
        self._psv_m = tk.StringVar(value="30")
        self._psv_s = tk.StringVar(value="0")
        self._pclk_h = tk.StringVar(value=str((now.hour + 1) % 24))
        self._pclk_m = tk.StringVar(value=str(now.minute))
        self._pclk_s = tk.StringVar(value="0")

        # Container
        self._container = ctk.CTkFrame(parent, fg_color="transparent")
        self._container.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        self._container.grid_columnconfigure(0, weight=1)
        self._container.grid_rowconfigure(1, weight=1)

        # ---- Tab Switcher ----
        self._tab_switch = ctk.CTkSegmentedButton(
            self._container,
            values=["Aktion erstellen", "Vorlagen"],
            command=self._on_tab_change,
            fg_color=SURFACE,
            selected_color=PRIMARY,
            selected_hover_color=PRIMARY_HOV,
            unselected_color=SURFACE_L,
            unselected_hover_color=SURFACE_H,
            text_color=ON_SURF,
            font=FONT_BOLD,
            height=32,
            corner_radius=8,
        )
        self._tab_switch.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self._tab_switch.set("Aktion erstellen")

        # ---- Tab Pages ----
        self._action_tab = ctk.CTkFrame(self._container, fg_color="transparent")
        self._action_tab.grid(row=1, column=0, sticky="nsew")
        self._action_tab.grid_columnconfigure(0, weight=1)

        self._presets_tab = ctk.CTkFrame(self._container, fg_color="transparent")
        self._presets_tab.grid(row=1, column=0, sticky="nsew")
        self._presets_tab.grid_columnconfigure(0, weight=1)
        self._presets_tab.grid_remove()

        self._build_form_card(self._action_tab)
        self._build_presets_card(self._presets_tab)

    def _on_tab_change(self, selected_tab: str) -> None:
        if selected_tab == "Aktion erstellen":
            self._presets_tab.grid_remove()
            self._action_tab.grid()
        else:
            self._action_tab.grid_remove()
            self._presets_tab.grid()

    # ------------------------------------------------------------------
    # Form card
    # ------------------------------------------------------------------

    def _build_form_card(self, parent: ctk.CTkFrame) -> None:
        card = ctk.CTkFrame(
            parent, fg_color=SURFACE,
            border_width=1, border_color=OUTLINE, corner_radius=12,
        )
        card.grid(row=0, column=0, sticky="nsew")
        card.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # ---- Mode selector ----
        mf = ctk.CTkFrame(card, fg_color="transparent")
        mf.grid(row=0, column=0, columnspan=4, sticky="w", padx=16, pady=(12, 4))

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
        self._inputs_frame.grid(row=1, column=0, columnspan=4, sticky="ew", padx=16, pady=4)
        self._inputs_frame.grid_columnconfigure((0, 1, 2), weight=1)
        self._render_inputs()

        # ---- Action selector (Visual Segmented Button) ----
        af = ctk.CTkFrame(card, fg_color="transparent")
        af.grid(row=2, column=0, columnspan=4, sticky="ew", padx=16, pady=(8, 4))
        af.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(af, text="Aktionstyp:", font=FONT_SMALL, text_color=ON_SURF_M).grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )

        self._act_segmented = ctk.CTkSegmentedButton(
            af,
            values=["Enter", "Linksklick", "Prompt senden", "Sleep & Wake", "Herunterfahren"],
            variable=self._action_val,
            command=self._on_action_change,
            fg_color=SURFACE_L,
            selected_color=PRIMARY,
            selected_hover_color=PRIMARY_HOV,
            unselected_color=SURFACE_L,
            unselected_hover_color=SURFACE_H,
            text_color=ON_SURF,
            font=FONT_SMALL,
            corner_radius=8,
            height=30,
        )
        self._act_segmented.grid(row=1, column=0, sticky="ew")
        self._act_segmented.set("Enter")

        # ---- Prompt text area (hidden unless "Prompt senden") ----
        self._prompt_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._prompt_frame.grid(row=3, column=0, columnspan=4, sticky="ew", padx=16, pady=4)
        self._prompt_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self._prompt_frame,
            text="Prompt-Text (eingefuegt + Enter gesendet):",
            font=FONT_SMALL, text_color=ON_SURF_M,
        ).grid(row=0, column=0, sticky="w", pady=(0, 2))
        self._prompt_box = ctk.CTkTextbox(
            self._prompt_frame, height=54,
            fg_color=SURFACE_L, border_color=OUTLINE, border_width=1,
            text_color=ON_SURF, font=FONT_BODY, corner_radius=8,
        )
        self._prompt_box.grid(row=1, column=0, sticky="ew")
        self._prompt_frame.grid_remove()

        # ---- Sleep config inputs (hidden unless "Sleep & Wake") ----
        self._sleep_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._sleep_frame.grid(row=4, column=0, columnspan=4, sticky="ew", padx=16, pady=4)
        self._sleep_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkLabel(
            self._sleep_frame, text="Sleep-Konfiguration",
            font=FONT_LABEL, text_color=ON_SURF_M,
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 4))

        # Pre-sleep mode selector
        sm_frame = ctk.CTkFrame(self._sleep_frame, fg_color="transparent")
        sm_frame.grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 4))

        ctk.CTkLabel(sm_frame, text="Wartezeit vor Schlaf:", font=FONT_SMALL, text_color=ON_SURF_M).pack(
            side="left", padx=(0, 12)
        )
        for text, val in [("Timer (Dauer)", "duration"), ("Uhrzeit", "clock")]:
            ctk.CTkRadioButton(
                sm_frame, text=text, variable=self._sleep_mode, value=val,
                command=self._on_sleep_mode_change,
                fg_color=PRIMARY, hover_color=PRIMARY_HOV,
                text_color=ON_SURF, font=FONT_BODY,
            ).pack(side="left", padx=(0, 16))

        # Dynamic inputs for pre-sleep
        self._sleep_inputs_frame = ctk.CTkFrame(self._sleep_frame, fg_color="transparent")
        self._sleep_inputs_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(2, 4))
        self._sleep_inputs_frame.grid_columnconfigure((0, 1, 2), weight=1)
        self._render_sleep_inputs()

        # Post-wake delay section
        pw_section = ctk.CTkFrame(self._sleep_frame, fg_color="transparent")
        pw_section.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(4, 0))
        pw_section.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            pw_section, text="Post-Wake-Verzoegerung (Sek.):",
            font=FONT_SMALL, text_color=ON_SURF_M,
        ).grid(row=0, column=0, sticky="w", pady=(0, 2))

        pw_row = ctk.CTkFrame(pw_section, fg_color="transparent")
        pw_row.grid(row=1, column=0, sticky="w")

        ctk.CTkEntry(
            pw_row, textvariable=self._sv_postwake,
            fg_color=SURFACE_L, border_color=OUTLINE, text_color=ON_SURF,
            justify="center", font=FONT_NUM, width=55,
        ).pack(side="left", padx=(0, 8))

        for pw_val in [5, 10, 15, 30, 60]:
            ctk.CTkButton(
                pw_row, text=f"{pw_val}s",
                command=lambda v=pw_val: self._sv_postwake.set(str(v)),
                fg_color=SURFACE_L, hover_color=PRIMARY_HOV,
                border_width=1, border_color=OUTLINE,
                text_color=ON_SURF, height=24, width=38, font=FONT_SMALL,
            ).pack(side="left", padx=2)

        self._sleep_frame.grid_remove()

        # ---- Target Window selector ----
        self._target_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._target_frame.grid(row=5, column=0, columnspan=4, sticky="ew", padx=16, pady=4)
        self._target_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self._target_frame, text="Ziel-Fenster (Background-Input):",
            font=FONT_SMALL, text_color=ON_SURF_M,
        ).grid(row=0, column=0, sticky="w", pady=(0, 2))

        tw_inner = ctk.CTkFrame(self._target_frame, fg_color="transparent")
        tw_inner.grid(row=1, column=0, sticky="ew")
        tw_inner.grid_columnconfigure(0, weight=1)

        self._window_combo = ctk.CTkComboBox(
            tw_inner, variable=self._target_window, values=_get_open_windows(),
            fg_color=SURFACE_L, border_color=OUTLINE, text_color=ON_SURF, font=FONT_BODY,
            width=240,
        )
        self._window_combo.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            tw_inner, text="Aktualisieren", width=85,
            command=lambda: self._window_combo.configure(values=_get_open_windows()),
            fg_color=SURFACE_L, hover_color=PRIMARY_HOV, border_width=1, border_color=OUTLINE,
            text_color=ON_SURF, font=FONT_SMALL,
        ).grid(row=0, column=1)

        ctk.CTkCheckBox(
            self._target_frame, text="Zwingend in den Vordergrund holen",
            variable=self._require_foreground,
            font=FONT_SMALL, text_color=ON_SURF, fg_color=PRIMARY, hover_color=PRIMARY_HOV,
        ).grid(row=2, column=0, sticky="w", pady=(4, 0))

        # ---- Label selector (hidden for Sleep & Wake and Herunterfahren) ----
        self._label_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._label_frame.grid(row=6, column=0, columnspan=4, sticky="ew", padx=16, pady=(4, 2))
        self._label_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self._label_frame, text="Bezeichnung:", font=FONT_SMALL, text_color=ON_SURF_M).grid(
            row=0, column=0, sticky="w", padx=(0, 10)
        )
        ctk.CTkEntry(
            self._label_frame, textvariable=self._sv_lbl,
            fg_color=SURFACE_L, border_color=OUTLINE, text_color=ON_SURF,
        ).grid(row=0, column=1, sticky="ew")

        # ---- Add button ----
        add_frame = ctk.CTkFrame(card, fg_color="transparent")
        add_frame.grid(row=7, column=0, columnspan=4, sticky="ew", padx=16, pady=(6, 12))
        add_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            add_frame, text="+ Zur Warteschlange", command=self._on_add_clicked,
            fg_color=PRIMARY, hover_color=PRIMARY_HOV, text_color="white",
            font=FONT_BOLD, corner_radius=8, height=34,
        ).grid(row=0, column=0, sticky="ew")

    # ------------------------------------------------------------------
    # Presets card
    # ------------------------------------------------------------------

    def _build_presets_card(self, parent: ctk.CTkFrame) -> None:
        card = ctk.CTkFrame(
            parent, fg_color=SURFACE,
            border_width=1, border_color=OUTLINE, corner_radius=12,
        )
        card.grid(row=0, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card, text="SCHNELL-VORLAGEN",
            font=FONT_LABEL, text_color=ON_SURF_M,
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))

        # Preset 1: Sleep & Wake + Enter
        p1 = ctk.CTkFrame(card, fg_color=SURFACE_L, border_width=1, border_color=OUTLINE, corner_radius=10)
        p1.grid(row=1, column=0, sticky="ew", padx=16, pady=6)
        p1.grid_columnconfigure(0, weight=1)

        p1_info = ctk.CTkFrame(p1, fg_color="transparent")
        p1_info.grid(row=0, column=0, sticky="w", padx=12, pady=10)
        ctk.CTkLabel(p1_info, text="Sleep & Wake + Enter", font=FONT_BOLD, text_color=ON_SURF).pack(anchor="w")
        ctk.CTkLabel(
            p1_info,
            text="Rechner in Ruhezustand versetzen und zur Zielzeit mit Enter wecken.",
            font=FONT_SMALL, text_color=ON_SURF_M, wraplength=220, justify="left",
        ).pack(anchor="w", pady=(2, 0))

        ctk.CTkButton(
            p1, text="+ Hinzufuegen", width=95, height=30,
            command=lambda: self._add_preset_combination("enter"),
            fg_color=PRIMARY, hover_color=PRIMARY_HOV, text_color="white",
            font=FONT_BOLD, corner_radius=6,
        ).grid(row=0, column=1, padx=12, pady=10, sticky="e")

        # Preset 2: Sleep & Wake + Klick
        p2 = ctk.CTkFrame(card, fg_color=SURFACE_L, border_width=1, border_color=OUTLINE, corner_radius=10)
        p2.grid(row=2, column=0, sticky="ew", padx=16, pady=6)
        p2.grid_columnconfigure(0, weight=1)

        p2_info = ctk.CTkFrame(p2, fg_color="transparent")
        p2_info.grid(row=0, column=0, sticky="w", padx=12, pady=10)
        ctk.CTkLabel(p2_info, text="Sleep & Wake + Linksklick", font=FONT_BOLD, text_color=ON_SURF).pack(anchor="w")
        ctk.CTkLabel(
            p2_info,
            text="Rechner in Ruhezustand versetzen und zur Zielzeit mit Klick wecken.",
            font=FONT_SMALL, text_color=ON_SURF_M, wraplength=220, justify="left",
        ).pack(anchor="w", pady=(2, 0))

        ctk.CTkButton(
            p2, text="+ Hinzufuegen", width=95, height=30,
            command=lambda: self._add_preset_combination("click"),
            fg_color=PRIMARY, hover_color=PRIMARY_HOV, text_color="white",
            font=FONT_BOLD, corner_radius=6,
        ).grid(row=0, column=1, padx=12, pady=10, sticky="e")

        # Preset 3: Timer + Herunterfahren
        p3 = ctk.CTkFrame(card, fg_color=SURFACE_L, border_width=1, border_color=OUTLINE, corner_radius=10)
        p3.grid(row=3, column=0, sticky="ew", padx=16, pady=(6, 14))
        p3.grid_columnconfigure(0, weight=1)

        p3_info = ctk.CTkFrame(p3, fg_color="transparent")
        p3_info.grid(row=0, column=0, sticky="w", padx=12, pady=10)
        ctk.CTkLabel(p3_info, text="Timer + Herunterfahren", font=FONT_BOLD, text_color=ON_SURF).pack(anchor="w")
        ctk.CTkLabel(
            p3_info,
            text="Rechner nach Ablauf der eingestellten Zeit vollstaendig herunterfahren.",
            font=FONT_SMALL, text_color=ON_SURF_M, wraplength=220, justify="left",
        ).pack(anchor="w", pady=(2, 0))

        ctk.CTkButton(
            p3, text="+ Hinzufuegen", width=95, height=30,
            command=lambda: self._add_preset_combination("shutdown"),
            fg_color=PRIMARY, hover_color=PRIMARY_HOV, text_color="white",
            font=FONT_BOLD, corner_radius=6,
        ).grid(row=0, column=1, padx=12, pady=10, sticky="e")

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
        pf.grid(row=pr_row, column=0, columnspan=4, sticky="ew", pady=(6, 0))
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
                width=45,
            ).grid(row=r, column=c, padx=2, pady=2, sticky="ew")

    def _render_sleep_inputs(self) -> None:
        for w in self._sleep_inputs_frame.winfo_children():
            w.destroy()

        if self._sleep_mode.get() == "duration":
            fields = [("Stunden", self._sv_grace_h), ("Minuten", self._sv_grace_m), ("Sekunden", self._sv_grace_s)]
            for col, (lbl, var) in enumerate(fields):
                f = ctk.CTkFrame(self._sleep_inputs_frame, fg_color="transparent")
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
            fields = [("Stunde", self._clk_grace_h), ("Minute", self._clk_grace_m), ("Sekunde", self._clk_grace_s)]
            for col, (lbl, var) in enumerate(fields):
                f = ctk.CTkFrame(self._sleep_inputs_frame, fg_color="transparent")
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
                var.trace_add("write", self._update_sleep_clock_preview)
            self._clk_grace_preview = ctk.CTkLabel(
                self._sleep_inputs_frame, text="",
                font=FONT_SMALL, text_color=PRIMARY,
            )
            self._clk_grace_preview.grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))
            self._update_sleep_clock_preview()
            pr_row = 2

        # ---- Quick time presets row for pre-sleep ----
        pf = ctk.CTkFrame(self._sleep_inputs_frame, fg_color="transparent")
        pf.grid(row=pr_row, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        pf.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        presets = [
            (5,  "s", "5s"),  (10, "s", "10s"), (30, "s", "30s"), (1, "m", "1m"),   (2, "m", "2m"),
            (3,  "m", "3m"),  (5,  "m", "5m"),  (10, "m", "10m"), (15, "m", "15m"), (30, "m", "30m"),
        ]
        for idx, (amount, unit, lbl) in enumerate(presets):
            r, c = divmod(idx, 5)
            ctk.CTkButton(
                pf, text=lbl,
                command=lambda a=amount, u=unit: self._set_sleep_time_preset(a, u),
                fg_color=SURFACE_L, hover_color=PRIMARY_HOV,
                border_width=1, border_color=OUTLINE,
                text_color=ON_SURF, height=24, font=FONT_SMALL,
                width=42,
            ).grid(row=r, column=c, padx=2, pady=2, sticky="ew")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_mode_change(self) -> None:
        self._render_inputs()

    def _on_sleep_mode_change(self) -> None:
        self._render_sleep_inputs()

    def _on_action_change(self, choice: str) -> None:
        if choice == "Prompt senden":
            self._prompt_frame.grid()
        else:
            self._prompt_frame.grid_remove()

        if choice == "Sleep & Wake":
            self._sleep_frame.grid()
        else:
            self._sleep_frame.grid_remove()

        if choice in ("Sleep & Wake", "Herunterfahren"):
            self._target_frame.grid_remove()
            self._label_frame.grid_remove()
        else:
            self._target_frame.grid()
            self._label_frame.grid()

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
            if hasattr(self, "_clk_preview"):
                self._clk_preview.configure(
                    text=f"-> in {fmt_short(delta)} (um {target.strftime('%H:%M:%S')})"
                )
        except Exception:
            if hasattr(self, "_clk_preview"):
                self._clk_preview.configure(text="")

    def _update_sleep_clock_preview(self, *_) -> None:
        if self._sleep_mode.get() != "clock":
            return
        try:
            h = int(self._clk_grace_h.get() or 0)
            m = int(self._clk_grace_m.get() or 0)
            s = int(self._clk_grace_s.get() or 0)
            now = datetime.datetime.now()
            target = now.replace(hour=h, minute=m, second=s, microsecond=0)
            if target <= now:
                target += datetime.timedelta(days=1)
            delta = int((target - now).total_seconds())
            if hasattr(self, "_clk_grace_preview"):
                self._clk_grace_preview.configure(
                    text=f"-> in {fmt_short(delta)} (um {target.strftime('%H:%M:%S')})"
                )
        except Exception:
            if hasattr(self, "_clk_grace_preview"):
                self._clk_grace_preview.configure(text="")

    def _set_time_preset(self, amount: int, unit: str) -> None:
        if self._mode.get() == "duration":
            self._sv_h.set("0")
            self._sv_m.set("0")
            self._sv_s.set("0")
            if unit == "h":
                self._sv_h.set(str(amount))
            elif unit == "m":
                self._sv_m.set(str(amount))
            else:
                self._sv_s.set(str(amount))
        else:
            now = datetime.datetime.now()
            if unit == "h":
                delta = datetime.timedelta(hours=amount)
            elif unit == "m":
                delta = datetime.timedelta(minutes=amount)
            else:
                delta = datetime.timedelta(seconds=amount)
            target = now + delta
            self._clk_h.set(str(target.hour))
            self._clk_m.set(str(target.minute))
            self._clk_s.set(str(target.second))
            self._update_clock_preview()

    def _set_sleep_time_preset(self, amount: int, unit: str) -> None:
        if self._sleep_mode.get() == "duration":
            self._sv_grace_h.set("0")
            self._sv_grace_m.set("0")
            self._sv_grace_s.set("0")
            if unit == "h":
                self._sv_grace_h.set(str(amount))
            elif unit == "m":
                self._sv_grace_m.set(str(amount))
            else:
                self._sv_grace_s.set(str(amount))
        else:
            now = datetime.datetime.now()
            if unit == "h":
                delta = datetime.timedelta(hours=amount)
            elif unit == "m":
                delta = datetime.timedelta(minutes=amount)
            else:
                delta = datetime.timedelta(seconds=amount)
            target = now + delta
            self._clk_grace_h.set(str(target.hour))
            self._clk_grace_m.set(str(target.minute))
            self._clk_grace_s.set(str(target.second))
            self._update_sleep_clock_preview()

    def _on_add_clicked(self) -> None:
        item = self._build_item()
        if item is None:
            return
        self._sv_lbl.set("")
        self._prompt_box.delete("1.0", tk.END)
        self._on_add(item)

    def _add_preset_combination(self, preset_type: str) -> None:
        total = self._get_total_seconds()
        if total is None:
            return

        if preset_type == "shutdown":
            shutdown_item = Item(total, "shutdown", label="Herunterfahren")
            self._on_add(shutdown_item)
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
            "Enter nach Aufwachen" if preset_type == "enter" else "Linksklick nach Aufwachen"
        )
        post_item = Item(2, preset_type, label=post_label)  # type: ignore[arg-type]

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
            if self._sleep_mode.get() == "duration":
                h = int(self._sv_grace_h.get() or 0)
                m = int(self._sv_grace_m.get() or 0)
                s = int(self._sv_grace_s.get() or 0)
                grace = max(0, h * 3600 + m * 60 + s)
            else:
                h = int(self._clk_grace_h.get() or 0)
                m = int(self._clk_grace_m.get() or 0)
                s = int(self._clk_grace_s.get() or 0)
                now = datetime.datetime.now()
                target = now.replace(hour=h, minute=m, second=s, microsecond=0)
                if target <= now:
                    target += datetime.timedelta(days=1)
                grace = max(0, int((target - now).total_seconds()))
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
            "Herunterfahren": "shutdown",
        }
        action = action_map.get(self._action_val.get(), "enter")

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

        tw = self._target_window.get()
        if tw == "(Global / Aktives Fenster)":
            tw = ""

        lbl = self._sv_lbl.get().strip()
        if not lbl:
            if action == "sleep":
                lbl = "Ruhezustand"
            elif action == "shutdown":
                lbl = "Herunterfahren"

        return Item(
            total=total,
            action=action,  # type: ignore[arg-type]
            prompt=prompt,
            label=lbl,
            sleep_cfg=sleep_cfg,
            target_window=tw,
            require_foreground=self._require_foreground.get(),
        )

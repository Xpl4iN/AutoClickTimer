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
from typing import Callable, Dict

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

from app.models import Item, SleepConfig, ACTION_LABELS
from app.ui.i18n import t, get_language, register_listener
from app.ui.theme import (
    BG_COLOR, SURFACE, SURFACE_L, SURFACE_H, OUTLINE,
    PRIMARY, PRIMARY_HOV, ON_SURF, ON_SURF_M, ERROR,
    FONT_BOLD, FONT_BODY, FONT_SMALL, FONT_LABEL, FONT_NUM,
    fmt, fmt_short,
)


ACTION_KEYS = ["enter", "click", "type", "sleep", "shutdown"]

ACTION_NAMES: Dict[str, Dict[str, str]] = {
    "de": {
        "enter": "Enter",
        "click": "Linksklick",
        "type": "Prompt senden",
        "sleep": "Sleep & Wake",
        "shutdown": "Herunterfahren",
    },
    "en": {
        "enter": "Enter",
        "click": "Left Click",
        "type": "Send Prompt",
        "sleep": "Sleep & Wake",
        "shutdown": "Shut Down",
    },
}


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

    titles = [t("global_window")]

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

        # Action selection state (stored as internal action ID)
        self._current_action = "enter"

        # Sleep config StringVars
        self._sleep_mode  = tk.StringVar(value="duration")
        self._sv_grace_h  = tk.StringVar(value="0")
        self._sv_grace_m  = tk.StringVar(value="0")
        self._sv_grace_s  = tk.StringVar(value="5")
        self._clk_grace_h = tk.StringVar(value=str(now.hour))
        self._clk_grace_m = tk.StringVar(value=str(now.minute))
        self._clk_grace_s = tk.StringVar(value=str(now.second))
        self._sv_postwake = tk.StringVar(value="30")

        self._target_window = tk.StringVar(value=t("global_window"))
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
            values=[t("tab_action"), t("tab_presets")],
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
        self._tab_switch.set(t("tab_action"))

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

        register_listener(self.retranslate)

    def retranslate(self, lang: str = "de") -> None:
        """Update all labels and buttons when language changes."""
        cur_tab_index = 0 if self._tab_switch.get() == t("tab_action") else 1
        new_tab_values = [t("tab_action"), t("tab_presets")]
        self._tab_switch.configure(values=new_tab_values)
        self._tab_switch.set(new_tab_values[cur_tab_index])

        # Mode selector labels
        self._mode_lbl.configure(text=t("mode_label"))
        self._rb_dur.configure(text=t("mode_duration"))
        self._rb_clk.configure(text=t("mode_clock"))

        # Time inputs
        self._render_inputs()

        # Action selector
        self._act_lbl.configure(text=t("action_type_label"))
        act_map = ACTION_NAMES.get(lang, ACTION_NAMES["de"])
        new_act_values = [act_map[k] for k in ACTION_KEYS]
        self._act_segmented.configure(values=new_act_values)
        self._act_segmented.set(act_map.get(self._current_action, "Enter"))

        # Prompt & sleep labels
        self._prompt_lbl.configure(text=t("prompt_label"))
        self._sleep_hdr.configure(text=t("sleep_config_title"))
        self._sleep_grace_lbl.configure(text=t("sleep_grace_label"))
        self._rb_sleep_dur.configure(text=t("mode_duration"))
        self._rb_sleep_clk.configure(text=t("mode_clock"))
        self._render_sleep_inputs()
        self._postwake_lbl.configure(text=t("postwake_label"))

        # Target window & labels
        self._tw_lbl.configure(text=t("target_window_label"))
        self._tw_btn.configure(text=t("refresh"))
        self._fg_cb.configure(text=t("require_foreground"))
        self._label_title.configure(text=t("label_title"))
        self._add_btn.configure(text=t("add_to_queue"))

        # Presets card
        self._presets_hdr.configure(text=t("presets_header"))
        self._p1_title.configure(text=t("p1_title"))
        self._p1_desc.configure(text=t("p1_desc"))
        self._p1_btn.configure(text=t("add_preset_btn"))

        self._p2_title.configure(text=t("p2_title"))
        self._p2_desc.configure(text=t("p2_desc"))
        self._p2_btn.configure(text=t("add_preset_btn"))

        self._p3_title.configure(text=t("p3_title"))
        self._p3_desc.configure(text=t("p3_desc"))
        self._p3_btn.configure(text=t("add_preset_btn"))

    def _on_tab_change(self, selected_tab: str) -> None:
        if selected_tab == t("tab_action"):
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

        self._mode_lbl = ctk.CTkLabel(mf, text=t("mode_label"), font=FONT_SMALL, text_color=ON_SURF_M)
        self._mode_lbl.pack(side="left", padx=(0, 12))

        self._rb_dur = ctk.CTkRadioButton(
            mf, text=t("mode_duration"), variable=self._mode, value="duration",
            command=self._on_mode_change,
            fg_color=PRIMARY, hover_color=PRIMARY_HOV,
            text_color=ON_SURF, font=FONT_BODY,
        )
        self._rb_dur.pack(side="left", padx=(0, 16))

        self._rb_clk = ctk.CTkRadioButton(
            mf, text=t("mode_clock"), variable=self._mode, value="clock",
            command=self._on_mode_change,
            fg_color=PRIMARY, hover_color=PRIMARY_HOV,
            text_color=ON_SURF, font=FONT_BODY,
        )
        self._rb_clk.pack(side="left", padx=(0, 16))

        # ---- Dynamic time inputs ----
        self._inputs_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._inputs_frame.grid(row=1, column=0, columnspan=4, sticky="ew", padx=16, pady=4)
        self._inputs_frame.grid_columnconfigure((0, 1, 2), weight=1)
        self._render_inputs()

        # ---- Action selector (Visual Segmented Button) ----
        af = ctk.CTkFrame(card, fg_color="transparent")
        af.grid(row=2, column=0, columnspan=4, sticky="ew", padx=16, pady=(8, 4))
        af.grid_columnconfigure(0, weight=1)

        self._act_lbl = ctk.CTkLabel(af, text=t("action_type_label"), font=FONT_SMALL, text_color=ON_SURF_M)
        self._act_lbl.grid(row=0, column=0, sticky="w", pady=(0, 4))

        lang = get_language()
        act_map = ACTION_NAMES.get(lang, ACTION_NAMES["de"])
        act_values = [act_map[k] for k in ACTION_KEYS]

        self._act_segmented = ctk.CTkSegmentedButton(
            af,
            values=act_values,
            command=self._on_action_change_ui,
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
        self._act_segmented.set(act_map.get(self._current_action, "Enter"))

        # ---- Prompt text area (hidden unless "Prompt senden" / "Send Prompt") ----
        self._prompt_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._prompt_frame.grid(row=3, column=0, columnspan=4, sticky="ew", padx=16, pady=4)
        self._prompt_frame.grid_columnconfigure(0, weight=1)

        self._prompt_lbl = ctk.CTkLabel(
            self._prompt_frame,
            text=t("prompt_label"),
            font=FONT_SMALL, text_color=ON_SURF_M,
        )
        self._prompt_lbl.grid(row=0, column=0, sticky="w", pady=(0, 2))

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

        self._sleep_hdr = ctk.CTkLabel(
            self._sleep_frame, text=t("sleep_config_title"),
            font=FONT_LABEL, text_color=ON_SURF_M,
        )
        self._sleep_hdr.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 4))

        # Pre-sleep mode selector
        sm_frame = ctk.CTkFrame(self._sleep_frame, fg_color="transparent")
        sm_frame.grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 4))

        self._sleep_grace_lbl = ctk.CTkLabel(sm_frame, text=t("sleep_grace_label"), font=FONT_SMALL, text_color=ON_SURF_M)
        self._sleep_grace_lbl.pack(side="left", padx=(0, 12))

        self._rb_sleep_dur = ctk.CTkRadioButton(
            sm_frame, text=t("mode_duration"), variable=self._sleep_mode, value="duration",
            command=self._on_sleep_mode_change,
            fg_color=PRIMARY, hover_color=PRIMARY_HOV,
            text_color=ON_SURF, font=FONT_BODY,
        )
        self._rb_sleep_dur.pack(side="left", padx=(0, 16))

        self._rb_sleep_clk = ctk.CTkRadioButton(
            sm_frame, text=t("mode_clock"), variable=self._sleep_mode, value="clock",
            command=self._on_sleep_mode_change,
            fg_color=PRIMARY, hover_color=PRIMARY_HOV,
            text_color=ON_SURF, font=FONT_BODY,
        )
        self._rb_sleep_clk.pack(side="left", padx=(0, 16))

        # Dynamic inputs for pre-sleep
        self._sleep_inputs_frame = ctk.CTkFrame(self._sleep_frame, fg_color="transparent")
        self._sleep_inputs_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(2, 4))
        self._sleep_inputs_frame.grid_columnconfigure((0, 1, 2), weight=1)
        self._render_sleep_inputs()

        # Post-wake delay section
        pw_section = ctk.CTkFrame(self._sleep_frame, fg_color="transparent")
        pw_section.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(4, 0))
        pw_section.grid_columnconfigure(0, weight=1)

        self._postwake_lbl = ctk.CTkLabel(
            pw_section, text=t("postwake_label"),
            font=FONT_SMALL, text_color=ON_SURF_M,
        )
        self._postwake_lbl.grid(row=0, column=0, sticky="w", pady=(0, 2))

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

        self._tw_lbl = ctk.CTkLabel(
            self._target_frame, text=t("target_window_label"),
            font=FONT_SMALL, text_color=ON_SURF_M,
        )
        self._tw_lbl.grid(row=0, column=0, sticky="w", pady=(0, 2))

        tw_inner = ctk.CTkFrame(self._target_frame, fg_color="transparent")
        tw_inner.grid(row=1, column=0, sticky="ew")
        tw_inner.grid_columnconfigure(0, weight=1)

        self._window_combo = ctk.CTkComboBox(
            tw_inner, variable=self._target_window, values=_get_open_windows(),
            fg_color=SURFACE_L, border_color=OUTLINE, text_color=ON_SURF, font=FONT_BODY,
            width=240,
        )
        self._window_combo.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self._tw_btn = ctk.CTkButton(
            tw_inner, text=t("refresh"), width=85,
            command=lambda: self._window_combo.configure(values=_get_open_windows()),
            fg_color=SURFACE_L, hover_color=PRIMARY_HOV, border_width=1, border_color=OUTLINE,
            text_color=ON_SURF, font=FONT_SMALL,
        )
        self._tw_btn.grid(row=0, column=1)

        self._fg_cb = ctk.CTkCheckBox(
            self._target_frame, text=t("require_foreground"),
            variable=self._require_foreground,
            font=FONT_SMALL, text_color=ON_SURF, fg_color=PRIMARY, hover_color=PRIMARY_HOV,
        )
        self._fg_cb.grid(row=2, column=0, sticky="w", pady=(4, 0))

        # ---- Label selector (hidden for Sleep & Wake and Herunterfahren) ----
        self._label_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._label_frame.grid(row=6, column=0, columnspan=4, sticky="ew", padx=16, pady=(4, 2))
        self._label_frame.grid_columnconfigure(1, weight=1)

        self._label_title = ctk.CTkLabel(self._label_frame, text=t("label_title"), font=FONT_SMALL, text_color=ON_SURF_M)
        self._label_title.grid(row=0, column=0, sticky="w", padx=(0, 10))

        ctk.CTkEntry(
            self._label_frame, textvariable=self._sv_lbl,
            fg_color=SURFACE_L, border_color=OUTLINE, text_color=ON_SURF,
        ).grid(row=0, column=1, sticky="ew")

        # ---- Add button ----
        add_frame = ctk.CTkFrame(card, fg_color="transparent")
        add_frame.grid(row=7, column=0, columnspan=4, sticky="ew", padx=16, pady=(6, 12))
        add_frame.grid_columnconfigure(0, weight=1)

        self._add_btn = ctk.CTkButton(
            add_frame, text=t("add_to_queue"), command=self._on_add_clicked,
            fg_color=PRIMARY, hover_color=PRIMARY_HOV, text_color="white",
            font=FONT_BOLD, corner_radius=8, height=34,
        )
        self._add_btn.grid(row=0, column=0, sticky="ew")

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

        self._presets_hdr = ctk.CTkLabel(
            card, text=t("presets_header"),
            font=FONT_LABEL, text_color=ON_SURF_M,
        )
        self._presets_hdr.grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))

        # Preset 1: Sleep & Wake + Enter
        p1 = ctk.CTkFrame(card, fg_color=SURFACE_L, border_width=1, border_color=OUTLINE, corner_radius=10)
        p1.grid(row=1, column=0, sticky="ew", padx=16, pady=6)
        p1.grid_columnconfigure(0, weight=1)

        p1_info = ctk.CTkFrame(p1, fg_color="transparent")
        p1_info.grid(row=0, column=0, sticky="w", padx=12, pady=10)
        self._p1_title = ctk.CTkLabel(p1_info, text=t("p1_title"), font=FONT_BOLD, text_color=ON_SURF)
        self._p1_title.pack(anchor="w")
        self._p1_desc = ctk.CTkLabel(
            p1_info,
            text=t("p1_desc"),
            font=FONT_SMALL, text_color=ON_SURF_M, wraplength=220, justify="left",
        )
        self._p1_desc.pack(anchor="w", pady=(2, 0))

        self._p1_btn = ctk.CTkButton(
            p1, text=t("add_preset_btn"), width=95, height=30,
            command=lambda: self._add_preset_combination("enter"),
            fg_color=PRIMARY, hover_color=PRIMARY_HOV, text_color="white",
            font=FONT_BOLD, corner_radius=6,
        )
        self._p1_btn.grid(row=0, column=1, padx=12, pady=10, sticky="e")

        # Preset 2: Sleep & Wake + Klick
        p2 = ctk.CTkFrame(card, fg_color=SURFACE_L, border_width=1, border_color=OUTLINE, corner_radius=10)
        p2.grid(row=2, column=0, sticky="ew", padx=16, pady=6)
        p2.grid_columnconfigure(0, weight=1)

        p2_info = ctk.CTkFrame(p2, fg_color="transparent")
        p2_info.grid(row=0, column=0, sticky="w", padx=12, pady=10)
        self._p2_title = ctk.CTkLabel(p2_info, text=t("p2_title"), font=FONT_BOLD, text_color=ON_SURF)
        self._p2_title.pack(anchor="w")
        self._p2_desc = ctk.CTkLabel(
            p2_info,
            text=t("p2_desc"),
            font=FONT_SMALL, text_color=ON_SURF_M, wraplength=220, justify="left",
        )
        self._p2_desc.pack(anchor="w", pady=(2, 0))

        self._p2_btn = ctk.CTkButton(
            p2, text=t("add_preset_btn"), width=95, height=30,
            command=lambda: self._add_preset_combination("click"),
            fg_color=PRIMARY, hover_color=PRIMARY_HOV, text_color="white",
            font=FONT_BOLD, corner_radius=6,
        )
        self._p2_btn.grid(row=0, column=1, padx=12, pady=10, sticky="e")

        # Preset 3: Timer + Herunterfahren
        p3 = ctk.CTkFrame(card, fg_color=SURFACE_L, border_width=1, border_color=OUTLINE, corner_radius=10)
        p3.grid(row=3, column=0, sticky="ew", padx=16, pady=(6, 14))
        p3.grid_columnconfigure(0, weight=1)

        p3_info = ctk.CTkFrame(p3, fg_color="transparent")
        p3_info.grid(row=0, column=0, sticky="w", padx=12, pady=10)
        self._p3_title = ctk.CTkLabel(p3_info, text=t("p3_title"), font=FONT_BOLD, text_color=ON_SURF)
        self._p3_title.pack(anchor="w")
        self._p3_desc = ctk.CTkLabel(
            p3_info,
            text=t("p3_desc"),
            font=FONT_SMALL, text_color=ON_SURF_M, wraplength=220, justify="left",
        )
        self._p3_desc.pack(anchor="w", pady=(2, 0))

        self._p3_btn = ctk.CTkButton(
            p3, text=t("add_preset_btn"), width=95, height=30,
            command=lambda: self._add_preset_combination("shutdown"),
            fg_color=PRIMARY, hover_color=PRIMARY_HOV, text_color="white",
            font=FONT_BOLD, corner_radius=6,
        )
        self._p3_btn.grid(row=0, column=1, padx=12, pady=10, sticky="e")

    # ------------------------------------------------------------------
    # Time input rendering
    # ------------------------------------------------------------------

    def _render_inputs(self) -> None:
        for w in self._inputs_frame.winfo_children():
            w.destroy()

        if self._mode.get() == "duration":
            fields = [(t("hours"), self._sv_h), (t("minutes"), self._sv_m), (t("seconds"), self._sv_s)]
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
            fields = [(t("hour_single"), self._clk_h), (t("minute_single"), self._clk_m), (t("second_single"), self._clk_s)]
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
            fields = [(t("hours"), self._sv_grace_h), (t("minutes"), self._sv_grace_m), (t("seconds"), self._sv_grace_s)]
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
            fields = [(t("hour_single"), self._clk_grace_h), (t("minute_single"), self._clk_grace_m), (t("second_single"), self._clk_grace_s)]
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

    def _on_action_change_ui(self, choice_text: str) -> None:
        lang = get_language()
        act_map = ACTION_NAMES.get(lang, ACTION_NAMES["de"])
        rev_map = {v: k for k, v in act_map.items()}
        self._current_action = rev_map.get(choice_text, "enter")
        self._apply_action_visibility()

    def _apply_action_visibility(self) -> None:
        if self._current_action == "type":
            self._prompt_frame.grid()
        else:
            self._prompt_frame.grid_remove()

        if self._current_action == "sleep":
            self._sleep_frame.grid()
        else:
            self._sleep_frame.grid_remove()

        if self._current_action in ("sleep", "shutdown"):
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
                    text=t("clock_preview", delta=fmt_short(delta), target=target.strftime('%H:%M:%S'))
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
                    text=t("clock_preview", delta=fmt_short(delta), target=target.strftime('%H:%M:%S'))
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
            shutdown_item = Item(total, "shutdown", label=t("default_shutdown_label"))
            self._on_add(shutdown_item)
            return

        if not _is_admin():
            messagebox.showerror(
                t("err_admin_title"),
                t("err_admin_msg"),
            )
            return

        sleep_cfg = self._get_sleep_config()
        sleep_item = Item(total, "sleep", sleep_cfg=sleep_cfg, label=t("default_sleep_label"))

        post_label = (
            t("post_wake_enter") if preset_type == "enter" else t("post_wake_click")
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
                    messagebox.showerror(t("err_title"), t("err_time_zero"))
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
                    messagebox.showerror(t("err_title"), t("err_time_past"))
                    return None
                return total
        except ValueError:
            messagebox.showerror(t("err_title"), t("err_time_invalid"))
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

        action = self._current_action

        if action == "sleep" and not _is_admin():
            messagebox.showerror(
                t("err_admin_title"),
                t("err_admin_msg"),
            )
            return None

        prompt = ""
        if action == "type":
            prompt = self._prompt_box.get("1.0", "end-1c").strip()
            if not prompt:
                messagebox.showerror(t("err_title"), t("err_prompt_missing"))
                return None

        sleep_cfg = self._get_sleep_config() if action == "sleep" else SleepConfig()

        tw = self._target_window.get()
        if tw in ("(Global / Aktives Fenster)", "(Global / Active Window)"):
            tw = ""

        lbl = self._sv_lbl.get().strip()
        if not lbl:
            if action == "sleep":
                lbl = t("default_sleep_label")
            elif action == "shutdown":
                lbl = t("default_shutdown_label")

        return Item(
            total=total,
            action=action,  # type: ignore[arg-type]
            prompt=prompt,
            label=lbl,
            sleep_cfg=sleep_cfg,
            target_window=tw,
            require_foreground=self._require_foreground.get(),
        )


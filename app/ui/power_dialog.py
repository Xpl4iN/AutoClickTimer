"""Power and lid behavior settings dialog."""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk
import tkinter as tk

from app.power_manager import (
    ACTION_VALUES,
    DISPLAY_TIMEOUTS,
    PowerManager,
    PowerSettings,
    PowerSettingsError,
    PowerSourceSettings,
)
from app.ui.i18n import STRINGS, register_listener, t, unregister_listener
from app.ui.theme import (
    OUTLINE,
    PRIMARY,
    PRIMARY_HOV,
    SURFACE,
    SURFACE_H,
    SURFACE_L,
    ON_SURF,
    ON_SURF_M,
    ERROR,
    SUCCESS,
    FONT_BODY,
    FONT_BOLD,
    FONT_SMALL,
    FONT_TITLE,
)


class PowerSettingsDialog(ctk.CTkToplevel):
    """Modal editor for the active Windows power plan."""

    def __init__(self, parent: ctk.CTk, on_applied: Callable[[], None] | None = None) -> None:
        super().__init__(parent)
        self._on_applied = on_applied or (lambda: None)
        self._manager = PowerManager()
        self._vars: dict[str, dict[str, tk.StringVar]] = {}
        self._source_frames: list[tuple[ctk.CTkLabel, ctk.CTkFrame]] = []

        self.title(t("power_title"))
        self.geometry("760x650")
        self.minsize(620, 560)
        self.configure(fg_color=SURFACE)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)

        self._build()
        self._load()
        register_listener(self.retranslate)

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 12))
        header.grid_columnconfigure(0, weight=1)

        self._title = ctk.CTkLabel(header, text=t("power_title"), font=FONT_TITLE, text_color=ON_SURF)
        self._title.grid(row=0, column=0, sticky="w")
        self._subtitle = ctk.CTkLabel(
            header,
            text=t("power_subtitle"),
            font=FONT_SMALL,
            text_color=ON_SURF_M,
            justify="left",
            wraplength=680,
        )
        self._subtitle.grid(row=1, column=0, sticky="w", pady=(6, 0))

        self._body = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=SURFACE_H,
            scrollbar_button_hover_color=PRIMARY_HOV,
        )
        self._body.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 8))
        self._body.grid_columnconfigure(0, weight=1)

        self._build_source_card("ac", "plugged_in")
        self._build_source_card("dc", "on_battery")

        self._hint = ctk.CTkLabel(
            self._body,
            text=t("power_remote_hint"),
            font=FONT_SMALL,
            text_color=PRIMARY,
            justify="left",
            wraplength=680,
        )
        self._hint.grid(row=2, column=0, sticky="ew", padx=12, pady=(2, 12))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=28, pady=(4, 20))
        footer.grid_columnconfigure(0, weight=1)

        self._status = ctk.CTkLabel(footer, text="", font=FONT_SMALL, text_color=ON_SURF_M, anchor="w")
        self._status.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self._cancel = ctk.CTkButton(
            footer,
            text=t("cancel"),
            command=self._close,
            width=100,
            fg_color=SURFACE_L,
            hover_color=SURFACE_H,
            border_width=1,
            border_color=OUTLINE,
            text_color=ON_SURF,
            font=FONT_BOLD,
        )
        self._cancel.grid(row=0, column=1, padx=(0, 8))
        self._apply = ctk.CTkButton(
            footer,
            text=t("power_apply"),
            command=self._apply_settings,
            width=130,
            fg_color=PRIMARY,
            hover_color=PRIMARY_HOV,
            text_color="white",
            font=FONT_BOLD,
        )
        self._apply.grid(row=0, column=2)

    def _build_source_card(self, source: str, label_key: str) -> None:
        row = 0 if source == "ac" else 1
        card = ctk.CTkFrame(self._body, fg_color=SURFACE, border_width=1, border_color=OUTLINE, corner_radius=12)
        card.grid(row=row, column=0, sticky="ew", padx=0, pady=(0, 12))
        card.grid_columnconfigure(0, weight=1)

        heading = ctk.CTkLabel(card, text=t(label_key), font=FONT_BOLD, text_color=ON_SURF)
        heading.grid(row=0, column=0, sticky="w", padx=16, pady=(14, 8))
        self._source_frames.append((heading, card))

        values = {
            "lid_action": tk.StringVar(),
            "power_button_action": tk.StringVar(),
            "display_timeout": tk.StringVar(),
        }
        self._vars[source] = values

        self._build_row(card, 1, "power_button_label", "power_button_action", values["power_button_action"])
        self._build_row(card, 2, "lid_label", "lid_action", values["lid_action"])
        self._build_row(card, 3, "display_timeout_label", "display_timeout", values["display_timeout"])

    def _build_row(
        self,
        parent: ctk.CTkFrame,
        row: int,
        label_key: str,
        setting_key: str,
        variable: tk.StringVar,
    ) -> None:
        label = ctk.CTkLabel(parent, text=t(label_key), font=FONT_BODY, text_color=ON_SURF)
        label.grid(row=row, column=0, sticky="w", padx=(28, 12), pady=6)

        combo = ctk.CTkComboBox(
            parent,
            variable=variable,
            values=self._display_values(setting_key),
            width=210,
            height=34,
            fg_color=SURFACE_L,
            border_color=OUTLINE,
            button_color=SURFACE_H,
            button_hover_color=PRIMARY_HOV,
            text_color=ON_SURF,
            font=FONT_BODY,
            state="readonly",
        )
        combo.grid(row=row, column=1, sticky="e", padx=(12, 16), pady=6)
        parent.grid_columnconfigure(1, weight=0)

    def _display_values(self, setting_key: str) -> list[str]:
        if setting_key == "display_timeout":
            return [t(f"timeout_{key}") for key in DISPLAY_TIMEOUTS]
        return [t(f"power_action_{key}") for key in ACTION_VALUES]

    def _load(self) -> None:
        try:
            settings = self._manager.read_settings()
        except PowerSettingsError as exc:
            self._status.configure(text=t("power_read_error", err=str(exc)), text_color=ERROR)
            settings = PowerSettings(PowerSourceSettings(), PowerSourceSettings())
        self._set_source("ac", settings.plugged_in)
        self._set_source("dc", settings.on_battery)

    def _set_source(self, source: str, values: PowerSourceSettings) -> None:
        for key, value in (
            ("lid_action", values.lid_action),
            ("power_button_action", values.power_button_action),
            ("display_timeout", values.display_timeout),
        ):
            self._vars[source][key].set(self._display_value(key, value))

    def _display_value(self, setting_key: str, value: str) -> str:
        if setting_key == "display_timeout":
            return t(f"timeout_{value}")
        return t(f"power_action_{value}")

    def _internal_value(self, setting_key: str, display_value: str) -> str:
        if setting_key == "display_timeout":
            for key in DISPLAY_TIMEOUTS:
                if any(display_value == strings.get(f"timeout_{key}") for strings in STRINGS.values()):
                    return key
            return "15_min"
        for key in ACTION_VALUES:
            if any(display_value == strings.get(f"power_action_{key}") for strings in STRINGS.values()):
                return key
        return "sleep"

    def _apply_settings(self) -> None:
        settings = PowerSettings(
            plugged_in=self._read_source("ac"),
            on_battery=self._read_source("dc"),
        )
        self._apply.configure(state="disabled")
        try:
            self._manager.apply_settings(settings)
        except PowerSettingsError as exc:
            self._status.configure(text=t("power_apply_error", err=str(exc)), text_color=ERROR)
            self._apply.configure(state="normal")
            return

        self._status.configure(text=t("power_applied"), text_color=SUCCESS)
        self._apply.configure(state="normal")
        self._on_applied()

    def _read_source(self, source: str) -> PowerSourceSettings:
        values = self._vars[source]
        return PowerSourceSettings(
            lid_action=self._internal_value("lid_action", values["lid_action"].get()),
            power_button_action=self._internal_value("power_button_action", values["power_button_action"].get()),
            display_timeout=self._internal_value("display_timeout", values["display_timeout"].get()),
        )

    def retranslate(self, lang: str = "de") -> None:
        self._title.configure(text=t("power_title"))
        self._subtitle.configure(text=t("power_subtitle"))
        self._hint.configure(text=t("power_remote_hint"))
        self._cancel.configure(text=t("cancel"))
        self._apply.configure(text=t("power_apply"))
        for source in ("ac", "dc"):
            self._vars[source]["lid_action"].set(self._display_value("lid_action", self._internal_value("lid_action", self._vars[source]["lid_action"].get())))
            self._vars[source]["power_button_action"].set(self._display_value("power_button_action", self._internal_value("power_button_action", self._vars[source]["power_button_action"].get())))
            self._vars[source]["display_timeout"].set(self._display_value("display_timeout", self._internal_value("display_timeout", self._vars[source]["display_timeout"].get())))
        # Rebuilding the cards keeps combo-box choices in the new language.
        # Existing values remain in their StringVars and are restored above.
        for _, card in self._source_frames:
            for child in card.winfo_children()[1:]:
                child.destroy()
        for source, card_info in zip(("ac", "dc"), self._source_frames):
            card = card_info[1]
            self._build_row(card, 1, "power_button_label", "power_button_action", self._vars[source]["power_button_action"])
            self._build_row(card, 2, "lid_label", "lid_action", self._vars[source]["lid_action"])
            self._build_row(card, 3, "display_timeout_label", "display_timeout", self._vars[source]["display_timeout"])
        for index, (heading, _) in enumerate(self._source_frames):
            heading.configure(text=t("plugged_in" if index == 0 else "on_battery"))

    def _close(self) -> None:
        unregister_listener(self.retranslate)
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

"""
app/ui/i18n.py -- Internationalization (DE / EN) for AutoClick Timer.

Supports runtime language switching between German (with proper umlauts) and English.
No emojis and no em dashes.
"""
from __future__ import annotations

from typing import Callable, List

_current_lang: str = "de"
_listeners: List[Callable[[str], None]] = []

STRINGS = {
    "de": {
        # App Header
        "app_title": "AutoClick Timer",
        "failsafe_tip": "Stop: Schaltfläche oder Strg+Umschalt+F12 verwenden. Die Bildschirmecke löst keinen Stop aus.",
        "control_ready": "CLI/MCP: {endpoint}",
        "caffeine": "Caffeine",
        "update_available": "Update {tag} verfügbar",
        "update_downloading": "Wird geladen...",
        "update_log": "Neue Version verfügbar: {tag} - Klick auf 'Update {tag}' zum Aktualisieren.",
        "update_started": "Update auf {tag} wird gestartet...",

        # Power and lid settings
        "power_button": "Power",
        "power_title": "Power- und Deckelverhalten",
        "power_subtitle": "Lege fest, was beim Drücken des Einschaltknopfs oder beim Schließen des Deckels passiert. Die Bildschirmabschaltung ist unabhängig, sodass der PC für Fernzugriff wach bleiben kann, während der Bildschirm ausgeht.",
        "plugged_in": "Netzbetrieb",
        "on_battery": "Akkubetrieb",
        "power_button_label": "Beim Drücken des Einschaltknopfs",
        "lid_label": "Beim Schließen des Deckels",
        "display_timeout_label": "Bildschirm ausschalten nach",
        "sleep_timeout_label": "PC in den Energiesparmodus nach",
        "power_action_do_nothing": "Nichts unternehmen",
        "power_action_sleep": "Energiesparmodus",
        "power_action_hibernate": "Ruhezustand",
        "power_action_shutdown": "Herunterfahren",
        "timeout_never": "Nie",
        "timeout_1_min": "1 Minute",
        "timeout_5_min": "5 Minuten",
        "timeout_10_min": "10 Minuten",
        "timeout_15_min": "15 Minuten",
        "timeout_30_min": "30 Minuten",
        "timeout_60_min": "60 Minuten",
        "timeout_120_min": "2 Stunden",
        "timeout_240_min": "4 Stunden",
        "timeout_480_min": "8 Stunden",
        "power_remote_hint": "Für Fernzugriff: Wähle beim Schließen des Deckels Nichts unternehmen und stelle eine Bildschirmabschaltung ein. Der PC bleibt für Fernverbindungen wach, während der Bildschirm ausgehen kann.",
        "power_apply": "Einstellungen anwenden",
        "power_applied": "Energieeinstellungen angewendet.",
        "power_read_error": "Energieeinstellungen konnten nicht gelesen werden: {err}",
        "power_apply_error": "Energieeinstellungen konnten nicht angewendet werden: {err}",
        "cancel": "Abbrechen",

        # Tray
        "tray_show": "Anzeigen",
        "tray_stop": "Stop",
        "tray_quit": "Beenden",

        # Form Tabs & Modes
        "tab_action": "Aktion erstellen",
        "tab_presets": "Vorlagen",
        "mode_label": "Modus:",
        "mode_duration": "Timer (Dauer)",
        "mode_clock": "Uhrzeit",
        "hours": "Stunden",
        "minutes": "Minuten",
        "seconds": "Sekunden",
        "hour_single": "Stunde",
        "minute_single": "Minute",
        "second_single": "Sekunde",
        "clock_preview": "-> in {delta} (um {target})",

        # Actions
        "action_type_label": "Aktionstyp:",
        "act_enter": "Enter",
        "act_click": "Linksklick",
        "act_type": "Prompt senden",
        "act_sleep": "Sleep & Wake",
        "act_shutdown": "Herunterfahren",

        # Prompt & Sleep Inputs
        "prompt_label": "Prompt-Text (eingefügt + Enter gesendet):",
        "sleep_config_title": "Sleep-Konfiguration",
        "sleep_grace_label": "Wartezeit vor Schlaf:",
        "postwake_label": "Post-Wake-Verzögerung (Sek.):",

        # Target Window & Label
        "target_window_label": "Ziel-Fenster (Background-Input):",
        "global_window": "(Global / Aktives Fenster)",
        "refresh": "Aktualisieren",
        "require_foreground": "Zwingend in den Vordergrund holen",
        "label_title": "Bezeichnung:",
        "add_to_queue": "+ Zur Warteschlange",

        # Default item labels
        "default_sleep_label": "Ruhezustand",
        "default_shutdown_label": "Herunterfahren",
        "post_wake_enter": "Enter nach Aufwachen",
        "post_wake_click": "Linksklick nach Aufwachen",

        # Presets
        "presets_header": "SCHNELL-VORLAGEN",
        "p1_title": "Sleep & Wake + Enter",
        "p1_desc": "Rechner in Ruhezustand versetzen und zur Zielzeit mit Enter wecken.",
        "p2_title": "Sleep & Wake + Linksklick",
        "p2_desc": "Rechner in Ruhezustand versetzen und zur Zielzeit mit Klick wecken.",
        "p3_title": "Timer + Herunterfahren",
        "p3_desc": "Rechner nach Ablauf der eingestellten Zeit vollständig herunterfahren.",
        "add_preset_btn": "+ Hinzufügen",

        # Queue Panel
        "queue_header": "WARTESCHLANGE",
        "empty_queue": "Noch keine Aktionen - füge deine erste links hinzu.",
        "start_btn": "Starten",
        "start_later_btn": "Später...",
        "stop_btn": "Stop",
        "reset_btn": "Reset",
        "clear_btn": "Leeren",
        "save_btn": "Speichern",
        "load_btn": "Laden",

        # Queue Phases & Status
        "status_done": "Fertig",
        "status_waiting": "Wartet",
        "status_running": "Läuft",
        "status_grace": "Vorbereitung",
        "status_sleeping": "Schläft...",
        "status_post_wake": "Aufgewacht",
        "status_awake_fallback": "Wach (Fallback)",
        "step_running": "Schritt {index}/{total} läuft...",
        "all_done": "Alle {count} Aktionen abgeschlossen!",
        "stopped": "Gestoppt.",
        "failsafe_status": "Failsafe!",
        "ready": "Bereit. Keine Aktionen ausgeführt.",

        # Meta formatting in rows
        "meta_sleep": "(Vorbereitung: {grace}s, Post-Wake: {post}s)",

        # Log Panel
        "log_title": "Log",
        "log_cleared": "Log geleert.",
        "log_queue_started": "Warteschlange gestartet.",
        "log_reset": "Zurückgesetzt.",
        "log_queue_cleared": "Warteschlange geleert.",
        "log_caffeine_on": "Caffeine Mode aktiviert (Anti-Lock).",
        "log_caffeine_off": "Caffeine Mode deaktiviert.",
        "log_profile_saved": "Profil gespeichert: {path}",
        "log_profile_save_err": "Fehler beim Speichern: {err}",
        "log_profile_loaded": "Profil geladen: {path}",
        "log_profile_load_err": "Fehler beim Laden: {err}",
        "log_item_added": "+ [{label}] {total}s hinzugefügt.",
        "log_scheduled": "Warteschlange geplant für {time} (in {delay} Min).",
        "log_scheduled_err": "Ungültige Eingabe für geplanten Start.",
        "log_control_ready": "Fernsteuerung aktiv: {endpoint}",
        "log_remote_action": "{source}: {action}",
        "log_remote_error": "Fernsteuerung abgelehnt: {err}",

        # Schedule Dialog
        "dlg_later_title": "Später starten",
        "dlg_later_text": "In wie vielen Minuten soll die Warteschlange starten?",

        # Validation Messages
        "err_title": "Fehler",
        "err_admin_title": "Administrator",
        "err_admin_msg": "Sleep & Wake benötigt Administratorrechte. Bitte als Administrator neu starten.",
        "err_time_zero": "Zeit > 0 erforderlich.",
        "err_time_past": "Zielzeit liegt in der Vergangenheit.",
        "err_time_invalid": "Ungültige Zeit-Eingabe.",
        "err_prompt_missing": "Prompt-Text fehlt.",
    },
    "en": {
        # App Header
        "app_title": "AutoClick Timer",
        "failsafe_tip": "Stop: Use the button or Ctrl+Shift+F12. The screen corner no longer stops the queue.",
        "control_ready": "CLI/MCP: {endpoint}",
        "caffeine": "Caffeine",
        "update_available": "Update {tag} available",
        "update_downloading": "Downloading...",
        "update_log": "New version available: {tag} - Click 'Update {tag}' to install.",
        "update_started": "Starting update to {tag}...",

        # Power and lid settings
        "power_button": "Power",
        "power_title": "Power and Lid Behavior",
        "power_subtitle": "Choose what happens when the power button or lid is used. Display timeout is independent, so the PC can stay available for remote access while the screen turns off.",
        "plugged_in": "Plugged in",
        "on_battery": "On battery",
        "power_button_label": "Pressing the power button will make my PC",
        "lid_label": "Closing the lid will make my PC",
        "display_timeout_label": "Turn off the display after",
        "sleep_timeout_label": "Put the PC to sleep after",
        "power_action_do_nothing": "Do nothing",
        "power_action_sleep": "Sleep",
        "power_action_hibernate": "Hibernate",
        "power_action_shutdown": "Shut down",
        "timeout_never": "Never",
        "timeout_1_min": "1 minute",
        "timeout_5_min": "5 minutes",
        "timeout_10_min": "10 minutes",
        "timeout_15_min": "15 minutes",
        "timeout_30_min": "30 minutes",
        "timeout_60_min": "60 minutes",
        "timeout_120_min": "2 hours",
        "timeout_240_min": "4 hours",
        "timeout_480_min": "8 hours",
        "power_remote_hint": "Remote access: choose Do nothing for lid close, then set a display timeout. The computer remains awake for remote connections while its display can turn off.",
        "power_apply": "Apply settings",
        "power_applied": "Power settings applied.",
        "power_read_error": "Could not read current power settings: {err}",
        "power_apply_error": "Could not apply power settings: {err}",
        "cancel": "Cancel",

        # Tray
        "tray_show": "Show",
        "tray_stop": "Stop",
        "tray_quit": "Exit",

        # Form Tabs & Modes
        "tab_action": "Create Action",
        "tab_presets": "Presets",
        "mode_label": "Mode:",
        "mode_duration": "Timer (Duration)",
        "mode_clock": "Clock Time",
        "hours": "Hours",
        "minutes": "Minutes",
        "seconds": "Seconds",
        "hour_single": "Hour",
        "minute_single": "Minute",
        "second_single": "Second",
        "clock_preview": "-> in {delta} (at {target})",

        # Actions
        "action_type_label": "Action Type:",
        "act_enter": "Enter",
        "act_click": "Left Click",
        "act_type": "Send Prompt",
        "act_sleep": "Sleep & Wake",
        "act_shutdown": "Shut Down",

        # Prompt & Sleep Inputs
        "prompt_label": "Prompt Text (pasted + Enter sent):",
        "sleep_config_title": "Sleep Configuration",
        "sleep_grace_label": "Grace Period before Sleep:",
        "postwake_label": "Post-Wake Delay (sec):",

        # Target Window & Label
        "target_window_label": "Target Window (Background Input):",
        "global_window": "(Global / Active Window)",
        "refresh": "Refresh",
        "require_foreground": "Force bring to foreground",
        "label_title": "Label:",
        "add_to_queue": "+ Add to Queue",

        # Default item labels
        "default_sleep_label": "Sleep Mode",
        "default_shutdown_label": "Shut Down",
        "post_wake_enter": "Enter after Wake",
        "post_wake_click": "Left Click after Wake",

        # Presets
        "presets_header": "QUICK PRESETS",
        "p1_title": "Sleep & Wake + Enter",
        "p1_desc": "Put computer to sleep and wake with Enter key at target time.",
        "p2_title": "Sleep & Wake + Left Click",
        "p2_desc": "Put computer to sleep and wake with mouse click at target time.",
        "p3_title": "Timer + Shut Down",
        "p3_desc": "Safely shut down computer after the specified time elapsed.",
        "add_preset_btn": "+ Add",

        # Queue Panel
        "queue_header": "QUEUE",
        "empty_queue": "No actions yet - add your first one on the left.",
        "start_btn": "Start",
        "start_later_btn": "Later...",
        "stop_btn": "Stop",
        "reset_btn": "Reset",
        "clear_btn": "Clear",
        "save_btn": "Save",
        "load_btn": "Load",

        # Queue Phases & Status
        "status_done": "Done",
        "status_waiting": "Waiting",
        "status_running": "Running",
        "status_grace": "Preparing",
        "status_sleeping": "Sleeping...",
        "status_post_wake": "Awake",
        "status_awake_fallback": "Awake (Fallback)",
        "step_running": "Step {index}/{total} running...",
        "all_done": "All {count} actions completed!",
        "stopped": "Stopped.",
        "failsafe_status": "Failsafe!",
        "ready": "Ready. No actions executed.",

        # Meta formatting in rows
        "meta_sleep": "(Grace: {grace}s, Post-Wake: {post}s)",

        # Log Panel
        "log_title": "Log",
        "log_cleared": "Log cleared.",
        "log_queue_started": "Queue started.",
        "log_reset": "Reset.",
        "log_queue_cleared": "Queue cleared.",
        "log_caffeine_on": "Caffeine Mode enabled (Anti-Lock).",
        "log_caffeine_off": "Caffeine Mode disabled.",
        "log_profile_saved": "Profile saved: {path}",
        "log_profile_save_err": "Error saving profile: {err}",
        "log_profile_loaded": "Profile loaded: {path}",
        "log_profile_load_err": "Error loading profile: {err}",
        "log_item_added": "+ [{label}] {total}s added.",
        "log_scheduled": "Queue scheduled for {time} (in {delay} min).",
        "log_scheduled_err": "Invalid input for scheduled start.",
        "log_control_ready": "Remote control ready: {endpoint}",
        "log_remote_action": "{source}: {action}",
        "log_remote_error": "Remote control rejected: {err}",

        # Schedule Dialog
        "dlg_later_title": "Start Later",
        "dlg_later_text": "In how many minutes should the queue start?",

        # Validation Messages
        "err_title": "Error",
        "err_admin_title": "Administrator",
        "err_admin_msg": "Sleep & Wake requires administrator privileges. Please restart as administrator.",
        "err_time_zero": "Time > 0 required.",
        "err_time_past": "Target time is in the past.",
        "err_time_invalid": "Invalid time input.",
        "err_prompt_missing": "Prompt text is missing.",
    },
}


def get_language() -> str:
    return _current_lang


def set_language(lang: str) -> None:
    global _current_lang
    if lang in STRINGS and lang != _current_lang:
        _current_lang = lang
        for listener in list(_listeners):
            try:
                listener(_current_lang)
            except Exception:
                pass


def register_listener(callback: Callable[[str], None]) -> None:
    if callback not in _listeners:
        _listeners.append(callback)


def unregister_listener(callback: Callable[[str], None]) -> None:
    if callback in _listeners:
        _listeners.remove(callback)


def t(key: str, **kwargs) -> str:
    """Lookup translated text and format with optional kwargs."""
    lang_dict = STRINGS.get(_current_lang, STRINGS["de"])
    template = lang_dict.get(key, STRINGS["de"].get(key, key))
    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template

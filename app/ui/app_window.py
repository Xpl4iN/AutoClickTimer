"""
app/ui/app_window.py -- Main application window.

Responsibilities:
  - Layout: header, left panel (form + log), right panel (queue + controls)
  - Owns the queue list (List[Item])
  - Owns the QueueExecutor instance
  - Wires executor callbacks through root.after() so worker thread never
    touches CTk widgets directly
  - Handles responsive layout switching at 720px breakpoint
"""
from __future__ import annotations

import os
import sys
import threading
from typing import List

import customtkinter as ctk

from app.executor import ExecutorCallbacks, QueueExecutor
from app.models import Item
from app.ui.form_panel import FormPanel
from app.ui.log_panel import LogPanel
from app.ui.queue_panel import QueuePanel
from app.ui.theme import BG_COLOR, ON_SURF, ON_SURF_M, ERROR, WARNING, FONT_TITLE, FONT_SMALL, FONT_BOLD
from app.version import VERSION, REPO


class AppWindow(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"AutoClick Timer  v{VERSION}")
        self.geometry("940x720")
        self.minsize(380, 620)
        self.configure(fg_color=BG_COLOR)

        self._load_icon()

        # ---- App state ----
        self._queue: List[Item] = []
        self._alive = True   # set to False in _on_close; guards safe() callbacks
        self._update_info = None

        # ---- Build executor (no queue yet) ----
        self._executor = QueueExecutor(self._make_callbacks())

        # ---- Build UI ----
        self._build_layout()

        # ---- Window events ----
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Configure>", self._on_resize)
        self.bind("<Unmap>", self._on_minimize)
        self._is_slim = False
        self._tray_icon = None
        
        self.after(150, self._init_layout)
        # Check for updates 3 s after startup so it doesn't delay first paint
        self.after(3000, self._start_update_check)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=0, minsize=380)
        self.grid_columnconfigure(1, weight=1, minsize=340)

        # Header
        self._hdr = ctk.CTkFrame(self, fg_color="transparent")
        self._hdr.grid(row=0, column=0, columnspan=2, sticky="ew", padx=24, pady=(18, 6))
        self._hdr.grid_columnconfigure(0, weight=0)
        self._hdr.grid_columnconfigure(1, weight=1)
        self._hdr.grid_columnconfigure(2, weight=0)  # caffeine switch
        self._hdr.grid_columnconfigure(3, weight=0)  # update button column

        self._title_lbl = ctk.CTkLabel(
            self._hdr, text=f"AutoClick Timer  v{VERSION}", font=FONT_TITLE, text_color=ON_SURF
        )
        self._title_lbl.grid(row=0, column=0, sticky="w")

        # Update button -- hidden until a newer version is detected
        self._update_btn = ctk.CTkButton(
            self._hdr, text="",
            fg_color=WARNING, hover_color="#d97706",
            text_color="#1a1a1a", font=FONT_BOLD,
            corner_radius=8, width=120,
            command=self._on_update_click,
        )
        self._update_btn.grid(row=0, column=3, padx=(12, 0))
        self._update_btn.grid_remove()   # hidden until update found
        
        self._caffeine_var = ctk.BooleanVar(value=False)
        self._caffeine_switch = ctk.CTkSwitch(
            self._hdr, text="☕ Caffeine", variable=self._caffeine_var,
            font=FONT_SMALL, text_color=ON_SURF, command=self._on_caffeine_toggle
        )
        self._caffeine_switch.grid(row=0, column=2, padx=(12, 12), sticky="e")

        self._failsafe_lbl = ctk.CTkLabel(
            self._hdr,
            text="Notfall-Stop: Maus ganz oben-links in die Bildschirmecke schieben",
            font=("Segoe UI", 10, "bold"), text_color=ERROR,
            wraplength=400, justify="right",
        )
        self._failsafe_lbl.grid(row=0, column=1, sticky="e")

        # Left panel
        self._left = ctk.CTkFrame(self, fg_color="transparent")
        self._left.grid(row=1, column=0, sticky="nsew", padx=(20, 10), pady=(10, 16))
        self._left.grid_columnconfigure(0, weight=1)
        self._left.grid_rowconfigure(0, weight=0)
        self._left.grid_rowconfigure(1, weight=0)
        self._left.grid_rowconfigure(2, weight=1)

        self._form = FormPanel(self._left, on_add=self._on_add)
        self._log  = LogPanel(self._left)
        self._log.grid(row=2, column=0, sticky="nsew")

        # Right panel
        self._right = ctk.CTkFrame(self, fg_color="transparent")
        self._right.grid(row=1, column=1, sticky="nsew", padx=(10, 20), pady=(10, 16))
        self._right.grid_columnconfigure(0, weight=1)
        self._right.grid_rowconfigure(0, weight=1)
        self._right.grid_rowconfigure(1, weight=0)

        self._queue_panel = QueuePanel(
            self._right,
            on_start=self._on_start,
            on_stop=self._on_stop,
            on_reset=self._on_reset,
            on_clear=self._on_clear,
            on_remove=self._on_remove,
            is_running=lambda: self._executor.running,
            on_save=self._on_save,
            on_load=self._on_load,
            on_start_later=self._on_start_later,
        )

    def _init_layout(self) -> None:
        self.update_idletasks()
        is_slim = self.winfo_width() < 780
        self._is_slim = is_slim
        self._apply_layout(is_slim)

    def _on_resize(self, event) -> None:
        if str(event.widget) != str(self):
            return
        width = self.winfo_width()
        is_slim = width < 780
        if is_slim != self._is_slim:
            self._is_slim = is_slim
            self._apply_layout(is_slim)

    def _apply_layout(self, is_slim: bool) -> None:
        if is_slim:
            self.grid_rowconfigure(1, weight=0)
            self.grid_rowconfigure(2, weight=1)
            self.grid_columnconfigure(0, weight=1, minsize=0)
            self.grid_columnconfigure(1, weight=0, minsize=0)

            self._hdr.grid_configure(columnspan=1)
            self._title_lbl.grid_configure(row=0, column=0, sticky="w")
            self._failsafe_lbl.grid_configure(row=1, column=0, sticky="w", pady=(2, 0))

            self._left.grid_configure(row=1, column=0, columnspan=1, padx=16, pady=(10, 6))
            self._right.grid_configure(row=2, column=0, columnspan=1, padx=16, pady=(6, 16))
            self._left.grid_rowconfigure(2, weight=0)
            self._queue_panel.configure_slim()
        else:
            self.grid_rowconfigure(1, weight=1)
            self.grid_rowconfigure(2, weight=0)
            self.grid_columnconfigure(0, weight=0, minsize=380)
            self.grid_columnconfigure(1, weight=1, minsize=340)

            self._hdr.grid_configure(columnspan=2)
            self._title_lbl.grid_configure(row=0, column=0, sticky="w")
            self._failsafe_lbl.grid_configure(row=0, column=1, sticky="e", pady=0)

            self._left.grid_configure(row=1, column=0, columnspan=1, padx=(20, 10), pady=(10, 16))
            self._right.grid_configure(row=1, column=1, columnspan=1, padx=(10, 20), pady=(10, 16))
            self._left.grid_rowconfigure(2, weight=1)
            self._queue_panel.configure_wide()

    # ------------------------------------------------------------------
    # Executor callbacks -- wired through after() for thread safety
    # ------------------------------------------------------------------

    def _make_callbacks(self) -> ExecutorCallbacks:
        def safe(fn):
            """
            Wrap fn so it runs on the Tk main thread via after().
            Drops the call silently if the window is already closing.
            Reading self._alive is GIL-safe (plain bool write in main thread).
            """
            def wrapper(*args, **kwargs):
                if not self._alive:
                    return
                try:
                    self.after(0, lambda: fn(*args, **kwargs))
                except Exception:
                    pass  # window was destroyed between the check and after()
            return wrapper

        return ExecutorCallbacks(
            on_tick=safe(self._cb_tick),
            on_step_start=safe(self._cb_step_start),
            on_step_done=safe(self._cb_step_done),
            on_all_done=safe(self._cb_all_done),
            on_stopped=safe(self._cb_stopped),
            on_log=safe(self._cb_log),
            on_failsafe=safe(self._cb_failsafe),
        )

    def _cb_tick(self, item: Item) -> None:
        self._queue_panel.update_row(item)

    def _cb_step_start(self, item: Item, index: int, total: int) -> None:
        self._queue_panel.set_status(f"Schritt {index + 1}/{total} laeuft...")
        self._queue_panel.render(self._queue)

    def _cb_step_done(self, item: Item) -> None:
        self._queue_panel.render(self._queue)

    def _cb_all_done(self, count: int) -> None:
        self._log.append(f"Alle {count} Aktionen abgeschlossen!")
        self._queue_panel.set_status("Fertig!")
        self._queue_panel.set_controls_enabled(running=False)

    def _cb_stopped(self) -> None:
        self._log.append("Gestoppt.")
        self._queue_panel.set_status("Gestoppt.")
        self._queue_panel.set_controls_enabled(running=False)

    def _cb_log(self, msg: str) -> None:
        self._log.append(msg)

    def _cb_failsafe(self) -> None:
        self._executor.stop()
        self._queue_panel.set_status("Failsafe!")
        self._queue_panel.set_controls_enabled(running=False)

    # ------------------------------------------------------------------
    # Queue event handlers
    # ------------------------------------------------------------------

    def _on_add(self, item: Item) -> None:
        self._queue.append(item)
        self._queue_panel.render(self._queue)
        self._log.append(f"+ [{item.label}] {item.total}s hinzugefuegt.")

    def _on_remove(self, item: Item) -> None:
        if self._executor.running:
            return
        self._queue.remove(item)
        self._queue_panel.render(self._queue)

    def _on_start(self) -> None:
        if self._executor.running or not self._queue:
            return
        self._queue_panel.set_controls_enabled(running=True)
        self._log.append("Warteschlange gestartet.")
        self._executor.start(self._queue)

    def _on_stop(self) -> None:
        self._executor.stop()
        # UI update happens via on_stopped callback

    def _on_reset(self) -> None:
        if self._executor.running:
            self._executor.stop()
        for item in self._queue:
            item.reset()
        self._queue_panel.render(self._queue)
        self._queue_panel.set_status("")
        self._log.append("Zurueckgesetzt.")

    def _on_clear(self) -> None:
        if self._executor.running:
            self._executor.stop()
        self._queue.clear()
        self._queue_panel.render(self._queue)
        self._queue_panel.set_status("")
        self._log.append("Warteschlange geleert.")

    def _on_caffeine_toggle(self) -> None:
        active = self._caffeine_var.get()
        self._executor.set_caffeine(active)
        if active:
            self._log.append("☕ Caffeine Mode aktiviert (Anti-Lock).")
        else:
            self._log.append("Caffeine Mode deaktiviert.")

    def _on_save(self) -> None:
        import json
        from tkinter import filedialog
        if not self._queue:
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".act",
            filetypes=[("AutoClickTimer Profile", "*.act"), ("All Files", "*.*")],
        )
        if not filepath:
            return
        try:
            data = [item.to_dict() for item in self._queue]
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            self._log.append(f"Profil gespeichert: {filepath}")
        except Exception as e:
            self._log.append(f"Fehler beim Speichern: {e}")

    def _on_load(self) -> None:
        import json
        from tkinter import filedialog
        if self._executor.running:
            return
        filepath = filedialog.askopenfilename(
            filetypes=[("AutoClickTimer Profile", "*.act"), ("All Files", "*.*")],
        )
        if not filepath:
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._queue.clear()
            for d in data:
                self._queue.append(Item.from_dict(d))
            self._queue_panel.render(self._queue)
            self._log.append(f"Profil geladen: {filepath}")
        except Exception as e:
            self._log.append(f"Fehler beim Laden: {e}")

    def _on_start_later(self) -> None:
        if self._executor.running or not self._queue:
            return
        import tkinter.simpledialog
        from datetime import datetime, timedelta
        
        ans = tkinter.simpledialog.askstring(
            "Später starten", 
            "In wie vielen Minuten soll die Warteschlange starten?",
            parent=self
        )
        if not ans:
            return
        try:
            delay = int(ans)
            if delay <= 0:
                return
            start_at = datetime.now() + timedelta(minutes=delay)
            self._queue_panel.set_controls_enabled(running=True)
            self._log.append(f"Warteschlange geplant für {start_at.strftime('%H:%M:%S')} (in {delay} Min).")
            self._executor.start(self._queue, start_at=start_at)
        except ValueError:
            self._log.append("Ungültige Eingabe für geplanten Start.")

    # ------------------------------------------------------------------
    # Auto-update
    # ------------------------------------------------------------------

    def _start_update_check(self) -> None:
        """Launch a background thread to query the GitHub API for a new release."""
        threading.Thread(target=self._bg_check_update, daemon=True).start()

    def _bg_check_update(self) -> None:
        """Runs in a daemon thread -- no UI access allowed here."""
        from app.updater import UpdateChecker
        info = UpdateChecker(REPO, VERSION).check()
        if info is not None and self._alive:
            try:
                self.after(0, lambda: self._show_update_available(info))
            except Exception:
                pass

    def _show_update_available(self, info) -> None:
        """Called on the Tk main thread when a newer release is found."""
        self._update_info = info
        self._update_btn.configure(text=f"Update {info.tag} \u2193")
        self._update_btn.grid()   # make visible
        self._log.append(
            f"Neue Version verfuegbar: {info.tag}  "
            f"-- Klick auf 'Update {info.tag}' zum Aktualisieren."
        )

    def _on_update_click(self) -> None:
        """User clicked the update button -- download and restart."""
        if not self._update_info:
            return
        info = self._update_info
        self._update_btn.configure(state="disabled", text="Wird geladen...")
        self._log.append(f"Update auf {info.tag} wird gestartet...")

        def safe_log(msg: str) -> None:
            if self._alive:
                try:
                    self.after(0, lambda m=msg: self._log.append(m))
                except Exception:
                    pass

        def do_update() -> None:
            from app.updater import UpdateChecker
            UpdateChecker(REPO, VERSION).download_and_apply(info, safe_log)

        threading.Thread(target=do_update, daemon=True).start()


    def _get_icon_path(self) -> str | None:
        icon_name = "image.ico"
        candidates = []
        if hasattr(sys, "_MEIPASS"):
            candidates.append(os.path.join(sys._MEIPASS, icon_name))
        base = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.path.dirname(sys.executable)
        # Walk up to project root
        for _ in range(4):
            candidates.append(os.path.join(base, icon_name))
            base = os.path.dirname(base)
        candidates.append(os.path.join(os.path.expanduser("~"), "Downloads", icon_name))
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def _load_icon(self) -> None:
        path = self._get_icon_path()
        if path:
            try:
                self.iconbitmap(path)
            except Exception:
                pass

    def _on_minimize(self, event) -> None:
        if str(event.widget) == str(self):
            try:
                import pystray
                from PIL import Image
                self.withdraw()  # hide the window
                icon_path = self._get_icon_path()
                if icon_path:
                    image = Image.open(icon_path)
                else:
                    image = Image.new('RGB', (64, 64), color=(73, 109, 137))
                
                menu = pystray.Menu(
                    pystray.MenuItem('Anzeigen', self._tray_show),
                    pystray.MenuItem('Stop', lambda: self.after(0, self._on_stop)),
                    pystray.MenuItem('Beenden', self._tray_quit)
                )
                self._tray_icon = pystray.Icon("AutoClickTimer", image, "AutoClickTimer", menu)
                threading.Thread(target=self._tray_icon.run, daemon=True).start()
            except ImportError:
                pass

    def _tray_show(self, icon, item) -> None:
        if self._tray_icon:
            self._tray_icon.stop()
            self._tray_icon = None
        self.after(0, self.deiconify)

    def _tray_quit(self, icon, item) -> None:
        if self._tray_icon:
            self._tray_icon.stop()
            self._tray_icon = None
        self.after(0, self._on_close)

    def _on_close(self) -> None:
        self._alive = False       # stop executor callbacks from posting to after()
        self._executor.stop()     # signal worker thread to exit
        self.withdraw()           # hide the window immediately (feels instant)
        # CustomTkinter spawns a non-daemon darkdetect thread that blocks
        # normal Python shutdown. os._exit(0) terminates the process directly,
        # bypassing thread join -- safe for a GUI utility with no open files.
        import os
        os._exit(0)

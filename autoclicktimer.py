#!/usr/bin/env python3
# AutoClick Timer – Modern CustomTkinter Split-Pane UI with Segmented Selector & Presets.
import sys, subprocess, os, time, datetime, threading

def ensure_deps():
    for pkg in ["pyautogui", "pyperclip", "customtkinter"]:
        try:
            __import__(pkg)
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

ensure_deps()

def is_admin():
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

def elevate():
    import ctypes
    if not is_admin():
        try:
            # Relaunch with admin privileges
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
            sys.exit(0)
        except Exception:
            pass

elevate()

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import pyautogui
import pyperclip

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

# Color tokens – Modern Teal Theme
BG_COLOR      = "#0f0f10"
SURFACE       = "#16161a"
SURFACE_L     = "#202026"
SURFACE_H     = "#2a2a33"
OUTLINE       = "#3f3f4c"
PRIMARY       = "#4891A1"
PRIMARY_HOV   = "#3a7683"
ON_SURF       = "#e8e8ea"
ON_SURF_M     = "#8b8b99"
ERROR         = "#f87171"
SUCCESS       = "#4ade80"

def fmt(s):
    return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"

def fmt_short(s):
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    parts = []
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if sec: parts.append(f"{sec}s")
    return " ".join(parts) if parts else "0s"

class Item:
    def __init__(self, total, action, prompt="", label=""):
        self.total  = total
        self.action = action
        self.prompt = prompt
        self.label  = label or {"enter":"Enter drücken","click":"Linksklick","type":"Prompt senden","sleep":"Sleep & Wake"}[action]
        self.status = "waiting"
        self.rem    = total

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AutoClick Timer")
        self.geometry("940x720")
        self.minsize(380, 560)
        
        self.configure(fg_color=BG_COLOR)
        
        # Load window icon if available
        import os
        icon_name = "image.ico"
        icon_path = ""
        if hasattr(sys, "_MEIPASS"):
            icon_path = os.path.join(sys._MEIPASS, icon_name)
        if not icon_path or not os.path.exists(icon_path):
            base_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in locals() else os.path.dirname(sys.executable)
            icon_path = os.path.join(base_dir, icon_name)
        if not os.path.exists(icon_path):
            # Fallback to current user's Downloads folder
            icon_path = os.path.join(os.path.expanduser("~"), "Downloads", icon_name)
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass
        
        # State variables
        self.queue   = []
        self.running = False
        self.stop_ev = threading.Event()
        self._q_rows = []
        
        self._mode   = tk.StringVar(value="duration")   # "duration" | "clock"
        self._sv_act = tk.StringVar(value="enter")
        
        self._sv_h = tk.StringVar(value="0")
        self._sv_m = tk.StringVar(value="0")
        self._sv_s = tk.StringVar(value="0")
        
        now = datetime.datetime.now()
        self._clk_h = tk.StringVar(value=str(now.hour))
        self._clk_m = tk.StringVar(value=str(now.minute))
        self._clk_s = tk.StringVar(value="0")
        self._sv_lbl = tk.StringVar()
        
        self._is_slim_layout = False
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._close)
        
        # Bind configure for responsive layout
        self.bind("<Configure>", self._on_resize)

    def _build_ui(self):
        # Main grid: row 0 = header, row 1 = panels
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Header
        self.hdr = ctk.CTkFrame(self, fg_color="transparent")
        self.hdr.grid(row=0, column=0, columnspan=2, sticky="ew", padx=24, pady=(18, 6))
        self.hdr.grid_columnconfigure(0, weight=0)
        self.hdr.grid_columnconfigure(1, weight=1)

        self.title_lbl = ctk.CTkLabel(self.hdr, text="AutoClick Timer", font=("Segoe UI", 20, "bold"), text_color=ON_SURF)
        self.title_lbl.grid(row=0, column=0, sticky="w")

        self.failsafe_lbl = ctk.CTkLabel(self.hdr, text="Notfall-Stop: Maus ganz oben-links in die Bildschirmecke schieben",
                                         font=("Segoe UI", 10, "bold"), text_color=ERROR, wraplength=400, justify="right")
        self.failsafe_lbl.grid(row=0, column=1, sticky="e")

        # Left Panel (Form + Presets + Log)
        self.left_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.left_panel.grid(row=1, column=0, sticky="nsew", padx=(20, 10), pady=(10, 16))
        self.left_panel.grid_columnconfigure(0, weight=1)
        # row 0 = form card (fixed), row 1 = presets card (fixed), row 2 = log (expands)
        self.left_panel.grid_rowconfigure(0, weight=0)
        self.left_panel.grid_rowconfigure(1, weight=0)
        self.left_panel.grid_rowconfigure(2, weight=1)

        self._build_form(self.left_panel)
        self._build_presets(self.left_panel)
        self._build_log(self.left_panel)

        # Right Panel (Queue + Controls)
        self.right_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.right_panel.grid(row=1, column=1, sticky="nsew", padx=(10, 20), pady=(10, 16))
        self.right_panel.grid_columnconfigure(0, weight=1)
        # row 0 = queue label+scrollable (expands), row 1 = controls (fixed)
        self.right_panel.grid_rowconfigure(0, weight=1)
        self.right_panel.grid_rowconfigure(1, weight=0)

        self._build_queue_area(self.right_panel)
        self._build_controls(self.right_panel)

        # Initial layout
        self.update_idletasks()
        self._apply_layout(self.winfo_width() < 720)

    def _on_resize(self, event):
        if str(event.widget) != str(self):
            return
        is_slim = event.width < 720
        if self._is_slim_layout != is_slim:
            self._is_slim_layout = is_slim
            self._apply_layout(is_slim)

    def _apply_layout(self, is_slim):
        if is_slim:
            # Slim: single column, panels stacked vertically
            # Row 1 = left panel (fixed height, all content), Row 2 = right panel (expands for queue)
            self.grid_rowconfigure(1, weight=0)  # left panel does not expand
            self.grid_rowconfigure(2, weight=1)  # right panel (queue) expands
            self.grid_columnconfigure(0, weight=1, minsize=0)
            self.grid_columnconfigure(1, weight=0, minsize=0)

            self.hdr.grid_configure(columnspan=1)
            self.title_lbl.grid_configure(row=0, column=0, sticky="w")
            self.failsafe_lbl.grid_configure(row=1, column=0, sticky="w", pady=(2, 0))

            self.left_panel.grid_configure(row=1, column=0, columnspan=1, sticky="nsew", padx=16, pady=(10, 6))
            self.right_panel.grid_configure(row=2, column=0, columnspan=1, sticky="nsew", padx=16, pady=(6, 16))

            # In slim mode, log in left panel should NOT expand (just show label)
            self.left_panel.grid_rowconfigure(2, weight=0)

            # Controls: 2x2 grid
            self._start_btn.grid_configure(row=0, column=0, padx=2, pady=2, sticky="ew")
            self._stop_btn.grid_configure(row=0, column=1, padx=2, pady=2, sticky="ew")
            self._reset_btn.grid_configure(row=1, column=0, padx=2, pady=2, sticky="ew")
            self._clear_btn.grid_configure(row=1, column=1, padx=2, pady=2, sticky="ew")
            self._stat.grid_configure(row=2, column=0, columnspan=2, pady=(4, 0), sticky="w")
            self.controls_bar.grid_columnconfigure((0, 1), weight=1)
            self.controls_bar.grid_columnconfigure((2, 3, 4), weight=0)
        else:
            # Wide: two columns side by side, both expand equally
            self.grid_rowconfigure(1, weight=1)
            self.grid_rowconfigure(2, weight=0)
            self.grid_columnconfigure(0, weight=1, minsize=360)
            self.grid_columnconfigure(1, weight=1, minsize=280)

            self.hdr.grid_configure(columnspan=2)
            self.title_lbl.grid_configure(row=0, column=0, sticky="w")
            self.failsafe_lbl.grid_configure(row=0, column=1, sticky="e", pady=0)

            self.left_panel.grid_configure(row=1, column=0, columnspan=1, sticky="nsew", padx=(20, 10), pady=(10, 16))
            self.right_panel.grid_configure(row=1, column=1, columnspan=1, sticky="nsew", padx=(10, 20), pady=(10, 16))

            # In wide mode, log in left panel expands to fill remaining space
            self.left_panel.grid_rowconfigure(2, weight=1)

            # Controls: horizontal row
            self._start_btn.grid_configure(row=0, column=0, padx=(0, 8), pady=0, sticky="ew")
            self._stop_btn.grid_configure(row=0, column=1, padx=(0, 8), pady=0, sticky="ew")
            self._reset_btn.grid_configure(row=0, column=2, padx=(0, 8), pady=0, sticky="ew")
            self._clear_btn.grid_configure(row=0, column=3, padx=0, pady=0, sticky="ew")
            self._stat.grid_configure(row=0, column=4, padx=(8, 0), pady=0, sticky="e")
            self.controls_bar.grid_columnconfigure((0, 1, 2, 3), weight=1)
            self.controls_bar.grid_columnconfigure(4, weight=0)

    def _build_form(self, parent):
        card = ctk.CTkFrame(parent, fg_color=SURFACE, border_width=1, border_color=OUTLINE, corner_radius=12)
        card.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        card.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        # Mode selector
        mode_frame = ctk.CTkFrame(card, fg_color="transparent")
        mode_frame.grid(row=0, column=0, columnspan=4, sticky="w", padx=16, pady=(12, 6))
        
        ctk.CTkLabel(mode_frame, text="Modus:", font=("Segoe UI", 11, "bold"), text_color=ON_SURF_M).pack(side="left", padx=(0, 12))
        
        rb_dur = ctk.CTkRadioButton(mode_frame, text="⏱ Timer (Dauer)", variable=self._mode, value="duration",
                                    command=self._on_mode, fg_color=PRIMARY, hover_color=PRIMARY_HOV, text_color=ON_SURF, font=("Segoe UI", 11))
        rb_dur.pack(side="left", padx=(0, 16))
        
        rb_clk = ctk.CTkRadioButton(mode_frame, text="Uhrzeit", variable=self._mode, value="clock",
                                    command=self._on_mode, fg_color=PRIMARY, hover_color=PRIMARY_HOV, text_color=ON_SURF, font=("Segoe UI", 11))
        rb_clk.pack(side="left")
        
        # Inputs frame (dynamic switching)
        self.inputs_frame = ctk.CTkFrame(card, fg_color="transparent")
        self.inputs_frame.grid(row=1, column=0, columnspan=4, sticky="ew", padx=16, pady=6)
        self.inputs_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        self._render_inputs()
        
        # Action selector (Segmented Button for modern look)
        act_frame = ctk.CTkFrame(card, fg_color="transparent")
        act_frame.grid(row=2, column=0, columnspan=4, sticky="ew", padx=16, pady=6)
        
        ctk.CTkLabel(act_frame, text="Aktion", font=("Segoe UI", 10), text_color=ON_SURF_M).pack(anchor="w", pady=(0, 4))
        
        self.act_seg = ctk.CTkSegmentedButton(act_frame, values=["Enter", "Linksklick", "Prompt senden", "Sleep & Wake"],
                                              command=self._on_act_segmented, fg_color=SURFACE_L, selected_color=PRIMARY,
                                              selected_hover_color=PRIMARY_HOV, text_color=ON_SURF, unselected_color=SURFACE_L,
                                              unselected_hover_color=SURFACE_H, font=("Segoe UI", 11))
        self.act_seg.pack(fill="x")
        self.act_seg.set("Enter")
        
        # Prompt text area (initially hidden)
        self._pf = ctk.CTkFrame(card, fg_color="transparent")
        self._pf.grid(row=3, column=0, columnspan=4, sticky="ew", padx=16, pady=6)
        self._pf.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self._pf, text="Prompt-Text (eingefügt + Enter gesendet)", font=("Segoe UI", 10), text_color=ON_SURF_M).grid(row=0, column=0, sticky="w", pady=(0, 2))
        self._pt = ctk.CTkTextbox(self._pf, height=60, fg_color=SURFACE_L, border_color=OUTLINE, border_width=1, text_color=ON_SURF)
        self._pt.grid(row=1, column=0, sticky="ew")
        self._pf.grid_remove()
        
        # Designation (Label) and Add Button
        lf = ctk.CTkFrame(card, fg_color="transparent")
        lf.grid(row=4, column=0, columnspan=4, sticky="ew", padx=16, pady=(6, 12))
        lf.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(lf, text="Bezeichnung:", font=("Segoe UI", 10), text_color=ON_SURF_M).grid(row=0, column=0, sticky="w", padx=(0, 10))
        ctk.CTkEntry(lf, textvariable=self._sv_lbl, fg_color=SURFACE_L, border_color=OUTLINE, text_color=ON_SURF, width=120).grid(row=0, column=1, sticky="ew", padx=(0, 12))
        
        add_btn = ctk.CTkButton(lf, text="+ Zur Warteschlange", command=self._add, fg_color=PRIMARY, hover_color=PRIMARY_HOV, text_color="white", width=140, font=("Segoe UI", 11, "bold"), corner_radius=8)
        add_btn.grid(row=0, column=2, sticky="e")

    def _render_inputs(self):
        for w in self.inputs_frame.winfo_children():
            w.destroy()
            
        if self._mode.get() == "duration":
            for col, (lbl, var) in enumerate([("Stunden", self._sv_h), ("Minuten", self._sv_m), ("Sekunden", self._sv_s)]):
                f = ctk.CTkFrame(self.inputs_frame, fg_color="transparent")
                f.grid(row=0, column=col, sticky="ew", padx=(0, 8))
                ctk.CTkLabel(f, text=lbl, font=("Segoe UI", 10), text_color=ON_SURF_M).pack(anchor="w", pady=(0, 2))
                ctk.CTkEntry(f, textvariable=var, fg_color=SURFACE_L, border_color=OUTLINE, text_color=ON_SURF, justify="center", font=("Segoe UI", 12, "bold"), width=60).pack(fill="x")
            pr_row = 1
        else:
            for col, (lbl, var) in enumerate([("Stunde", self._clk_h), ("Minute", self._clk_m), ("Sekunde", self._clk_s)]):
                f = ctk.CTkFrame(self.inputs_frame, fg_color="transparent")
                f.grid(row=0, column=col, sticky="ew", padx=(0, 8))
                ctk.CTkLabel(f, text=lbl, font=("Segoe UI", 10), text_color=ON_SURF_M).pack(anchor="w", pady=(0, 2))
                entry = ctk.CTkEntry(f, textvariable=var, fg_color=SURFACE_L, border_color=OUTLINE, text_color=ON_SURF, justify="center", font=("Segoe UI", 12, "bold"), width=60)
                entry.pack(fill="x")
                var.trace_add("write", self._update_clock_preview)
            
            self._clk_preview = ctk.CTkLabel(self.inputs_frame, text="", font=("Segoe UI", 10), text_color=PRIMARY)
            self._clk_preview.grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))
            self._update_clock_preview()
            pr_row = 2

        # Time presets frame for both modes
        presets_f = ctk.CTkFrame(self.inputs_frame, fg_color="transparent")
        presets_f.grid(row=pr_row, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        presets_f.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=1)
        
        presets = [
            (15, "m", "15m"), (30, "m", "30m"), (1, "h", "1h"), (2, "h", "2h"), (3, "h", "3h"), (4, "h", "4h"),
            (5, "h", "5h"), (6, "h", "6h"), (8, "h", "8h"), (10, "h", "10h"), (12, "h", "12h"), (24, "h", "24h")
        ]
        
        for idx, (amount, unit, lbl) in enumerate(presets):
            r = idx // 6
            c = idx % 6
            btn = ctk.CTkButton(presets_f, text=lbl, command=lambda a=amount, u=unit: self._set_time_preset(a, u),
                                fg_color=SURFACE_L, hover_color=PRIMARY_HOV, border_width=1, border_color=OUTLINE,
                                text_color=ON_SURF, height=24, font=("Segoe UI", 10))
            btn.grid(row=r, column=c, padx=2, pady=2, sticky="ew")

    def _set_time_preset(self, amount, unit="h"):
        if self._mode.get() == "duration":
            if unit == "h":
                self._sv_h.set(str(amount))
                self._sv_m.set("0")
                self._sv_s.set("0")
            elif unit == "m":
                self._sv_h.set("0")
                self._sv_m.set(str(amount))
                self._sv_s.set("0")
        else:
            # Clock mode: calculate target time
            now = datetime.datetime.now()
            if unit == "h":
                target = now + datetime.timedelta(hours=amount)
            elif unit == "m":
                target = now + datetime.timedelta(minutes=amount)
            self._clk_h.set(str(target.hour))
            self._clk_m.set(str(target.minute))
            self._clk_s.set(str(target.second))
            self._update_clock_preview()

    def _on_mode(self):
        self._render_inputs()

    def _update_clock_preview(self, *_):
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
                text=f"→ in {fmt_short(delta)} (um {target.strftime('%H:%M:%S')})"
            )
        except Exception:
            if hasattr(self, "_clk_preview"):
                self._clk_preview.configure(text="")

    def _on_act_segmented(self, choice):
        if choice == "Prompt senden":
            self._pf.grid()
        else:
            self._pf.grid_remove()

    def _build_presets(self, parent):
        card = ctk.CTkFrame(parent, fg_color=SURFACE, border_width=1, border_color=OUTLINE, corner_radius=12)
        card.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        card.grid_columnconfigure((0, 1), weight=1)
        
        ctk.CTkLabel(card, text="PRESETS (Zeit oben eintragen)", font=("Segoe UI", 11, "bold"), text_color=ON_SURF_M).grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(10, 4))
        
        p1_btn = ctk.CTkButton(card, text="Sleep & Wake + Enter", command=self._preset_sleep_enter, fg_color=SURFACE_L, hover_color=PRIMARY_HOV, border_width=1, border_color=OUTLINE, text_color=ON_SURF, font=("Segoe UI", 11))
        p1_btn.grid(row=1, column=0, padx=(16, 6), pady=(0, 12), sticky="ew")
        
        p2_btn = ctk.CTkButton(card, text="Sleep & Wake + Klick", command=self._preset_sleep_click, fg_color=SURFACE_L, hover_color=PRIMARY_HOV, border_width=1, border_color=OUTLINE, text_color=ON_SURF, font=("Segoe UI", 11))
        p2_btn.grid(row=1, column=1, padx=(6, 16), pady=(0, 12), sticky="ew")

    def _preset_sleep_enter(self):
        self._add_preset_combination("enter")

    def _preset_sleep_click(self):
        self._add_preset_combination("click")

    def _add_preset_combination(self, post_action):
        if self._mode.get() == "duration":
            try:
                h = int(self._sv_h.get() or 0)
                m = int(self._sv_m.get() or 0)
                s = int(self._sv_s.get() or 0)
            except ValueError:
                messagebox.showerror("Fehler", "Ungültige Zeit."); return
            total = h*3600 + m*60 + s
            if total <= 0:
                messagebox.showerror("Fehler", "Zeit > 0 erforderlich."); return
        else:
            try:
                h = int(self._clk_h.get() or 0)
                m = int(self._clk_m.get() or 0)
                s = int(self._clk_s.get() or 0)
            except ValueError:
                messagebox.showerror("Fehler", "Ungültige Uhrzeit."); return
            now    = datetime.datetime.now()
            target = now.replace(hour=h, minute=m, second=s, microsecond=0)
            if target <= now:
                target += datetime.timedelta(days=1)
            total  = int((target - now).total_seconds())
            if total <= 0:
                messagebox.showerror("Fehler", "Zielzeit liegt in der Vergangenheit."); return

        if not is_admin():
            messagebox.showerror("Administrator", "Die Aktion 'sleep & wake' erfordert Administratorrechte. Bitte starten Sie die Anwendung als Administrator neu.")
            return

        # Add Sleep & Wake action
        sleep_item = Item(total, "sleep", label="Ruhezustand")
        self.queue.append(sleep_item)
        self._log_line(f"+ [Ruhezustand] {fmt(total)}")

        # Add Post Action (delay 2 seconds)
        post_label = "Enter-Taste nach Aufwachen" if post_action == "enter" else "Linksklick nach Aufwachen"
        post_item = Item(2, post_action, label=post_label)
        self.queue.append(post_item)
        self._log_line(f"+ [{post_label}] {fmt(2)}")

        # Reset time input fields and render
        self._sv_lbl.set("")
        self._render()

    def _build_queue_area(self, parent):
        outer = ctk.CTkFrame(parent, fg_color="transparent")
        outer.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        outer.grid_rowconfigure(0, weight=0)
        outer.grid_rowconfigure(1, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(outer, text="WARTESCHLANGE", font=("Segoe UI", 10, "bold"), text_color=ON_SURF_M).grid(row=0, column=0, sticky="w", pady=(0, 4))

        self.queue_frame = ctk.CTkScrollableFrame(outer, fg_color=SURFACE, border_width=1, border_color=OUTLINE, corner_radius=12)
        self.queue_frame.grid(row=1, column=0, sticky="nsew")
        self.queue_frame.grid_columnconfigure(0, weight=1)

        self._empty = ctk.CTkLabel(self.queue_frame, text="Noch keine Aktionen — füge deine erste oben hinzu.", font=("Segoe UI", 11), text_color=ON_SURF_M)
        self._empty.pack(pady=32)

    def _build_controls(self, parent):
        self.controls_bar = ctk.CTkFrame(parent, fg_color="transparent")
        self.controls_bar.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        self.controls_bar.grid_columnconfigure(4, weight=1)
        
        self._start_btn = ctk.CTkButton(self.controls_bar, text="▶  Starten", command=self._start, fg_color=PRIMARY, hover_color=PRIMARY_HOV, text_color="white", width=100, font=("Segoe UI", 11, "bold"), corner_radius=8)
        self._start_btn.grid(row=0, column=0, padx=(0, 8))
        
        self._stop_btn = ctk.CTkButton(self.controls_bar, text="⏹ Stop", command=self._stop, fg_color=SURFACE, border_width=1, border_color=OUTLINE, hover_color=SURFACE_H, text_color=ON_SURF, width=80, font=("Segoe UI", 11), corner_radius=8)
        self._stop_btn.grid(row=0, column=1, padx=(0, 8))
        
        self._reset_btn = ctk.CTkButton(self.controls_bar, text="↺ Reset", command=self._reset, fg_color=SURFACE, border_width=1, border_color=OUTLINE, hover_color=SURFACE_H, text_color=ON_SURF, width=80, font=("Segoe UI", 11), corner_radius=8)
        self._reset_btn.grid(row=0, column=2, padx=(0, 8))
        
        self._clear_btn = ctk.CTkButton(self.controls_bar, text="🗑 Leeren", command=self._clear, fg_color=SURFACE, border_width=1, border_color=OUTLINE, hover_color="#2e1414", text_color=ERROR, width=80, font=("Segoe UI", 11), corner_radius=8)
        self._clear_btn.grid(row=0, column=3)
        
        self._stat = ctk.CTkLabel(self.controls_bar, text="", font=("Segoe UI", 11), text_color=ON_SURF_M)
        self._stat.grid(row=0, column=4, sticky="e")

    def _build_log(self, parent):
        lf = ctk.CTkFrame(parent, fg_color="transparent")
        lf.grid(row=2, column=0, sticky="nsew", pady=(0, 0))
        lf.grid_columnconfigure(0, weight=1)
        lf.grid_rowconfigure(0, weight=0)
        lf.grid_rowconfigure(1, weight=1)  # Textbox expands to fill available space

        ctk.CTkLabel(lf, text="LOG", font=("Segoe UI", 10, "bold"), text_color=ON_SURF_M).grid(row=0, column=0, sticky="w", pady=(0, 4))

        self._log = ctk.CTkTextbox(lf, fg_color=SURFACE, border_width=1, border_color=OUTLINE,
                                   font=("Consolas", 9), text_color=ON_SURF_M, height=120)
        self._log.grid(row=1, column=0, sticky="nsew")
        self._log.configure(state="disabled")

    def _add(self):
        if self._mode.get() == "duration":
            try:
                h = int(self._sv_h.get() or 0)
                m = int(self._sv_m.get() or 0)
                s = int(self._sv_s.get() or 0)
            except ValueError:
                messagebox.showerror("Fehler", "Ungültige Zeit."); return
            total = h*3600 + m*60 + s
            if total <= 0:
                messagebox.showerror("Fehler", "Zeit > 0 erforderlich."); return
        else:
            try:
                h = int(self._clk_h.get() or 0)
                m = int(self._clk_m.get() or 0)
                s = int(self._clk_s.get() or 0)
            except ValueError:
                messagebox.showerror("Fehler", "Ungültige Uhrzeit."); return
            now    = datetime.datetime.now()
            target = now.replace(hour=h, minute=m, second=s, microsecond=0)
            if target <= now:
                target += datetime.timedelta(days=1)
            total  = int((target - now).total_seconds())
            if total <= 0:
                messagebox.showerror("Fehler", "Zielzeit liegt in der Vergangenheit."); return

        choice = self.act_seg.get()
        action_map = {
            "Enter": "enter",
            "Linksklick": "click",
            "Prompt senden": "type",
            "Sleep & Wake": "sleep"
        }
        act = action_map.get(choice, "enter")

        if act == "sleep" and not is_admin():
            messagebox.showerror("Administrator", "Die Aktion 'sleep & wake' erfordert Administratorrechte. Bitte starten Sie die Anwendung als Administrator neu.")
            return
        prompt = self._pt.get("1.0", "end-1c").strip() if act == "type" else ""
        if act == "type" and not prompt:
            messagebox.showerror("Fehler", "Prompt-Text fehlt."); return

        item = Item(total, act, prompt, self._sv_lbl.get().strip())
        self.queue.append(item)
        self._sv_lbl.set("")
        self._pt.delete("1.0", tk.END)
        self._render()
        self._log_line(f"+ [{item.label}] {fmt(total)}")

    def _remove(self, item):
        if self.running: return
        self.queue.remove(item)
        self._render()

    def _clear(self):
        if self.running: self._stop()
        self.queue.clear()
        self._render()
        self._stat_set("")
        self._log_line("🗑 Warteschlange geleert.")

    def _render(self):
        for w in self.queue_frame.winfo_children():
            if w is not self._empty:
                w.destroy()
        self._q_rows.clear()
        if not self.queue:
            self._empty.pack(pady=32)
            return
        self._empty.pack_forget()
        
        for i, item in enumerate(self.queue):
            is_run  = item.status == "running"
            is_done = item.status == "done"
            bc = PRIMARY if is_run else (SUCCESS if is_done else OUTLINE)
            
            row = ctk.CTkFrame(self.queue_frame, fg_color=SURFACE_L, border_width=1, border_color=bc, corner_radius=10)
            row.pack(fill="x", pady=(0, 6), padx=4)
            row.grid_columnconfigure(1, weight=1)
            
            # number badge
            nb = PRIMARY if is_run else (SUCCESS if is_done else SURFACE_H)
            nf = "#fff" if (is_run or is_done) else ON_SURF_M
            badge = ctk.CTkLabel(row, text=str(i+1), fg_color=nb, text_color=nf, font=("Segoe UI", 10, "bold"), width=24, height=24, corner_radius=12)
            badge.grid(row=0, column=0, rowspan=2, padx=(10, 6), pady=10, sticky="n")
            
            # info
            info = ctk.CTkFrame(row, fg_color="transparent")
            info.grid(row=0, column=1, sticky="w", pady=10)
            ctk.CTkLabel(info, text=item.label, font=("Segoe UI", 11, "bold"), text_color=ON_SURF).pack(anchor="w")
            meta = f"{fmt(item.total)} · {item.action}"
            if item.action == "type" and item.prompt:
                meta += f' · "{item.prompt[:40]}{"…" if len(item.prompt)>40 else ""}"'
            ctk.CTkLabel(info, text=meta, font=("Segoe UI", 10), text_color=ON_SURF_M).pack(anchor="w")
            
            # right side
            right = ctk.CTkFrame(row, fg_color="transparent")
            right.grid(row=0, column=2, padx=12, pady=10, sticky="e")
            sc  = PRIMARY if is_run else (SUCCESS if is_done else ON_SURF_M)
            st  = "● Läuft" if is_run else ("✓ Fertig" if is_done else "Wartet")
            ctk.CTkLabel(right, text=st, text_color=sc, font=("Segoe UI", 10)).pack(anchor="e")
            
            cdfg = SUCCESS if is_done else (PRIMARY if is_run else ON_SURF_M)
            cdtx = "✓ Fertig" if is_done else fmt(item.rem)
            cd   = ctk.CTkLabel(right, text=cdtx, text_color=cdfg, font=("Segoe UI", 15, "bold"))
            cd.pack(anchor="e")
            
            if not self.running:
                del_btn = ctk.CTkButton(row, text="✕", width=24, height=24, fg_color="transparent", text_color=ON_SURF_M, hover_color="#2e1414", corner_radius=6)
                del_btn.configure(command=lambda it=item: self._remove(it))
                del_btn.grid(row=0, column=3, padx=10, pady=10)
            
            # progress bar
            prog = ctk.CTkProgressBar(row, height=4, progress_color=PRIMARY if not is_done else SUCCESS, trough_color=SURFACE_H)
            prog.set(1.0 if is_done else (item.total - item.rem) / max(1, item.total))
            prog.grid(row=2, column=0, columnspan=4, sticky="ew", padx=10, pady=(0, 8))
            
            self._q_rows.append((item, row, cd, prog))

    def _update_row(self, item):
        for it, row, cd, prog in self._q_rows:
            if it is item:
                cd.configure(text=fmt(item.rem), text_color=PRIMARY)
                prog.set((item.total - item.rem) / max(1, item.total))
                break

    def _start(self):
        if self.running or not self.queue: return
        for it in self.queue: it.status = "waiting"; it.rem = it.total
        self.running = True
        self.stop_ev.clear()
        self._start_btn.configure(state="disabled")
        self._render()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            for i, item in enumerate(self.queue):
                if self.stop_ev.is_set(): break
                item.status = "running"
                self.after(0, self._render)
                self._log_line(f"⏳ Schritt {i+1}/{len(self.queue)}: [{item.label}] — {fmt(item.total)}")
                self._stat_set(f"Schritt {i+1}/{len(self.queue)} läuft…")
                
                if item.action == "sleep":
                    self._log_line("  → Bereite Sleep & Wake vor und versetze PC in den Ruhezustand...")
                    self._prepare_and_sleep(item.total)
                    
                t0 = time.time()
                while True:
                    if self.stop_ev.is_set(): break
                    elapsed   = time.time() - t0
                    item.rem  = max(0, item.total - int(elapsed))
                    self.after(0, lambda it=item: self._update_row(it))
                    if elapsed >= item.total: break
                    time.sleep(0.4)
                if self.stop_ev.is_set(): break
                item.rem = 0
                self._do_action(item)
                item.status = "done"
                self.after(0, self._render)
                self._log_line(f"✓ Schritt {i+1} fertig")
        except pyautogui.FailSafeException:
            pass # Already handled in _do_action
        self.running = False
        if not self.stop_ev.is_set():
            self._log_line(f"✅ Alle {len(self.queue)} Aktionen abgeschlossen!")
            self._stat_set("Fertig!")
        self.after(0, lambda: self._start_btn.configure(state="normal"))

    def _prepare_and_sleep(self, duration_seconds):
        try:
            import base64
            wake_time = datetime.datetime.now() + datetime.timedelta(seconds=duration_seconds)
            wake_time_str = wake_time.strftime("%Y-%m-%dT%H:%M:%S")

            # 1. Enable wake timers
            subprocess.run(["powercfg", "/SETACVALUEINDEX", "SCHEME_CURRENT", "SUB_SLEEP", "RTCWAKE", "1"], capture_output=True)
            subprocess.run(["powercfg", "/SETDCVALUEINDEX", "SCHEME_CURRENT", "SUB_SLEEP", "RTCWAKE", "1"], capture_output=True)

            # 2. Set unattended sleep timeout to 0 (Never)
            subprocess.run(["powercfg", "/SETACVALUEINDEX", "SCHEME_CURRENT", "SUB_SLEEP", "7bc4a2f9-d8fc-4469-b07b-33eb785aaca0", "0"], capture_output=True)
            subprocess.run(["powercfg", "/SETDCVALUEINDEX", "SCHEME_CURRENT", "SUB_SLEEP", "7bc4a2f9-d8fc-4469-b07b-33eb785aaca0", "0"], capture_output=True)

            # 3. Disable console lock
            subprocess.run(["powercfg", "/SETACVALUEINDEX", "SCHEME_CURRENT", "SUB_NONE", "CONSOLELOCK", "0"], capture_output=True)
            subprocess.run(["powercfg", "/SETDCVALUEINDEX", "SCHEME_CURRENT", "SUB_NONE", "CONSOLELOCK", "0"], capture_output=True)

            # Apply settings
            subprocess.run(["powercfg", "/SETACTIVE", "SCHEME_CURRENT"], capture_output=True)

            # 4. Remove existing task if any
            task_name = "SleepWakeTask"
            subprocess.run(["schtasks", "/Delete", "/TN", task_name, "/F"], capture_output=True)

            # 5. Register the scheduled task to wake and unlock
            ps_command = (
                f"$sessionId = (Get-Process -Name explorer -ErrorAction SilentlyContinue | Select-Object -First 1).SessionId; "
                f"if ($sessionId) {{ tscon $sessionId /dest:console }}; "
                f"Unregister-ScheduledTask -TaskName '{task_name}' -Confirm:$false"
            )
            ps_bytes = ps_command.encode('utf-16le')
            ps_b64 = base64.b64encode(ps_bytes).decode('ascii')

            register_script = (
                f"$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-NoProfile -WindowStyle Hidden -EncodedCommand {ps_b64}'; "
                f"$trigger = New-ScheduledTaskTrigger -Once -At '{wake_time_str}'; "
                f"$settings = New-ScheduledTaskSettingsSet -WakeToRun -AllowStartIfOnBatteries; "
                f"Register-ScheduledTask -TaskName '{task_name}' -Action $action -Trigger $trigger -Settings $settings -User 'NT AUTHORITY\\SYSTEM'"
            )
            reg_bytes = register_script.encode('utf-16le')
            reg_b64 = base64.b64encode(reg_bytes).decode('ascii')

            subprocess.run(["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-EncodedCommand", reg_b64], capture_output=True)

            # 6. Put the PC to sleep
            sleep_script = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "[System.Windows.Forms.Application]::SetSuspendState([System.Windows.Forms.PowerState]::Suspend, $false, $false)"
            )
            sleep_bytes = sleep_script.encode('utf-16le')
            sleep_b64 = base64.b64encode(sleep_bytes).decode('ascii')

            time.sleep(1)
            subprocess.Popen(["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-EncodedCommand", sleep_b64])
        except Exception as e:
            self._log_line(f"  ⚠ Fehler beim Einschlafen: {e}")

    def _do_action(self, item):
        try:
            time.sleep(0.2)
            if item.action == "enter":
                pyautogui.press("enter")
            elif item.action == "click":
                pyautogui.click()
            elif item.action == "type":
                pyperclip.copy(item.prompt)
                time.sleep(0.3)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.35)
                pyautogui.press("enter")
            elif item.action == "sleep":
                pass
            self._log_line(f"  → {item.action} ausgeführt")
        except pyautogui.FailSafeException:
            self._log_line("  ⚠ Notfall-Stop ausgelöst (Maus oben-links)!")
            self.after(0, self._stop)
            raise
        except Exception as e:
            self._log_line(f"  ⚠ Fehler: {e}")

    def _stop(self):
        self.stop_ev.set()
        self.running = False
        self._start_btn.configure(state="normal")
        self._stat_set("Gestoppt.")
        self._log_line("⏹ Gestoppt.")

    def _reset(self):
        if self.running: self._stop()
        for it in self.queue: it.status = "waiting"; it.rem = it.total
        self._render()
        self._stat_set("")
        self._log_line("↺ Zurückgesetzt.")

    def _stat_set(self, msg):
        self.after(0, lambda: self._stat.configure(text=msg))

    def _log_line(self, msg):
        def _do():
            self._log.configure(state="normal")
            self._log.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
            self._log.see("end")
            self._log.configure(state="disabled")
        self.after(0, _do)

    def _close(self):
        self.stop_ev.set()
        self.destroy()

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    app = App()
    app.mainloop()

"""Gisto desktop app — main window, grid popup, settings UI, wiring."""

from __future__ import annotations

import os
import time
import math
import random
import ctypes
import threading
import json
from pathlib import Path
from typing import Any, Callable, Optional

import customtkinter as ctk
from PIL import Image

from src.desktop.settings import AppSettings, load_settings, save_settings
import src.desktop.keys as keys  # type: ignore[import-not-found]


def _assets_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "assets"


class GistoApp(ctk.CTk):
    """Main Gisto window. Normally hides to tray."""

    def __init__(self, settings: AppSettings, settings_path: Path,
                 api_key: str = "", base_url: str = "") -> None:
        super().__init__()

        self._settings = settings
        self.settings_path = settings_path
        self._tray: Any = None
        self._watcher: Any = None
        self._api_key = api_key
        self._api_base = base_url
        self._memory: Any = None
        self._onboarding_complete: bool = False

    @property
    def settings(self) -> AppSettings:
        """Bridge: the rest of the code reads app.settings; we store self._settings."""
        return self._settings

    # ---- memory + onboarding -------------------------------------------
        from src.desktop.wiring import _init_memory

        self._memory_dir = Path(__file__).resolve().parent / ".." / ".gisto" / "memory"
        self._memory_dir = self._memory_dir.resolve()
        _init_memory(self)

        # Grid popup state.
        self._popup_window: Any = None
        self._popup_grid: list[ctk.CTkLabel] = []
        self._popup_visible = False
        self._last_activity: float = 0.0
        self._silence_timer_id: int = 0
        self._pulse_after_id: int = 0
        self._working_after_id: int = 0
        self._popup_callback_ids: list[int] = []
        self._drag_start_x: float = 0.0
        self._drag_start_y: float = 0.0
        self._popup_x: float = 0.0
        self._popup_y: float = 0.0

        self.title("Gisto")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Visibility>", lambda e: self._on_visible())

        self._build_ui()
        self._apply_settings()

    # ------------------------------------------------------------------
    # UI build
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self._cleanup_scale()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Top bar.
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="nw", padx=12, pady=(12, 4))

        logo_path = _assets_dir() / "gisto_logo_full.png"
        self._logo: Any = None
        try:
            if logo_path.exists():
                self._logo = ctk.CTkImage(
                    light_image=Image.open(logo_path),
                    dark_image=Image.open(logo_path),
                    size=(36, 36),
                )
                ctk.CTkLabel(top, image=self._logo, text="").pack(side="left", padx=(0, 8))
        except Exception:
            pass

        ctk.CTkLabel(top, text="Gisto", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")

        self._minimize_btn = ctk.CTkButton(
            top,
            text="Minimize to tray",
            width=130,
            height=26,
            font=ctk.CTkFont(size=12),
            command=self._minimize_to_tray,
        )
        self._minimize_btn.pack(side="right")

        # Center: square grid.
        self._grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._grid_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)
        self._grid_labels: list[ctk.CTkLabel] = []
        self._build_grid()

        # Bottom bar.
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=2, column=0, sticky="sew", padx=12, pady=(0, 12))

        self._status_label = ctk.CTkLabel(
            bottom,
            text="Listening in the background",
            font=ctk.CTkFont(size=12),
            justify="left",
        )
        self._status_label.pack(side="left", fill="x", expand=True)

        self._chat_hint = ctk.CTkLabel(
            bottom,
            text="Type or say the wake word",
            font=ctk.CTkFont(size=11),
            text_color=("#999999", "#666666"),
            justify="right",
        )
        self._chat_hint.pack(side="right", padx=(0, 8))

        self._input = ctk.CTkEntry(
            bottom,
            placeholder_text="Message Gisto...",
            font=ctk.CTkFont(size=13),
        )
        self._input.pack(side="right", fill="x", expand=True, padx=(0, 8))
        self._input.bind("<Return>", self._on_input_enter)

        self._settings_btn = ctk.CTkButton(
            bottom,
            text="Settings",
            width=80,
            height=26,
            font=ctk.CTkFont(size=12),
            command=self._open_settings,
        )
        self._settings_btn.pack(side="right", padx=(0, 8))

    def _cleanup_scale(self) -> None:
        try:
            ctk.set_widget_scaling(1.0)
        except Exception:
            pass

    def _build_grid(self) -> None:
        for lbl in self._grid_labels:
            try:
                lbl.destroy()
            except Exception:
                pass
        self._grid_labels.clear()

        rows = self.settings.grid_rows
        cols = self.settings.grid_cols
        cell = self.settings.grid_cell_size

        for r in range(rows):
            for c in range(cols):
                lbl = ctk.CTkLabel(
                    self._grid_frame,
                    width=cell,
                    height=cell,
                    corner_radius=4,
                    fg_color="#1a1a2e",
                )
                lbl.grid(row=r, column=c, padx=2, pady=2)
                self._grid_labels.append(lbl)

        self._apply_grid_colors()

    def _apply_settings(self) -> None:
        ctk.set_widget_scaling(self.settings.ui_scale)
        self.geometry(f"{self.settings.window_width}x{self.settings.window_height}")
        self._apply_grid_colors()

    def _apply_grid_colors(self) -> None:
        for lbl in self._grid_labels:
            try:
                lbl.configure(fg_color="#1a1a2e")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Tray / window lifecycle
    # ------------------------------------------------------------------

    def set_tray(self, tray: Any) -> None:
        self._tray = tray

    def set_watcher(self, watcher: Any) -> None:
        self._watcher = watcher

    def _on_close(self) -> None:
        self._minimize_to_tray()

    def _on_visible(self) -> None:
        self._reset_silence_timer()

    def _minimize_to_tray(self) -> None:
        self.withdraw()
        try:
            self._tray.show_notification(
                "Gisto is running",
                "Say the wake word or press Ctrl+Alt+G to bring it back.",
            )
        except Exception:
            pass

    def show_main_window(self, reason: str = "manual") -> None:
        if self._popup_visible:
            self._hide_popup()
        self.deiconify()
        try:
            self.lift()
            self.focus_force()
        except Exception:
            pass
        self._reset_silence_timer()
        self._status_label.configure(text=f"Shown: {reason}")

    # ------------------------------------------------------------------
    # Wake / speech / hotkey callbacks
    # ------------------------------------------------------------------

    def on_wake_word(self) -> None:
        self._reset_silence_timer()
        self.show_main_window(reason="wake word")
        self._status_label.configure(text="Gisto heard you")
        self._show_popup_and_pulse("gisto")

    def on_user_speech(self, text: str) -> None:
        self._reset_silence_timer()
        if not self._popup_visible:
            self._show_popup_near_grid()
        self._pulse_popup_grid("user")

    def on_working(self) -> None:
        if not self._popup_visible:
            return
        self._pulse_popup_grid("working")

    def on_hotkey(self) -> None:
        self._reset_silence_timer()
        self.show_main_window(reason="hotkey")
        self._status_label.configure(text="Hotkey triggered")
        self._show_popup_and_pulse("gisto")

    def _show_popup_and_pulse(self, state: str) -> None:
        self._show_popup_near_grid()
        self._pulse_popup_grid(state)

    def _show_reply(self, reply: str) -> None:
        """Show a Solar reply as a transient toast near the popup or screen edge."""
        self._show_reply_toast(reply)

    def _show_reply_toast(self, reply: str) -> None:
        try:
            from tkinter import Toplevel, Label
        except Exception:
            return
        toast = Toplevel(self)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(bg="#1a1a2e", bd=0, highlightthickness=0)
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        if self._popup_visible and self._popup_window and self._popup_window.winfo_exists():
            try:
                gx = int(self._popup_window.geometry().split("+")[-2])
                gy = int(self._popup_window.geometry().split("+")[-1])
                pw = self._popup_window.winfo_width()
                ph = self._popup_window.winfo_height()
                x = gx
                y = gy + ph + 8
            except Exception:
                x = screen_w - 340 - 30
                y = 30
        else:
            x = screen_w - 340 - 30
            y = 30
        toast.geometry(f"+{x}+{y}")
        toast.geometry("320x48")
        lbl = Label(
            toast,
            text=reply,
            bg="#1a1a2e",
            fg="#00e5ff",
            font=("Segoe UI", 11),
            justify="left",
            wraplength=300,
            padx=12,
            pady=8,
        )
        lbl.pack(fill="both", expand=True)
        # Auto-dismiss after 6 seconds.
        toast.after(6000, toast.destroy)

    # ------------------------------------------------------------------
    # Grid popup
    # ------------------------------------------------------------------

    def _show_popup_near_grid(self) -> None:
        if self._popup_visible:
            return
        self._popup_visible = True
        self._last_activity = time.time()

        cell = self.settings.grid_cell_size
        rows = self.settings.grid_rows
        cols = self.settings.grid_cols

        # Transparent popup background so you see through between squares.
        transparent_color = "#000001"
        popup = ctk.CTkToplevel(self)
        popup.title("Gisto")
        popup.attributes("-topmost", True)
        popup.overrideredirect(True)
        popup.config(bg=transparent_color)
        try:
            popup.attributes("-transparentcolor", transparent_color)
        except Exception:
            pass

        gap = 6
        popup_width = cols * cell + (cols - 1) * gap + 2 * gap
        popup_height = rows * cell + (rows - 1) * gap + 2 * gap
        popup.geometry(f"{popup_width}x{popup_height}")

        # Position: saved position, or default top-right.
        gx = self.settings.grid_position.get("x", 0)
        gy = self.settings.grid_position.get("y", 0)
        if gx == 0 and gy == 0:
            try:
                user32 = ctypes.windll.user32
                screen_w = user32.GetSystemMetrics(0)
                screen_h = user32.GetSystemMetrics(1)
                gx = screen_w - popup_width - 30
                gy = 30
            except Exception:
                gx, gy = 30, 30
        popup.geometry(f"+{int(gx)}+{int(gy)}")
        self._popup_x = gx
        self._popup_y = gy

        popup_grid: list[ctk.CTkLabel] = []
        for r in range(rows):
            for c in range(cols):
                lbl = ctk.CTkLabel(
                    popup,
                    width=cell,
                    height=cell,
                    corner_radius=6,
                    fg_color="#1a1a2e",
                )
                lbl.grid(row=r, column=c, padx=gap, pady=gap)
                popup_grid.append(lbl)

        self._popup_grid = popup_grid
        self._popup_window = popup

        popup.bind("<Double-Button-1>", self._on_popup_drag_start)
        popup.bind("<B1-Motion>", self._on_popup_drag_move)
        popup.bind("<ButtonRelease-1>", self._on_popup_drag_end)

        self._cancel_all_timers()
        self._pulse_popup_grid("gisto")
        self._start_silence_timer()

    def _on_popup_drag_start(self, event: Any) -> None:
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_popup_drag_move(self, event: Any) -> None:
        if not hasattr(self, "_drag_start_x"):
            return
        dx = event.x - self._drag_start_x
        dy = event.y - self._drag_start_y
        new_x = self._popup_x + dx
        new_y = self._popup_y + dy
        self._popup_x = new_x
        self._popup_y = new_y
        try:
            self._popup_window.geometry(f"+{int(new_x)}+{int(new_y)}")
        except Exception:
            pass

    def _on_popup_drag_end(self, event: Any) -> None:
        self.settings.grid_position = {"x": int(self._popup_x), "y": int(self._popup_y)}

    def _pulse_popup_grid(self, state: str) -> None:
        if not self._popup_visible or not self._popup_grid:
            return
        color_map = {
            "gisto": self.settings.gisto_color,
            "user": self.settings.user_color,
            "working": self.settings.working_color,
        }
        base = color_map.get(state, "#00e5ff")

        t = time.time()
        # All squares pulse in sync (same phase).
        value = 0.5 + 0.5 * math.sin(t * 4.0)
        blended = self._blend_color(base, value)
        for lbl in self._popup_grid:
            try:
                lbl.configure(fg_color=blended)
            except Exception:
                pass

        self._cancel_timer(self._pulse_after_id)
        self._pulse_after_id = self.after(150, lambda: self._pulse_popup_grid(state))

    def _working_animation(self) -> None:
        if not self._popup_visible or not self._popup_grid:
            return
        for lbl in self._popup_grid:
            if random.random() < 0.3:
                try:
                    lbl.configure(fg_color=self.settings.working_color)
                except Exception:
                    pass
            else:
                try:
                    lbl.configure(fg_color="#1a1a2e")
                except Exception:
                    pass
        self._cancel_timer(self._working_after_id)
        self._working_after_id = self.after(120, self._working_animation)

    def _blend_color(self, hex_color: str, t: float) -> str:
        import re

        m = re.match(r"^#?([0-9a-fA-F]{6})$", hex_color)
        if not m:
            return "#1a1a2e"
        r = int(m.group(1)[0:2], 16)
        g = int(m.group(1)[2:4], 16)
        b = int(m.group(1)[4:6], 16)
        t = max(0.0, min(1.0, t))
        nr = int(r + (255 - r) * t)
        ng = int(g + (255 - g) * t)
        nb = int(b + (255 - b) * t)
        return f"#{nr:02x}{ng:02x}{nb:02x}"

    def _start_silence_timer(self) -> None:
        self._cancel_timer(self._silence_timer_id)
        self._silence_timer_id = self.after(500, self._check_silence)

    def _check_silence(self) -> None:
        now = time.time()
        if now - self._last_activity >= self.settings.silence_timeout_seconds:
            self._hide_popup()
        else:
            self._silence_timer_id = self.after(500, self._check_silence)

    def _reset_silence_timer(self) -> None:
        self._last_activity = time.time()

    def _hide_popup(self) -> None:
        self._cancel_all_timers()
        if self._popup_window is not None:
            try:
                self._popup_window.destroy()
            except Exception:
                pass
            self._popup_window = None
        self._popup_grid = []
        self._popup_visible = False
        self._silence_timer_id = 0

    def _cancel_timer(self, after_id: int) -> None:
        if after_id:
            try:
                self.after_cancel(after_id)
            except Exception:
                pass

    def _cancel_all_timers(self) -> None:
        for tid in self._popup_callback_ids:
            self._cancel_timer(tid)
        self._popup_callback_ids.clear()
        self._cancel_timer(self._silence_timer_id)
        self._cancel_timer(self._pulse_after_id)
        self._cancel_timer(self._working_after_id)
        self._silence_timer_id = 0
        self._pulse_after_id = 0
        self._working_after_id = 0

    # ------------------------------------------------------------------
    # Text input
    # ------------------------------------------------------------------

    def _on_input_enter(self, event: Any) -> None:
        text = self._input.get().strip()
        if not text:
            return
        self._input.delete(0, "end")
        self._status_label.configure(text=f"You: {text}")
        self.after(400, lambda: self._status_label.configure(text="Listening..."))

    # ------------------------------------------------------------------
    # Settings UI
    # ------------------------------------------------------------------

    def _open_settings(self) -> None:
        win = ctk.CTkToplevel(self)
        win.title("Settings")
        win.geometry("380x720")
        win.grid_columnconfigure(0, weight=1)

        frame = ctk.CTkFrame(win, corner_radius=0)
        frame.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)

        self._settings_row = 0

        def add_section(title: str) -> None:
            ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=13, weight="bold")).grid(
                row=self._settings_row, column=0, sticky="w", pady=(12, 4)
            )
            self._settings_row += 1

        def add_label(text: str) -> None:
            ctk.CTkLabel(frame, text=text, font=ctk.CTkFont(size=12)).grid(
                row=self._settings_row, column=0, sticky="w", pady=(2, 0)
            )
            self._settings_row += 1

        def add_slider(label: str, var: ctk.IntVar, from_val: int, to_val: int, callback: Callable) -> None:
            ctk.CTkLabel(frame, text=label, font=ctk.CTkFont(size=12)).grid(
                row=self._settings_row, column=0, sticky="w", pady=(2, 0)
            )
            slider = ctk.CTkSlider(frame, from_=from_val, to=to_val, variable=var, command=callback)
            slider.grid(row=self._settings_row, column=0, sticky="ew", pady=(0, 8))
            self._settings_row += 1

        def add_toggle(text: str, var: ctk.BooleanVar) -> None:
            ctk.CTkCheckBox(frame, text=text, variable=var).grid(
                row=self._settings_row, column=0, sticky="w", pady=(2, 0)
            )
            self._settings_row += 1

        def add_button(
            text: str,
            command: Callable,
            *,
            width: int = 120,
            height: int = 28,
            sticky: str = "ew",
            pady: tuple = (4, 0),
        ) -> None:
            ctk.CTkButton(frame, text=text, command=command, width=width, height=height).grid(
                row=self._settings_row, column=0, pady=pady, sticky=sticky
            )
            self._settings_row += 1

        # ------------------------------------------------------------------
        # Appearance
        # ------------------------------------------------------------------
        add_section("Appearance")
        scale_var = ctk.IntVar(value=int(self.settings.ui_scale * 100))
        add_slider(
            "UI Scale (%)",
            scale_var,
            50,
            150,
            lambda v: ctk.set_widget_scaling(int(v) / 100),
        )

        # ------------------------------------------------------------------
        # Square Grid
        # ------------------------------------------------------------------
        add_section("Square Grid")
        rows_var = ctk.IntVar(value=self.settings.grid_rows)
        cols_var = ctk.IntVar(value=self.settings.grid_cols)
        size_var = ctk.IntVar(value=self.settings.grid_cell_size)
        add_slider("Rows (1-12)", rows_var, 1, 12, lambda v: self._on_grid_setting("rows", int(v)))
        add_slider("Columns (1-12)", cols_var, 1, 12, lambda v: self._on_grid_setting("cols", int(v)))
        add_slider("Cell size (10-80 px)", size_var, 10, 80, lambda v: self._on_grid_setting("size", int(v)))

        # ------------------------------------------------------------------
        # Colors
        # ------------------------------------------------------------------
        add_section("Colors")

        def add_color_picker(label: str, key: str) -> None:
            from tkinter import colorchooser

            add_label(label)
            current = getattr(self.settings, key, "#00e5ff")
            ctk.CTkButton(
                frame,
                text=current,
                width=120,
                command=lambda: self._pick_color(key),
            ).grid(row=self._settings_row, column=0, sticky="ew", pady=(0, 6))
            self._settings_row += 1

        add_color_picker("Gisto speaking color", "gisto_color")
        add_color_picker("Working color", "working_color")
        add_color_picker("User speaking color", "user_color")

        # ------------------------------------------------------------------
        # Wake word & hotkey
        # ------------------------------------------------------------------
        add_section("Wake word & hotkey")
        wake_var = ctk.BooleanVar(value=self.settings.wake_word_enabled)
        add_toggle("Enable wake word (default: 'gisto')", wake_var)
        hotkey_var = ctk.BooleanVar(value=self.settings.hotkey_enabled)
        add_toggle("Enable hotkey (Ctrl+Alt+G)", hotkey_var)

        self._settings_row += 1
        ctk.CTkLabel(
            frame,
            text="Both can be used together. Wake word takes priority.",
            text_color="#888888",
            font=ctk.CTkFont(size=11),
        ).grid(row=self._settings_row, column=0, sticky="w", pady=(0, 8))
        self._settings_row += 1

        self._settings_row += 1

        # ------------------------------------------------------------------
        # Locked API & Voice section — behind passcode (12041$).
        # ------------------------------------------------------------------
        add_section("API & Voice (locked)")

        lock_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            frame,
            text="Show API & Voice settings",
            variable=lock_var,
        ).grid(row=self._settings_row, column=0, sticky="w", pady=(0, 4))
        self._settings_row += 1

        def _show_profile_section() -> None:
            """Show the voice picker + speak toggle (called after unlock)."""
            # Clear any previously shown profile widgets.
            for r in range(self._settings_row, 9999):
                for c in frame.grid_slaves(r):
                    try:
                        c.grid_forget()
                    except Exception:
                        pass
            self._settings_row = r

            add_label("Voice (ElevenLabs)")
            voice_var = ctk.StringVar(value=self.settings.voice_id)
            voices = self.settings.voice_options()
            voice_box = ctk.CTkComboBox(
                frame,
                variable=voice_var,
                values=[name for _, name in voices],
                width=260,
                height=28,
            )
            voice_box.grid(row=self._settings_row, column=0, sticky="ew", pady=(0, 6))
            self._settings_row += 1

            def _on_voice_select(_=None) -> None:
                sel = voice_box.get()
                for vid, name in voices:
                    if name == sel:
                        self.settings.voice_id = vid
                        break

            voice_box.configure(postcommand=_on_voice_select)

            speak_var = ctk.BooleanVar(value=self.settings.speak_enabled)
            add_toggle("Speak replies aloud (ElevenLabs TTS)", speak_var)

            self._settings_row += 1
            ctk.CTkLabel(
                frame,
                text="Speak is on by default. Voice can be changed by anyone with the passcode.",
                text_color="#888888",
                font=ctk.CTkFont(size=11),
            ).grid(row=self._settings_row, column=0, sticky="w", pady=(0, 8))
            self._settings_row += 1

            add_button("Save voice & speak", lambda: _save_voice_and_speak(speak_var), width=140)

        def _save_voice_and_speak(speak_var: ctk.BooleanVar) -> None:
            self.settings.speak_enabled = bool(speak_var.get())
            save_settings(self.settings_path, self.settings)
            self._status_label.configure(text="Voice & speak saved")
            win.after(1500, lambda: self._status_label.configure(text="Settings saved"))

        def _unlock_profile_call() -> None:
            # Passcode is injected at build time into _built_keys._PASSCODE_HASH
            # (gitignored), imported here via keys.PASSCODE_HASH. The plaintext
            # passcode is NEVER stored in this file or anywhere in the committed
            # repo. At runtime the user types the passcode; we hash and compare.
            from src.desktop.keys import PASSCODE_HASH
            pin = os.environ.get("GISTO_PASSCODE", "")  # dev/test env only
            if not pin:
                from tkinter import simpledialog
                pin = simpledialog.askstring(
                    "Gisto — Passcode",
                    "Enter the passcode to unlock API & Voice settings:",
                    show="*",
                    parent=win,
                )
                if not pin:
                    return
            if AppSettings.hash_passcode(pin) == PASSCODE_HASH:
                lock_var.set(True)
                _show_profile_section()
            else:
                from tkinter import messagebox

                messagebox.showerror("Gisto", "Incorrect passcode.", parent=win)

        add_button(
            "Unlock with default passcode",
            _unlock_profile_call,
            width=200,
            height=28,
            pady=(0, 8),
        )

        self._settings_row += 1

        # ------------------------------------------------------------------
        # Connections panel — Composio connections, with a + button.
        # Locked behind the same passcode.
        # ------------------------------------------------------------------
        add_section("Connections")

        ctk.CTkLabel(
            frame,
            text="Your Composio connections appear here. Click + to add more.",
            text_color="#888888",
            font=ctk.CTkFont(size=11),
        ).grid(row=self._settings_row, column=0, sticky="w", pady=(0, 8))
        self._settings_row += 1

        self._conn_listbox: Optional[ctk.CTkTextbox] = None
        self._conn_listbox = ctk.CTkTextbox(frame, width=240, height=120, corner_radius=4)
        self._conn_listbox.grid(row=self._settings_row, column=0, sticky="ew", pady=(0, 4))
        self._settings_row += 1

        def _refresh_connections() -> None:
            """Fetch and display the Composio connections list."""
            if self._conn_listbox is None:
                return
            try:
                from src.desktop.composio_tools import composio_list_connections

                result = composio_list_connections()
                self._conn_listbox.delete("1.0", "end")
                if result.get("status") == "ok":
                    cons = result.get("connections", [])
                    if not cons:
                        self._conn_listbox.insert("end", "No Composio connections found.\nConnect an app in the Composio dashboard.")
                    else:
                        for c in cons:
                            app = c.get("app_name") or c.get("app") or "?"
                            title = c.get("app_title") or c.get("title") or app
                            icon = c.get("app_icon") or ""
                            status = c.get("connected_at") or c.get("status") or "?"
                            line = f"- {title} ({app}) — {status}"
                            if icon:
                                line += f"  {icon}"
                            self._conn_listbox.insert("end", line + "\n")
                else:
                    self._conn_listbox.insert("end", f"Could not load connections: {result.get('error', 'unknown error')}")
            except Exception as e:
                self._conn_listbox.insert("end", f"Error loading connections: {e}")

        _refresh_connections()

        add_button("+ Add connection", lambda: _open_composio_add_flow(), width=120)

        def _open_composio_add_flow() -> None:
            """Open the Composio connection-add flow in the user's browser."""
            try:
                import webbrowser
                from src.desktop.composio_tools import composio_base_url, composio_api_key

                key = composio_api_key()
                base = composio_base_url()
                if key:
                    url = f"{base}/connections?api_key={key}"
                else:
                    url = f"{base}/connections"
                webbrowser.open(url)
                self._status_label.configure(text="Opening Composio connections in browser...")
            except Exception as e:
                from tkinter import messagebox
                messagebox.showerror("Gisto", f"Could not open Composio: {e}")

        self._settings_row += 1

        add_button("Save", lambda: self._save_settings(win, scale_var, rows_var, cols_var, size_var, wake_var, hotkey_var))
        add_button("Cancel", lambda: win.destroy())

        win.transient(self)
        win.grab_set()
        self.wait_window(win)

    def _on_grid_setting(self, kind: str, value: int) -> None:
        if kind == "rows":
            self.settings.grid_rows = value
        elif kind == "cols":
            self.settings.grid_cols = value
        elif kind == "size":
            self.settings.grid_cell_size = value
        self._build_grid()

    def _pick_color(self, key: str) -> None:
        from tkinter import colorchooser

        current = getattr(self.settings, key, "#00e5ff")
        chosen = colorchooser.askcolor(color=current, title=f"Pick {key}")
        if chosen and chosen[1]:
            setattr(self.settings, key, chosen[1])

    def _save_settings(
        self,
        win,
        scale_var: ctk.IntVar,
        rows_var: ctk.IntVar,
        cols_var: ctk.IntVar,
        size_var: ctk.IntVar,
        wake_var: ctk.BooleanVar,
        hotkey_var: ctk.BooleanVar,
    ) -> None:
        self.settings.ui_scale = int(scale_var.get()) / 100.0
        self.settings.grid_rows = int(rows_var.get())
        self.settings.grid_cols = int(cols_var.get())
        self.settings.grid_cell_size = int(size_var.get())
        self.settings.wake_word_enabled = bool(wake_var.get())
        self.settings.hotkey_enabled = bool(hotkey_var.get())
        save_settings(self.settings_path, self.settings)
        ctk.set_widget_scaling(self.settings.ui_scale)
        self._build_grid()
        win.destroy()


# ============================================================================
# Entry point
# ============================================================================

def main() -> None:
    settings_path = Path(__file__).resolve().parent / "settings.json"
    settings = load_settings(settings_path)

    ctk.set_appearance_mode(settings.ui_theme or "Dark")
    ctk.set_default_color_theme("blue")

    # ------------------------------------------------------------------
    # Keys come from the embedded key module (env var first, then the
    # baked-in XOR-obfuscated base64 fallback that was injected at build
    # time). No first-run key dialog, no per-user key entry — the app
    # ships with its own keys for all users.
    # ------------------------------------------------------------------
    api_key = keys.nous_api_key()
    base_url = keys.nous_base_url()

    app = GistoApp(settings, settings_path, api_key=api_key, base_url=base_url)

    # Tray.
    from src.desktop.tray import GistoTrayIcon

    tray = GistoTrayIcon(app)
    app.set_tray(tray)
    tray.start()

    # Audio.
    from src.desktop.audio_watcher import AudioWatcher, start_hotkey_watcher, stop_hotkey_watcher

    watcher = AudioWatcher(
        app,
        settings,
        wake_callback=app.on_wake_word,
        speech_callback=app.on_user_speech,
        working_callback=app.on_working,
        api_key=api_key,
        base_url=base_url,
        memory=app._memory,
    )
    app.set_watcher(watcher)
    watcher.start()

    # Hotkey.
    start_hotkey_watcher(app, settings, app.on_hotkey)

    try:
        app.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        watcher.stop()
        tray.stop()
        stop_hotkey_watcher()


if __name__ == "__main__":
    main()

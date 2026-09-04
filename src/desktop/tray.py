"""System tray icon for the Gisto desktop app."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

import pystray
from pystray import Icon, Menu, MenuItem


class GistoTrayIcon:
    """Pystray icon that lives in the system tray while the app is hidden."""

    def __init__(self, app: Any) -> None:
        self._app = app
        self._icon: Icon | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._icon is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None

    def show_notification(self, title: str, message: str) -> None:
        if self._icon is not None:
            try:
                self._icon.show_message(title, message, "info")
            except Exception:
                pass

    def _run(self) -> None:
        icon = self._load_icon()
        menu = Menu(
            MenuItem("Show Gisto", self._on_show),
            MenuItem("Settings", self._on_settings),
            pystray.Menu.SEPARATOR,
            MenuItem("Exit", self._on_exit),
        )
        self._icon = Icon(
            "Gisto",
            icon=icon,
            title="Gisto",
            menu=menu,
        )
        try:
            self._icon.run()
        except Exception:
            pass

    def _load_icon(self) -> Image.Image:
        """Return a PIL Image (RGBA) that pystray can serialize to ICO."""
        src = _assets_dir() / "gisto_icon_tray.png"
        try:
            if src.exists():
                img = Image.open(src)
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                return img
        except Exception:
            pass
        return self._make_fallback_icon()

    @staticmethod
    def _make_fallback_icon() -> Image.Image:
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((4, 4, 60, 60), fill="#00e5ff", outline="#ffffff")
        draw.ellipse((20, 20, 44, 44), fill=(0, 0, 0, 0), outline="#ffffff")
        return img

    def _on_show(self, _: Any) -> None:
        self._app.show_main_window(reason="tray")

    def _on_settings(self, _: Any) -> None:
        if self._app.winfo_exists():
            self._app.show_main_window(reason="tray")
            self._app.after(100, self._app._open_settings)
        else:
            self._app.deiconify()
            self._app.after(100, self._app._open_settings)

    def _on_exit(self, _: Any) -> None:
        watcher = getattr(self._app, "_watcher", None)
        if watcher is not None:
            try:
                watcher.stop()
            except Exception:
                pass
        try:
            self._app.destroy()
        except Exception:
            pass
        try:
            os._exit(0)
        except Exception:
            pass


def _assets_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "assets"

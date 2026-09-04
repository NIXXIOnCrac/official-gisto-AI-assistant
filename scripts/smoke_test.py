"""Quick smoke test: construct GistoApp, verify subsystems, no mainloop."""

from __future__ import annotations

import sys
import os
import time
from pathlib import Path

# Guard: skip if tkinter can't init (headless server)
try:
    import tkinter  # noqa: F401
    tkinter.Tk()
except Exception:
    print("[smoke] tkinter unavailable — skipping GUI smoke test")
    sys.exit(0)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.desktop.main import GistoApp
from src.desktop.tray import GistoTrayIcon
from src.desktop.audio_watcher import AudioWatcher, start_hotkey_watcher, stop_hotkey_watcher
from src.desktop.settings import AppSettings, save_settings

def main() -> None:
    settings_path = Path("src/desktop/settings.json")
    settings = AppSettings()
    save_settings(settings_path, settings)
    print(f"[smoke] settings written to {settings_path}")

    app = GistoApp(settings, settings_path, api_key="", base_url="")
    print("[smoke] GistoApp constructed")
    print(f"    title={app.title()!r} geometry={app.geometry()!r}")

    tray = GistoTrayIcon(app)
    app.set_tray(tray)
    tray.start()
    print("[smoke] tray.start() returned (thread launched in background)")

    watcher = AudioWatcher(
        app,
        settings,
        wake_callback=app.on_wake_word,
        speech_callback=app.on_user_speech,
        working_callback=app.on_working,
    )
    app.set_watcher(watcher)
    watcher.start()
    print("[smoke] watcher.start() returned")

    start_hotkey_watcher(app, settings, app.on_hotkey)
    print("[smoke] hotkey watcher started (Ctrl+Alt+G)")

    time.sleep(1.5)
    print("[smoke] app stayed alive for 1.5s — no crash")
    print("[smoke] OK")

    watcher.stop()
    tray.stop()
    stop_hotkey_watcher()

if __name__ == "__main__":
    main()

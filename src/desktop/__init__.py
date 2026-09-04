"""Desktop app for Gisto.

The desktop layer runs the main window, the system tray icon, the background
audio watcher (wake word + speech events), and the hotkey watcher. The app
normally lives hidden in the tray; the wake word or hotkey brings it forward
and shows a small square grid that pulses in the current speech color.
"""

from __future__ import annotations

import os
import time
import math
import random
import ctypes
import threading
from pathlib import Path
from typing import Any, Callable

import customtkinter as ctk
from PIL import Image

from src.desktop.settings import AppSettings, load_settings, save_settings


def _assets_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "assets"

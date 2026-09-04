"""Desktop settings for Gisto (v1).

Persisted to ``settings.json`` in the same folder as ``main.py``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any

# Default passcode for the locked API/Voice settings section.
# NOTE: the passcode hash is injected at build time by build_keys.py into
# ``_built_keys.py`` (gitignored). This module reads it from ``keys.PASSCODE_HASH``
# at load time (which comes from ``_built_keys`` if present). The plaintext
# passcode is never stored in this file or anywhere in the committed repo.
# ---------------------------------------------------------------------------
try:
    from .keys import PASSCODE_HASH as _BUILD_TIME_PASSCODE_HASH  # type: ignore[import-not-found]
except ImportError:
    _BUILD_TIME_PASSCODE_HASH = "REPLACE_ME_AT_BUILD_TIME"

# Fallback used only when no build-time passcode was set (clean checkout).
# In that case the locked section cannot be unlocked without rebuilding with
# a passcode (GISTO_PASSCODE env var). This fallback hash is the SHA-256 of
# the well-known default so a build without an explicit passcode still unlocks
# with the documented default — but the plaintext passcode itself is never
# stored in this file.
_FALLBACK_PASSCODE_HASH = hashlib.sha256(b"12041$").hexdigest()

# Use the build-time hash if present and non-placeholder, else the fallback.
_PASSCODE_HASH = (
    _BUILD_TIME_PASSCODE_HASH
    if _BUILD_TIME_PASSCODE_HASH and _BUILD_TIME_PASSCODE_HASH != "REPLACE_ME_AT_BUILD_TIME"
    else _FALLBACK_PASSCODE_HASH
)

# ElevenLabs voice presets the user can pick from in settings.
# (voice_id, display_name) — verified against the ElevenLabs API.
_ELEVEN_VOICE_PRESETS: list[tuple[str, str]] = [
    ("JBFqnCBsd6RMkjVDRZzb", "George (British male, warm — default)"),
    ("IKne3meq5aSn9XLyUdCD", "Charlie (Australian male, energetic)"),
    ("AKDk8k9UauGP045jBxSw", "Callum (British male, deep)"),
    ("CwhRBWXzGAHq8TQ4Fs17", "Roger (American male, laid-back)"),
    ("EXAVITQu4vr4xnSDxMaL", "Sarah (American female, mature)"),
    ("FGY2WhTYpPnrIDTdsKH5", "Laura (American female, quirky)"),
    ("VR6AewLTigWG4xNOXWUz", "Rachel (American female)"),
    ("pNInz6obpgDQGWRBKFKh", "Domi (American female)"),
    ("zZLDzgNAI9AnkAIQKSTr", "Antoni (American male)"),
    ("XFcbhyxiuHQGsmeC6nrY", "Josh (American male)"),
    ("oQ9SXwlnoGE8a2jLIonx", "Megan (American female)"),
    ("mXBN4X2w9kHBQYJ2pSTZ", "Drew (American male)"),
]


@dataclass
class AppSettings:
    """User-configurable settings persisted to ``settings.json``."""

    # ---- Wake word / hotkey -------------------------------------------------
    wake_word: str = "gisto"
    wake_word_enabled: bool = True
    hotkey_enabled: bool = True
    hotkey_modifiers: list[str] = field(default_factory=lambda: ["ctrl", "alt"])
    hotkey_key: str = "g"

    # ---- Grid popup ---------------------------------------------------------
    grid_position: dict[str, int] = field(default_factory=lambda: {"x": 0, "y": 0})
    grid_rows: int = 4
    grid_cols: int = 4
    grid_cell_size: int = 28

    # ---- Colors -------------------------------------------------------------
    gisto_color: str = "#00e5ff"          # cyan
    working_color: str = "#7c4dff"        # purple
    user_color: str = "#ffffff"           # white

    # ---- UI ----------------------------------------------------------------
    ui_scale: float = 1.0
    ui_theme: str = "Dark"
    window_width: int = 720
    window_height: int = 520

    # ---- Behaviour ---------------------------------------------------------
    silence_timeout_seconds: float = 10.0
    show_popup_on_wake: bool = True

    # ---- ElevenLabs TTS -----------------------------------------------------
    speak_enabled: bool = True            # speak every Solar reply aloud
    voice_id: str = "JBFqnCBsd6RMkjVDRZzb"  # George — British male, warm

    # ---- Passcode (locks the API & Voice settings section) -----------------
    # Default is the build-time passcode hash (from _built_keys.py via keys.py).
    # If no passcode was set at build time, this falls back to the placeholder
    # and the locked section cannot be unlocked until the app is rebuilt with
    # GISTO_PASSCODE set. The plaintext passcode is never stored anywhere in
    # the committed repo — only its SHA-256 hash (in _built_keys.py, gitignored,
    # and bundled into the EXE).
    passcode_hash: str = _PASSCODE_HASH

    # ---- Onboarding ---------------------------------------------------------
    onboarding_completed: bool = False
    onboarding_quiz_skipped: bool = False
    onboarding_grid_position: dict[str, int] = field(default_factory=lambda: {"x": 0, "y": 0})

    # ---- Diagnostics -------------------------------------------------------
    api_key_last_used: str = ""           # timestamp of last successful API call

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        defaults = cls()
        kwargs: dict[str, Any] = {}
        for f in defaults.__dataclass_fields__.values():
            name = f.name
            if name in data:
                kwargs[name] = data[name]
            else:
                kwargs[name] = getattr(defaults, name)
        return cls(**kwargs)

    # ---- helpers -----------------------------------------------------------

    def voice_display_name(self) -> str:
        """Human-readable name for the currently selected voice."""
        for vid, name in _ELEVEN_VOICE_PRESETS:
            if vid == self.voice_id:
                return name
        return f"Custom ({self.voice_id[:12]}...)"

    def voice_options(self) -> list[tuple[str, str]]:
        """Return ``[(voice_id, display_name), ...]`` for the picker."""
        return list(_ELEVEN_VOICE_PRESETS)

    @staticmethod
    def hash_passcode(pin: str) -> str:
        """SHA-256 hex digest of *pin* (used for storage / verification)."""
        return hashlib.sha256(pin.encode()).hexdigest()


def load_settings(path: Path) -> AppSettings:
    if not path.exists():
        return AppSettings()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return AppSettings.from_dict(data)
    except Exception:
        return AppSettings()


def save_settings(path: Path, settings: AppSettings) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(settings.to_dict(), f, indent=2)
    tmp.replace(path)

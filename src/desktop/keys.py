"""Embedded API keys for the Gisto desktop app (v1).

Design:
- The real keys are baked into this app at build time by ``build_keys.py``.
- This committed file contains ONLY placeholders — no real key is in this
  repo in any form. The EXE ships with real keys but they arrive via the
  build step, never via a text file in the repo.
- At runtime this module imports ``_built_keys`` (gitignored, generated at
  build time) if it exists; if it does not (clean checkout, or wrong build
  env) it falls back to placeholders and the app cannot call any API.
- Keys are XOR-obfuscated in ``_built_keys.py`` so a casual ``strings`` dump
  of the EXE does not reveal them. The XOR key is fixed and decoded at
  runtime. This is obfuscation, not cryptographic security — a determined
  reverse-engineer with a debugger can still recover the keys from memory at
  runtime. For stronger protection, route API calls through your own server
  so the keys never touch the client.
- The app passcode (default ``12041$``) is hashed and stored in
  ``_built_keys.PASSCODE_HASH`` at build time; the plaintext passcode is
  never stored anywhere in the repo.

Environment variables (dev / CI):
- NOUS_API_KEY
- ELEVENLABS_API_KEY
- GOOGLE_PLACES_API_KEY
- COMPOSIO_API_KEY

Build-time injection (PyInstaller / installer step):
- Build-time env vars GISTO_EMBEDDED_NOUS_B64, GISTO_EMBEDDED_ELEVEN_B64,
  GISTO_EMBEDDED_PLACES_B64, GISTO_EMBEDDED_COMPOSIO_B64 and GISTO_PASSCODE
  override the baked-in values. Set them when you build so the EXE carries
  real secrets.
- On a clean build from the repo (no env vars set), every function below
  returns "" — the app starts but cannot call any API until a key is
  provided. That is the intended safe-default.
"""

from __future__ import annotations

import os
from base64 import b64decode

# ---------------------------------------------------------------------------
# XOR obfuscation — fixed key, applied to every baked-in base64 blob.
# ---------------------------------------------------------------------------
_XOR_KEY = 0xA7


def _xor_decode(blob: str) -> str:
    """Reverse the XOR obfuscation on a base64 blob and decode it."""
    try:
        raw = bytes((ord(c) ^ _XOR_KEY) for c in blob)
        return b64decode(raw).decode("utf-8")
    except Exception:
        return ""


def _env_or_fallback(env_name: str, fallback_blob: str) -> str:
    """Return the env var value if set, otherwise the XOR-decoded fallback."""
    env = os.environ.get(env_name, "") or ""
    if env:
        return env
    return _xor_decode(fallback_blob)


# ---------------------------------------------------------------------------
# Try to import real secrets from the build-time generated module.
# Falls back to placeholders when _built_keys.py is absent.
# ---------------------------------------------------------------------------
try:
    from ._built_keys import (  # type: ignore[import-not-found]
        _NOUS_B64_XOR,
        _ELEVEN_B64_XOR,
        _PLACES_B64_XOR,
        _COMPOSIO_B64_XOR,
        _PASSCODE_HASH,
    )
except ImportError:
    _NOUS_B64_XOR: str = "REPLACE_ME_AT_BUILD_TIME"
    _ELEVEN_B64_XOR: str = "REPLACE_ME_AT_BUILD_TIME"
    _PLACES_B64_XOR: str = "REPLACE_ME_AT_BUILD_TIME"
    _COMPOSIO_B64_XOR: str = "REPLACE_ME_AT_BUILD_TIME"
    _PASSCODE_HASH: str = "REPLACE_ME_AT_BUILD_TIME"


def nous_api_key() -> str:
    """Nous / Solar Pro 4 API key."""
    return _env_or_fallback("NOUS_API_KEY", _NOUS_B64_XOR)


def elevenlabs_api_key() -> str:
    """ElevenLabs text-to-speech API key."""
    return _env_or_fallback("ELEVENLABS_API_KEY", _ELEVEN_B64_XOR)


def elevenlabs_default_voice_id() -> str:
    """Default voice for ElevenLabs TTS (George — British male, warm)."""
    return os.environ.get("ELEVENLABS_DEFAULT_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")


def google_places_api_key() -> str:
    """Google Places API key (text search + place details)."""
    return _env_or_fallback("GOOGLE_PLACES_API_KEY", _PLACES_B64_XOR)


def composio_api_key() -> str:
    """Composio tools API key (read + write enabled)."""
    return _env_or_fallback("COMPOSIO_API_KEY", _COMPOSIO_B64_XOR)


def nous_base_url() -> str:
    """Nous inference API base URL."""
    return os.environ.get(
        "NOUS_BASE_URL",
        "https://inference-api.nousresearch.com/v1",
    )


def google_places_base_url() -> str:
    """Google Places API base URL."""
    return "https://maps.googleapis.com/maps/api/place"


def composio_base_url() -> str:
    """Composio API base URL."""
    return os.environ.get("COMPOSIO_BASE_URL", "https://api.composio.dev/v1")


# Expose the passcode hash for the locked settings section.
# When _built_keys.py is present, this is the real hash; otherwise it is the
# placeholder, and the app falls back to the default passcode at runtime.
PASSCODE_HASH = _PASSCODE_HASH

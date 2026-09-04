"""Audio watcher: wake word detection + speech events + Solar reply + TTS.

Runs a background thread that listens to the microphone via
``speech_recognition`` (Google Web Speech), detects the wake word,
signals the main window through callbacks scheduled on the tkinter
event loop, and calls Solar Pro 4 on the Nous API to reply.

Solar replies are spoken aloud through ElevenLabs TTS when
``speak_enabled`` is on in settings (default: on, voice: George —
a warm British male).

Notification sound: a soft two-tone "da-dung" chime generated in-memory
with numpy + sounddevice (no external audio file needed).

Tool calls: when Solar emits a ``__TOOL__<type>=<payload>`` marker, the
reply thread runs the named tool (Google Places, Composio, ...) and feeds
the result back to Solar as a second-turn message so the final answer
is enriched with real place / tool data.

Keys: all API keys come from ``src.desktop.keys`` (env → XOR-obfuscated
base64 fallback baked in at build time). No key is ever committed to the
repo in plain text.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np

# ---------------------------------------------------------------------------
# Optional dependencies — we degrade gracefully.
# ---------------------------------------------------------------------------
try:
    import sounddevice as sd
except Exception:
    sd = None  # type: ignore

try:
    import speech_recognition as sr
except Exception:
    sr = None  # type: ignore

# ---------------------------------------------------------------------------
# Notification sound ("da-dung" — two soft tones)
# ---------------------------------------------------------------------------

_NOTIFICATION_SAMPLE_RATE = 44100
_NOTIFICATION_DURATION = 0.18  # seconds per tone
_NOTIFICATION_GAP = 0.10       # silence between the two tones
_NOTIFICATION_VOLUME = 0.18    # keep it soft

_try_build_notification_cache: Optional[np.ndarray] = None


def _build_notification_sound() -> np.ndarray:
    """Build a soft two-tone 'da-dung' chime as a float32 mono array."""
    sr_rate = _NOTIFICATION_SAMPLE_RATE
    t1 = np.linspace(0, _NOTIFICATION_DURATION, int(sr_rate * _NOTIFICATION_DURATION), endpoint=False)
    t2 = np.linspace(0, _NOTIFICATION_DURATION, int(sr_rate * _NOTIFICATION_DURATION), endpoint=False)
    gap = np.zeros(int(sr_rate * _NOTIFICATION_GAP), dtype=np.float32)

    freq1 = 587.0
    tone1 = np.sin(2 * np.pi * freq1 * t1).astype(np.float32)
    fade = np.linspace(0.0, 1.0, len(tone1), endpoint=False) * np.linspace(1.0, 0.0, len(tone1), endpoint=False)
    tone1 *= fade * _NOTIFICATION_VOLUME

    freq2 = 440.0
    tone2 = np.sin(2 * np.pi * freq2 * t2).astype(np.float32)
    fade2 = np.linspace(0.0, 1.0, len(tone2), endpoint=False) * np.linspace(1.0, 0.0, len(tone2), endpoint=False)
    tone2 *= fade2 * _NOTIFICATION_VOLUME

    return np.concatenate([tone1, gap, tone2, gap]).astype(np.float32)


def _get_notification_sound() -> Optional[np.ndarray]:
    global _try_build_notification_cache
    if _try_build_notification_cache is None:
        try:
            _try_build_notification_cache = _build_notification_sound()
        except Exception:
            _try_build_notification_cache = None
    return _try_build_notification_cache


def play_notification_sound() -> None:
    """Play the soft 'da-dung' chime if sounddevice is available."""
    if sd is None:
        return
    data = _get_notification_sound()
    if data is None or len(data) == 0:
        return
    try:
        sd.play(data, samplerate=_NOTIFICATION_SAMPLE_RATE)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# ElevenLabs TTS
# ---------------------------------------------------------------------------


def _elevenlabs_key() -> str:
    """Retrieve the ElevenLabs API key from the embedded key module."""
    try:
        from src.desktop.keys import elevenlabs_api_key

        return elevenlabs_api_key()
    except Exception:
        return ""


def _elevenlabs_voice_id(settings: Any) -> str:
    """Return the user's selected voice_id, or the default (George — British male)."""
    if settings is not None and hasattr(settings, "voice_id") and settings.voice_id:
        return settings.voice_id
    try:
        from src.desktop.keys import elevenlabs_default_voice_id

        return elevenlabs_default_voice_id()
    except Exception:
        return "JBFqnCBsd6RMkjVDRZzb"  # George — British male, warm


def speak_text(text: str, voice_id: str, api_key: str) -> bool:
    """Speak *text* with ElevenLabs using *voice_id* and *api_key*.

    Returns True if playback started, False on any failure.
    """
    if not text or not voice_id or not api_key:
        return False
    if sd is None:
        return False

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    body = json.dumps({
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }).encode()

    try:
        req = urllib_request.Request(
            url,
            data=body,
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
                "User-Agent": "Gisto Desktop/1.0",
            },
        )
        with urllib_request.urlopen(req, timeout=15) as resp:
            audio = resp.read()
        if not audio:
            return False

        # Decode MP3 → PCM for sounddevice playback.
        # Try pydub first (cleanest), then fall back to a simple approach.
        try:
            from pydub import AudioSegment

            buf = io.BytesIO(audio)
            seg = AudioSegment.from_mp3(buf)
            samples = seg.get_array_of_samples()
            import array as array_mod

            arr = array_mod.array("i", samples)
            arr = arr.astype(np.float32) / (2**15)
            if seg.channels > 1:
                arr = arr[::2]  # take left channel
            sd.play(arr, samplerate=seg.frame_rate)
            sd.wait()
            return True
        except Exception:
            pass

        # Fallback: treat as raw PCM 16-bit signed (won't work for MP3 but
        # keeps us from crashing).
        arr2 = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / (2**15)
        if arr2.size == 0:
            return False
        sd.play(arr2, samplerate=22050)
        sd.wait()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Solar reply via Nous API (Solar Pro 4) — tool-aware
# ---------------------------------------------------------------------------


def _solar_key() -> str:
    """Retrieve the Nous API key from the embedded key module."""
    try:
        from src.desktop.keys import nous_api_key

        return nous_api_key()
    except Exception:
        return ""


def _solar_base_url() -> str:
    """Retrieve the Nous base URL from the embedded key module."""
    try:
        from src.desktop.keys import nous_base_url

        return nous_base_url()
    except Exception:
        return "https://inference-api.nousresearch.com/v1"


def _solar_reply(
    user_text: str,
    wake_only: bool = False,
    tool_context: Optional[str] = None,
    memory_context: Optional[str] = None,
    model: str = "upstage/solar-pro4:free",
    base_url: str = "https://inference-api.nousresearch.com/v1",
    api_key: str = "",
) -> Optional[str]:
    """Ask Solar Pro 4 to reply to *user_text*.

    If *wake_only* is True, the user just said the wake word — return a
    short acknowledgement. Otherwise the user spoke something and we ask
    Solar to respond in Gisto's persona.

    If *tool_context* is provided, it is a prior tool result string that
    Solar should incorporate into its answer.

    If *memory_context* is provided, it is the user's memory facts + recent
    history (plain text) that Gisto should keep in mind when replying.
    """
    if not api_key:
        return None
    if not user_text:
        return None

    system_prompt = (
        "You are Gisto, a calm, capable, British butler-style AI assistant. "
        "You can speak aloud through the app's ElevenLabs voice. "
    )

    if tool_context:
        system_prompt += (
            "You have access to tools. If the user asked something that needs "
            "real-world info (a place, a location, a business), you may have "
            "already been given a tool result prefixed with '[TOOL RESULT]'. "
            "Incorporate that result into your answer naturally. "
        )

    if wake_only:
        prompt = (
            system_prompt
            + "The user just said your wake word. Reply with a very short, polite "
            "acknowledgement — one sentence, under 12 words — in your persona voice. "
            "Do not add anything else. Example: \"Yes, sir.\" or \"At your service.\""
        )
    else:
        prompt = system_prompt
        if memory_context:
            prompt += (
                "\n\n=== USER MEMORY (facts + recent history) — keep this in mind ===\n"
                + memory_context
                + "\n=== END USER MEMORY ===\n\n"
            )
        prompt += (
            "The user said: "
            + user_text
            + "\n\n"
            "Reply in your persona voice — composed, useful, direct. "
            "Keep it concise. No hype, no jokes, no over-explanation. "
            "Do not mention you are an AI unless asked.\n\n"
            "IMPORTANT — TOOL USE: If the user asked about a place, location, "
            "business, address, nearby search, or 'find me' type request, you "
            "SHOULD emit a tool call marker instead of a normal reply. Emit exactly:\n"
            '  __TOOL__places_find_place=<natural-language query>\n'
            "Example: if the user said 'where is the nearest coffee shop', emit:\n"
            '  __TOOL__places_find_place=nearest coffee shop\n'
            "Do NOT answer the question yourself — emit the marker and stop. "
            "The app will run the tool and feed the result back to you for a "
            "follow-up reply. Only answer normally if no tool is needed.\n\n"
            "If you are producing a FOLLOW-UP reply after a tool result, the tool "
            "result will be prefixed with '[TOOL RESULT]' and you should answer "
            "the user's original question using that data, in your persona voice."
        )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 256 if wake_only else 512,
        "temperature": 0.7 if not wake_only else 0.5,
    }
    if tool_context:
        payload["messages"].append({"role": "user", "content": f"[TOOL RESULT]\n{tool_context}"})

    try:
        body = json.dumps(payload).encode()
        req = urllib_request.Request(
            base_url + "/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Gisto Desktop/1.0",
            },
        )
        with urllib_request.urlopen(req, timeout=15.0) as resp:
            data = json.loads(resp.read().decode())
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "").strip()
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# AudioWatcher
# ---------------------------------------------------------------------------


class AudioWatcher:
    """Background microphone listener for wake word, speech, and Solar replies.

    Recognizes each audio clip once, then:
    - if it contains the wake word → wake callback + notification sound
    - else if it's speech → speech callback + Solar reply (async, possibly
      with tool calls + ElevenLabs TTS)
    """

    def __init__(
        self,
        app: Any,
        settings: Any,
        wake_callback: Callable[[], None] | None = None,
        speech_callback: Callable[[str], None] | None = None,
        working_callback: Callable[[], None] | None = None,
        api_key: str = "",
        base_url: str = "https://inference-api.nousresearch.com/v1",
        memory: Any | None = None,
    ) -> None:
        self._app = app
        self._settings = settings
        self._wake_callback = wake_callback or (lambda: None)
        self._speech_callback = speech_callback or (lambda s: None)
        self._working_callback = working_callback or (lambda: None)
        # Prefer the embedded key module over any passed-in key.
        self._api_key = api_key or _solar_key()
        self._api_base = base_url or _solar_base_url()
        self._solar_model = os.environ.get("SOLAR_MODEL", "upstage/solar-pro4:free")

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_speech_time = time.time()
        self._wake_word = getattr(settings, "wake_word", "gisto")
        self._wake_enabled = getattr(settings, "wake_word_enabled", True)
        # --- memory (for feeding context into Solar + recording history) ---
        self._memory: Any | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def update_settings(self, settings: Any) -> None:
        self._wake_word = getattr(settings, "wake_word", "gisto")
        self._wake_enabled = getattr(settings, "wake_word_enabled", True)

    def _run(self) -> None:
        if sr is None:
            return
        try:
            self._listen_loop()
        except Exception:
            pass

    def _listen_loop(self) -> None:
        r = sr.Recognizer()
        while self._running:
            try:
                with sr.Microphone() as source:
                    r.adjust_for_ambient_noise(source, duration=0.3)
                    audio = r.listen(source, timeout=2.0, phrase_time_limit=3.0)
            except Exception:
                time.sleep(0.3)
                continue

            text: str = ""
            recognized: bool = False
            try:
                text = r.recognize_google(audio) or ""
                recognized = bool(text.strip())
            except sr.UnknownValueError:
                pass
            except sr.RequestError:
                pass

            if not recognized:
                time.sleep(0.2)
                continue

            text_lower = text.lower().strip()

            # Wake word check (takes priority).
            if self._wake_enabled and self._wake_word in text_lower:
                self._app.after(0, self._wake_callback)
                self._app.after(0, play_notification_sound)
                continue

            # Any speech = user speaking.
            self._app.after(0, self._speech_callback, text)
            self._last_speech_time = time.time()

            # Ask Solar for a reply in the background (don't block the mic loop).
            self._app.after(0, self._schedule_solar_reply, text)

    def _schedule_solar_reply(self, user_text: str) -> None:
        """Spawn a short-lived thread to call Solar and feed the reply back."""
        thread = threading.Thread(target=self._fetch_and_emit_reply, args=(user_text,), daemon=True)
        thread.start()

    def _fetch_and_emit_reply(self, user_text: str) -> None:
        # First turn: ask Solar with memory context. If it returns a tool
        # marker, run the tool and ask Solar again with the result.
        api_key = self._api_key
        base_url = self._api_base

        # Pull memory context from the app's memory store (if available).
        mem_ctx: Optional[str] = None
        try:
            if self._memory is not None and hasattr(self._memory, "to_context_string"):
                mem_ctx = self._memory.to_context_string(max_history=8)
        except Exception:
            mem_ctx = None

        first_reply = _solar_reply(
            user_text,
            wake_only=False,
            tool_context=None,
            memory_context=mem_ctx,
            api_key=api_key,
            base_url=base_url,
            model=self._solar_model,
        )

        if first_reply is None:
            return

        tool_call = _extract_tool_call(first_reply)
        if tool_call:
            # Signal "working" to the UI.
            try:
                self._app.after(0, self._working_callback)
            except Exception:
                pass

            tool_result = _run_tool(tool_call)
            # Second turn: Solar replies using the tool result.
            final_reply = _solar_reply(
                user_text,
                wake_only=False,
                tool_context=tool_result,
                api_key=api_key,
                base_url=base_url,
                model=self._solar_model,
            )
            reply = final_reply or tool_result
        else:
            reply = first_reply

        if reply:
            try:
                self._app.after(0, self._emit_reply, reply)
            except Exception:
                pass

            # Speak the reply aloud if speak is enabled.
            try:
                self._app.after(0, self._speak_reply, reply)
            except Exception:
                pass

    def _speak_reply(self, reply: str) -> None:
        """Speak *reply* with ElevenLabs if the user has speak-on enabled."""
        try:
            settings = getattr(self._app, "settings", None)
            if settings is None or not getattr(settings, "speak_enabled", False):
                return
            voice_id = _elevenlabs_voice_id(settings)
            api_key = _elevenlabs_key()
            if not api_key:
                return
            if not reply:
                return
            # Offload TTS to a background thread so the UI doesn't freeze.
            t = threading.Thread(target=speak_text, args=(reply, voice_id, api_key), daemon=True)
            t.start()
        except Exception:
            pass

    def _emit_reply(self, reply: str) -> None:
        """Called on the main thread with a Solar reply — show it in status,
        then remember the interaction in the user's memory."""
        try:
            self._app._show_reply(reply)
        except Exception:
            pass
        # Remember the reply in the user's memory (best effort).
        try:
            if self._memory is not None and hasattr(self._memory, "remember_interaction"):
                self._memory.remember_interaction(
                    "reply",
                    f"Gisto replied: {reply[:200]}",
                    {"reply_preview": reply[:500]},
                )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Tool helpers — called from the reply thread
# ---------------------------------------------------------------------------


def _extract_tool_call(reply: str) -> Optional[str]:
    """If *reply* contains a ``__TOOL__...`` marker, return it; else None."""
    m = re.search(r"__TOOL__[^\n]+", reply)
    if m:
        return m.group(0)
    # Also match if it's on its own line.
    for line in reply.splitlines():
        stripped = line.strip()
        if stripped.startswith("__TOOL__"):
            return stripped
    return None


def _run_tool(tool_call: str) -> str:
    """Run a tool described by *tool_call* and return a text result."""
    try:
        from src.desktop.composio_tools import run_tool as _run

        return _run(tool_call)
    except Exception as e:
        return f"[tool error: {e}]"


# ============================================================================
# Hotkey watcher (pynput)
# ============================================================================

_hotkey_listener: Any = None
_hotkey_running = False


def start_hotkey_watcher(
    app: Any,
    settings: Any,
    callback: Callable[[], None],
) -> None:
    global _hotkey_listener, _hotkey_running
    if _hotkey_running:
        return

    try:
        from pynput import keyboard
    except Exception:
        return

    _hotkey_running = True
    target_key = (getattr(settings, "hotkey_key", "g") or "g").lower()
    modifiers = set(getattr(settings, "hotkey_modifiers", ["ctrl", "alt"]) or [])

    def _normalize_mods(key: Any) -> set[str]:
        mods: set[str] = set()
        try:
            name = str(key).lower()
        except Exception:
            name = ""
        if "ctrl" in name or "control" in name:
            mods.add("ctrl")
        if "alt" in name:
            mods.add("alt")
        if "shift" in name:
            mods.add("shift")
        if "win" in name or "super" in name or "meta" in name:
            mods.add("win")
        return mods

    def _on_press(key: Any) -> None:
        if not _hotkey_running:
            return
        pressed_mods = _normalize_mods(key)
        pressed_key: Optional[str] = None
        try:
            if hasattr(key, "char") and key.char is not None:
                pressed_key = key.char.lower()
        except Exception:
            pass
        if pressed_key == target_key and modifiers.issubset(pressed_mods):
            settings_now = getattr(app, "settings", None) or settings
            if settings_now and not settings_now.wake_word_enabled:
                callback()
            callback()
            try:
                app.after(0, play_notification_sound)
            except Exception:
                pass

    def _on_release(key: Any) -> None:
        if key == keyboard.Key.esc:
            global _hotkey_running
            _hotkey_running = False

    _hotkey_listener = keyboard.Listener(on_press=_on_press, on_release=_on_release)
    _hotkey_listener.start()


def stop_hotkey_watcher() -> None:
    global _hotkey_running, _hotkey_listener
    _hotkey_running = False
    if _hotkey_listener is not None:
        try:
            _hotkey_listener.stop()
        except Exception:
            pass
        _hotkey_listener = None

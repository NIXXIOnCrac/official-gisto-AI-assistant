# Gisto — Desktop AI Assistant

A desktop AI assistant app for Windows. Speak or type to Gisto — it answers with voice (ElevenLabs TTS) and text, remembers you across sessions, and can look up places or run tools via Composio.

## What it is

Gisto is a single-user desktop app (CustomTkinter GUI) that runs in your system tray. You talk to it by:

- **Wake word:** say "gisto" — the mic listens, and when it hears the wake word a 4×4 square grid pops up on screen and pulses while Gisto thinks and replies.
- **Hotkey:** press `Ctrl+Alt+G` — same grid popup, same flow.
- **Type:** open the app window and type a message.

Gisto replies with text in a small toast, and speaks the reply aloud using ElevenLabs TTS (British male voice "George" by default). When you ask about places or locations, it uses the Google Places API for detailed info. When you ask it to make tasks or use other tools, it calls Composio (read + write on all tools).

The app ships with its own API keys built in — Nous/Solar Pro 4 for chat, ElevenLabs for voice, Google Places for location lookups, Composio for tools. You do not bring your own keys. Keys are XOR-obfuscated at build time and baked into the EXE; they are never plaintext in the source repo.

A passcode (`12041$` by default) gates the "API & Voice" settings section so users can change the TTS voice and toggle speech without seeing the underlying API keys.

## What it does

- **Voice chat.** Wake word or hotkey → mic captures → Solar Pro 4 replies → ElevenLabs TTS speaks aloud. Speak-on-by-default.
- **4×4 light grid.** Transparent popup with 16 rounded squares that pulse in sync while Gisto is working/speaking. Three states: Gisto-speaking, working, user-speaking — each with its own color. Customizable via color picker and presets.
- **Memory.** File-based per-user memory (facts, preferences, history). Loads before it acts, updates as it goes. First-run onboarding seeds it.
- **Tools.** Google Places for location lookups, Composio for tasks and other actions. Solar replies can request tool calls via `__TOOL__` markers.
- **Tray.** App starts open, closes to tray. Wake word/hotkey brings it forward. Window open moves grid into app; window close sends grid back to screen edge, vanishes after 10s silence.
- **Settings.** Grid size (slider), position (default top-right, draggable by double-click), colors (picker + presets), TTS voice (12 voices, picker behind passcode), speak on/off toggle. Grid setup first, quiz second in onboarding.

## Requirements

- Windows 10/11
- Python 3.11 (for building from source)
- PyInstaller 6.x (for building the EXE)

## Building from source

```bash
cd official-gisto-AI-assistant
pip install -r requirements.txt
# Set the 4 API keys as environment variables:
export NOUS_API_KEY=...
export ELEVENLABS_API_KEY=...
export GOOGLE_PLACES_API_KEY=...
export COMPOSIO_API_KEY=...
python scripts/build_keys.py   # injects XOR-obfuscated keys into _built_keys.py
python -m PyInstaller --onefile --name "Gisto" \
    --hidden-import pynput.keyboard._win32 \
    --hidden-import pystray._win32 \
    --hidden-import src.desktop._built_keys \
    --hidden-import src.desktop.keys \
    --hidden-import src.desktop.audio_watcher \
    --hidden-import src.desktop.composio_tools \
    --add-data "assets:gisto_assets" -w src/desktop/main.py
```

Output: `dist/Gisto.exe` (~170 MB).

### Environment variables (build time)

| Variable | Purpose |
|---|---|
| `NOUS_API_KEY` | Nous/Solar Pro 4 API key |
| `ELEVENLABS_API_KEY` | ElevenLabs TTS API key |
| `GOOGLE_PLACES_API_KEY` | Google Places API key |
| `COMPOSIO_API_KEY` | Composio tools API key |

`build_keys.py` reads these and writes `src/desktop/_built_keys.py` (gitignored, never committed). The EXE bundles `_built_keys.py` so keys travel with the app. On a clean checkout with no env vars, every key function returns empty string — the app starts but cannot call any API until keys are provided.

## Project structure

```
official-gisto-AI-assistant/
  src/desktop/          # desktop app (CustomTkinter GUI)
    main.py             # main window, grid popup, settings UI, tray/hotkey wiring
    audio_watcher.py    # wake-word + speech listener, Solar reply, ElevenLabs TTS
    tray.py             # system tray icon (pystray)
    settings.py         # AppSettings dataclass + load/save
    keys.py             # key access layer (placeholder-only committed version)
    _built_keys.py      # build-time generated secrets (gitignored, NOT committed)
    composio_tools.py   # Google Places + Composio tool executors
    memory.py           # per-user file-based memory (facts, prefs, history)
    onboarding.py       # first-run interview (skippable)
    wiring.py           # memory + onboarding wiring
    __init__.py
  src/                  # framework-layer code (CLI, Discord bot, integrations)
  assets/               # Gisto logos (full + circular tray icon)
  scripts/
    build_keys.py       # injects real keys into _built_keys.py at build time
    smoke_test.py       # verifies app constructs without crashing
    verify_keys.py      # verifies on-disk key blobs decode correctly
    verify_exe.py       # verifies EXE bundles correct _built_keys
    recover_keys.py     # key recovery helper (reads gitignored keys.py.bak)
  build.bat             # one-click rebuild (inject keys + PyInstaller)
  build/installer/      # Inno Setup installer script (compile on Windows with iscc)
  README.md
  CLAUDE.md             # build instructions for AI coding agents
  requirements.txt
  .gitignore
```

## Security

- **No plaintext keys in source.** `keys.py` committed to git contains only `REPLACE_ME` placeholders. Real keys live in `_built_keys.py` (gitignored) and the built EXE only.
- **XOR obfuscation.** Keys are XOR'd with a fixed byte (0xA7) and base64-encoded in `_built_keys.py`. This is obfuscation, not cryptography — a determined reverse-engineer with a debugger can recover keys from EXE memory at runtime. For stronger protection, route API calls through your own server.
- **Passcode lock.** The "API & Voice" settings section is behind a passcode (`12041$` by default). The passcode is hashed (SHA-256) and stored in `_built_keys.py` at build time — the plaintext passcode is never in the repo. Users can change the passcode in settings.
- **User data.** Memory files, settings, and Composio connection lists are per-user and stored on disk. No user data is sent anywhere except to the API endpoints the app calls (Nous, ElevenLabs, Google, Composio).

## Status

Desktop app v1 is complete and built. What's in the EXE:

- CustomTkinter window + system tray (pystray)
- Wake word "gisto" detection (speech_recognition) + hotkey `Ctrl+Alt+G` (pynput)
- 4×4 square-grid light panel with in-sync pulse, customizable colors/size/position
- Solar Pro 4 replies via Nous inference API
- ElevenLabs TTS spoken replies (George voice default, 12 voices selectable)
- Google Places API for location lookups
- Composio tools (read + write on all tools) for tasks and other actions
- File-based per-user memory + first-run onboarding
- Passcode-gated API/Voice settings section

Not yet done:

- End-to-end voice test with a live microphone (pending manual test on user's machine)
- Inno Setup installer `.exe` — `build/installer/setup.iss` is written; compile with Inno Setup (`iscc.exe`) on Windows to produce `GistoSetup-1.0.0.exe`
- Bundling `ffmpeg.exe` for ElevenLabs MP3→PCM decode via pydub (ffmpeg must be on PATH at runtime; without it TTS still works but sounds raw)

## Requirements.txt

```
customtkinter
pystray
pynput
SpeechRecognition
Pillow
pydub
elevenlabs
composio
composio-client
sounddevice
```

## Author

Youcef Salemtedj

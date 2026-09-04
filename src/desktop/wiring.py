"""Memory + onboarding wiring for GistoApp (desktop).

Loaded in ``GistoApp.__init__`` after the UI is built. Handles:
- loading (or creating) the per-user memory store
- running the first-run onboarding interview when the user has no memory yet
- feeding memory context into every Solar reply
- remembering interactions after each exchange
"""
from __future__ import annotations

from typing import Any

from src.desktop.memory import DEFAULT_MEMORY_DIR, UserMemory, load_memory
from src.desktop.onboarding import Onboarding
from src.desktop.settings import AppSettings, save_settings
from tkinter import simpledialog, messagebox


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

def _init_memory(app: GistoApp) -> None:
    """Load the user's memory store and run onboarding if it's a first run."""
    mem_dir = app._memory_dir
    mem = load_memory(mem_dir, "default")
    app._memory = mem
    app._onboarding_complete = not mem.is_empty()

    if mem.is_empty() and getattr(app.settings, "onboarding_enabled", True):
        # Defer the onboarding dialog to the mainloop so it can show a window.
        app.after(400, lambda: _run_onboarding_dialog(app, mem))
    else:
        app._onboarding_complete = True


def _run_onboarding_dialog(app: GistoApp, mem: UserMemory) -> None:
    """Run the onboarding interview in a small modal so the user can answer
    with a keyboard right after the app opens."""

    def ask(question: str) -> str:
        return simpledialog.askstring(
            "Gisto — getting to know you",
            question,
            parent=app,
        ) or ""

    def say(msg: str) -> None:
        app._status_label.configure(text=msg)

    ob = Onboarding(mem, ask=ask, say=say, skip_if_empty=True)
    result = ob.run()

    if result["ran"]:
        app._onboarding_complete = True
        app._status_label.configure(
            text="Onboarding done — Gisto is ready. Say the wake word or type."
        )
    else:
        app._onboarding_complete = True
        app._status_label.configure(
            text="Onboarding skipped — Gisto started with empty memory."
        )


# ---------------------------------------------------------------------------
# Memory context for Solar
# ---------------------------------------------------------------------------

def _get_memory_context(app: GistoApp, max_history: int = 8) -> str:
    """Return the current memory context string for pasting into a Solar prompt.
    Empty string when memory is not loaded yet."""
    if app._memory is None:
        return ""
    return app._memory.to_context_string(max_history=max_history)


# ---------------------------------------------------------------------------
# Remember an interaction
# ---------------------------------------------------------------------------

def _remember_interaction(
    app: GistoApp,
    kind: str,
    summary: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    if app._memory is None:
        return
    try:
        app._memory.remember_interaction(kind, summary, metadata)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# User-facing actions
# ---------------------------------------------------------------------------

def on_text_input(app: GistoApp, text: str) -> None:
    """Called when the user types a message in the input box."""
    app._input.delete(0, "end")
    app._status_label.configure(text=f"You: {text}")
    app.after(400, lambda: app._status_label.configure(text="Thinking..."))

    # Remember the user's side.
    _remember_interaction(
        app,
        "user_input",
        f"User said: {text}",
        {"text": text[:500]},
    )

    # Build a prompt that includes the memory context.
    ctx = _get_memory_context(app)
    prompt_parts = [ctx] if ctx else []
    prompt_parts.append(f"User said: {text}")
    full_prompt = "\n\n".join(prompt_parts)

    # Ask Solar (with tool support) and emit the reply.
    api_key = app._api_key if hasattr(app, "_api_key") else ""
    base_url = app._api_base if hasattr(app, "_api_base") else "https://inference-api.nousresearch.com/v1"

    def _do_reply() -> None:
        try:
            from src.desktop.audio_watcher import _solar_reply, _extract_tool_call, _run_tool

            first = _solar_reply(
                text,
                wake_only=False,
                tool_context=None,
                api_key=api_key,
                base_url=base_url,
            )
            if first is None:
                app._status_label.configure(text="No reply from Gisto.")
                return

            tool_call = _extract_tool_call(first)
            if tool_call:
                app._working_callback()
                tool_result = _run_tool(tool_call)
                reply = _solar_reply(
                    text,
                    wake_only=False,
                    tool_context=tool_result,
                    api_key=api_key,
                    base_url=base_url,
                ) or tool_result
            else:
                reply = first

            if reply:
                app._show_reply(reply)
                _remember_interaction(
                    app,
                    "reply",
                    f"Gisto replied to '{text[:80]}...'",
                    {"reply_preview": reply[:500]},
                )
                app._status_label.configure(text=f"Gisto: {reply[:120]}{'...' if len(reply) > 120 else ''}")
        except Exception as e:
            app._status_label.configure(text=f"Error: {e}")

    app.after(50, _do_reply)


# ---------------------------------------------------------------------------
# Re-onboard (from settings)
# ---------------------------------------------------------------------------

def _reopen_onboarding(app: GistoApp) -> None:
    """Clear memory and re-run onboarding (for the settings UI 'Re-run onboarding'
    button)."""
    if app._memory is None:
        return
    try:
        app._memory.set_facts({})
        for k in list(app._memory.get_prefs()):
            app._memory.forget_fact(k)
        app._memory.save()
    except Exception:
        pass
    app._onboarding_complete = False
    app.after(300, lambda: _run_onboarding_dialog(app, app._memory))

"""Onboarding interview for Gisto.

When a user runs Gisto for the first time (or when onboarding is enabled in
config and they have no memory yet), Gisto asks a short interview to seed the
user's memory with facts and preferences.

The interview is a conversation, not a giant form. It writes results into the
user's memory so they persist across restarts.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from src.memory import UserMemory


class Onboarding:
    """First-run interview that seeds a user's memory.

    Usage::

        from src.onboarding import Onboarding

        ob = Onboarding(
            memory=mem,
            ask=handler,       # function(text) -> user's reply
            emit=handler,      # function(text) -> print/send to user
        )
        ob.run()
    """

    def __init__(
        self,
        memory: UserMemory,
        ask: Callable[[str], str],
        emit: Callable[[str], None],
        *,
        timeout_seconds: int = 600,
    ) -> None:
        self.memory = memory
        self.ask = ask
        self.emit = emit
        self.timeout_seconds = timeout_seconds
        self._start: Optional[float] = None

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self) -> Dict[str, Any]:
        """Run the full onboarding interview.

        Returns a dict with what was learned and which steps completed.
        """
        self._start = time.time()
        result: Dict[str, Any] = {
            "completed_steps": [],
            "facts_added": 0,
            "preferences_added": 0,
            "notes": [],
        }

        self._emit_long(
            "Hi — I'm Gisto. Before we get going, I'd like to ask you a few "
            "questions so I can remember what matters about you. Nothing fancy, "
            "just enough that I'm not starting from zero every time we talk.\n"
        )

        self._step_welcome(result)
        if self._timed_out():
            return result

        self._step_what_for(result)
        if self._timed_out():
            return result

        self._step_work_and_goals(result)
        if self._timed_out():
            return result

        self._step_modules(result)
        if self._timed_out():
            return result

        self._step_integrations(result)
        if self._timed_out():
            return result

        self._step_limits(result)
        if self._timed_out():
            return result

        self._step_style(result)
        if self._timed_out():
            return result

        self._step_what_else(result)
        if self._timed_out():
            return result

        self._emit_long(
            "\nThanks — I've saved what you told me. If anything changes, just "
            "tell me and I'll update it. You can also tell me to forget something "
            "anytime.\n"
        )
        result["notes"].append("onboarding completed")
        return result

    # ------------------------------------------------------------------
    # Timeout guard
    # ------------------------------------------------------------------

    def _timed_out(self) -> bool:
        if self._start is None:
            return False
        return (time.time() - self._start) > self.timeout_seconds

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def _emit_long(self, text: str) -> None:
        self.emit(text)

    def _step_welcome(self, result: Dict[str, Any]) -> None:
        reply = self.ask(
            "First — what should I call you? (Just your name or whatever you "
            "want me to use.)"
        )
        if reply and reply.strip():
            self.memory.apply(reply.strip(), kind="fact", tags=["onboarding", "name"])
            result["facts_added"] += 1
            result["completed_steps"].append("name")
            self._emit_long(f"Got it — {reply.strip()}.\n")
        else:
            self.memory.apply("user hasn't told me their name yet", kind="fact", tags=["onboarding"])
            result["completed_steps"].append("name_skipped")

    def _step_what_for(self, result: Dict[str, Any]) -> None:
        self._emit_long(
            "What do you want to use Gisto for? You can be brief — personal stuff, "
            "agency work, both, or something else entirely."
        )
        reply = self.ask("What do you want to use Gisto for?")
        if reply and reply.strip():
            self.memory.apply(
                content=f"uses Gisto for: {reply.strip()}",
                kind="fact",
                tags=["onboarding", "purpose"],
            )
            result["facts_added"] += 1
            result["completed_steps"].append("purpose")

    def _step_work_and_goals(self, result: Dict[str, Any]) -> None:
        self._emit_long(
            "What kind of work are you doing? Anything you're trying to build or "
            "get done — I don't need a full resume, just enough that I understand "
            "what world I'm operating in."
        )
        reply = self.ask("What work are you doing / what are you trying to build?")
        if reply and reply.strip():
            self.memory.apply(
                content=f"work/context: {reply.strip()}",
                kind="fact",
                tags=["onboarding", "work"],
            )
            result["facts_added"] += 1

        self._emit_long("Anything specific you're trying to get done with me?")
        reply = self.ask("What are you trying to get done?")
        if reply and reply.strip():
            self.memory.apply(
                content=f"goals: {reply.strip()}",
                kind="fact",
                tags=["onboarding", "goals"],
            )
            result["facts_added"] += 1
            result["completed_steps"].append("goals")

    def _step_modules(self, result: Dict[str, Any]) -> None:
        self._emit_long(
            "Gisto has two capability modes — personal and agency. Personal is "
            "the assistant side: memory, notes, drafting, planning, research, "
            "chat. Agency adds the agency engine on top: lead finding, site "
            "building, outreach, client comms, project tracking.\n"
            "Which do you want on? You can say personal, agency, both, or neither "
            "for now."
        )
        reply = self.ask("Which modes do you want on — personal, agency, both, or neither?")
        if reply and reply.strip():
            lowered = reply.strip().lower()
            notes: List[str] = []
            if "both" in lowered or "agency" in lowered:
                self.memory.apply("wants agency mode", kind="preference", tags=["onboarding", "modules"])
                result["preferences_added"] += 1
                notes.append("agency")
            if "both" in lowered or "personal" in lowered:
                self.memory.apply("wants personal mode", kind="preference", tags=["onboarding", "modules"])
                result["preferences_added"] += 1
                notes.append("personal")
            if not notes:
                self.memory.apply(
                    "user didn't confirm any mode yet",
                    kind="preference",
                    tags=["onboarding", "modules"],
                )
                result["completed_steps"].append("modules_unsure")
            else:
                result["completed_steps"].append("modules")
            result["notes"].append(f"modules preference: {', '.join(notes) or 'none'}")

    def _step_integrations(self, result: Dict[str, Any]) -> None:
        self._emit_long(
            "You can connect Gisto to things like Discord, Slack, and Google "
            "Workspace — but only if you want to, and you'll need to supply your "
            "own keys for anything you turn on. Do you want to connect any of "
            "those? You can say yes, no, or list the ones you're interested in."
        )
        reply = self.ask(
            "Do you want to connect Discord, Slack, Google, or anything else? "
            "Say yes, no, or list the ones you're interested in."
        )
        if reply and reply.strip():
            self.memory.apply(
                content=f"integration interest: {reply.strip()}",
                kind="fact",
                tags=["onboarding", "integrations"],
            )
            result["facts_added"] += 1
            result["completed_steps"].append("integrations")

    def _step_limits(self, result: Dict[str, Any]) -> None:
        self._emit_long(
            "Is there anything I should not do, or anything I should clear with "
            "you before doing? Spending, purchases, access to anything sensitive — "
            "anything at all you want me to keep in mind."
        )
        reply = self.ask(
            "Anything I should not do, or clear with you first — spending, access, "
            "anything?"
        )
        if reply and reply.strip():
            self.memory.apply(
                content=f"limits: {reply.strip()}",
                kind="fact",
                tags=["onboarding", "limits"],
            )
            result["facts_added"] += 1
            result["completed_steps"].append("limits")

    def _step_style(self, result: Dict[str, Any]) -> None:
        self._emit_long(
            "How do you want me to talk? Concise, detailed, casual, formal — "
            "anything you prefer? You can skip this."
        )
        reply = self.ask("How do you want me to talk — concise, detailed, casual, formal?")
        if reply and reply.strip():
            self.memory.apply(
                content=f"style preference: {reply.strip()}",
                kind="preference",
                tags=["onboarding", "style"],
            )
            result["preferences_added"] += 1
            result["completed_steps"].append("style")

    def _step_what_else(self, result: Dict[str, Any]) -> None:
        self._emit_long(
            "Anything else you want me to remember about you — how you work, "
            "pet peeves, things you care about, whatever? This is optional."
        )
        reply = self.ask("Anything else you want me to remember?")
        if reply and reply.strip():
            self.memory.apply(
                content=f"misc: {reply.strip()}",
                kind="fact",
                tags=["onboarding", "misc"],
            )
            result["facts_added"] += 1
            result["completed_steps"].append("misc")


# ---------------------------------------------------------------------------
# Convenience runner
# ---------------------------------------------------------------------------

def run_onboarding_if_needed(
    memory: UserMemory,
    ask: Callable[[str], str],
    emit: Callable[[str], None],
    *,
    onboarding_enabled: bool = True,
) -> Dict[str, Any]:
    """Run onboarding if the user has no facts yet and it's enabled.

    Returns the onboarding result dict, or {"skipped": True, "reason": ...}
    if onboarding did not run.
    """
    if not onboarding_enabled:
        return {"skipped": True, "reason": "onboarding disabled in config"}

    facts = memory.facts
    prefs = memory.preferences
    if not facts and not prefs:
        return Onboarding(memory, ask, emit).run()

    return {"skipped": True, "reason": "user already has memory"}

"""Gisto desktop — first-run onboarding interview.

Conversation-style: Gisto asks, the user answers, Gisto follows up where
it makes sense, and when it has enough it writes the answers into the user's
memory as facts + preferences.

Runs once on first run (when the user has no memory yet) or when explicitly
re-run. Skippable — if the user says "skip" or closes the window, memory
stays empty and the app starts normally.

Spec origin: CLAUDE.md §9 (Onboarding), §6 (Memory).
"""
from __future__ import annotations

import re
import textwrap
from typing import Any, Callable, Optional

from src.desktop.memory import UserMemory


# ---------------------------------------------------------------------------
# The interview script
# ---------------------------------------------------------------------------

# Each item: (id, question_text, followup_fn | None).
# followup_fn(memory, answer) -> list[str] of extra questions to ask next,
# or None to continue the default sequence.

_ONBOARD_QUESTIONS = [
    (
        "use_case",
        "What do you want to use Gisto for? Things like: personal notes and "
        "planning, running an agency, outreach, content, research — or just "
        "chatting with a capable assistant. Give me the headline version.",
        None,
    ),
    (
        "work",
        "What do you actually do — your work, your projects, what you're "
        "trying to get done? A few sentences is plenty.",
        None,
    ),
    (
        "goals",
        "What are you trying to achieve right now — the real goals, not the "
        "polished version? What would make Gisto feel useful to you?",
        None,
    ),
    (
        "limits",
        "Anything Gisto should NOT do, or any hard limits — spending limits, "
        "access limits, topics to stay away from, anything you don't want it "
        "touching? If nothing, say so.",
        None,
    ),
    (
        "style",
        "How do you want Gisto to talk to you? Direct and brief, more detailed, "
        "calm and professional, casual — pick whatever fits. You can change this "
        "later.",
        None,
    ),
    (
        "anything_else",
        "Anything else worth remembering about how you work, what you like, or "
        "what you'd want Gisto to know on day one? If not, say skip.",
        None,
    ),
]


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

def _is_skip(answer: str) -> bool:
    a = answer.strip().lower()
    return a in {"skip", "s", "none", "nothing", "nope", "no", "n", "ignore", "later"}


def _clean_answer(answer: str) -> str:
    """Trim, collapse whitespace, drop trailing punctuation soup."""
    a = re.sub(r"\s+", " ", answer.strip())
    a = re.sub(r"[.?!]+\s*$", "", a)
    return a


# ---------------------------------------------------------------------------
# Interview runner (works headless at first run, before the GUI is fully up)
# ---------------------------------------------------------------------------

class Onboarding:
    """Runs the first-run interview and writes results into memory."""

    def __init__(
        self,
        memory: UserMemory,
        ask: Callable[[str], str],
        say: Callable[[str], None],
        skip_if_empty: bool = True,
    ) -> None:
        """
        Parameters
        ----------
        memory:
            The user's memory store to write results into.
        ask:
            Called with a question string; should block until the user replies
            and return their answer as a string. On the desktop app this can be
            a small modal dialog or a console prompt; in tests it's a function.
        say:
            Called to print/display status messages (intro, pauses, the final
            confirmation).
        skip_if_empty:
            If True and the user has no memory yet AND the interview is skipped,
            that's fine. If False we still attempt the interview.
        """
        self.memory = memory
        self.ask = ask
        self.say = say
        self.skip_if_empty = skip_if_empty
        self._facts: dict[str, Any] = {}
        self._prefs: dict[str, Any] = {}
        self._skipped = False

    # --- run ----------------------------------------------------------------

    def run(self) -> dict[str, Any]:
        """Run the interview. Returns a summary of what was collected."""
        self.say("Welcome. Let's get to know you — this is how Gisto starts "
                 "remembering what matters. You can skip any question with "
                 "'skip', and skip the whole thing with 'skip' on the first "
                 "question. This takes a couple of minutes.")

        if self._ask_first() is False:
            self._skipped = True
            self.say("Onboarding skipped. Gisto will start with an empty memory "
                     "— you can fill it in anytime by talking to it.")
            return {"ran": False, "skipped": True}

        for qid, question, _followup in _ONBOARD_QUESTIONS:
            if self._skipped:
                break
            self._ask_question(qid, question)

        self._finalize()
        return {
            "ran": True,
            "skipped": False,
            "facts_count": len(self._facts),
            "prefs_count": len(self._prefs),
        }

    # --- individual steps ---------------------------------------------------

    def _ask_first(self) -> bool:
        answer = _clean_answer(self.ask(_ONBOARD_QUESTIONS[0][1]))
        if _is_skip(answer):
            return False
        self._collect("use_case", answer)
        return True

    def _ask_question(self, qid: str, question: str) -> None:
        answer = _clean_answer(self.ask(question))
        if _is_skip(qid == "anything_else" and answer == "skip"):
            self._skipped = True
            return
        if _is_skip(answer):
            return
        self._collect(qid, answer)

    def _collect(self, key: str, answer: str) -> None:
        self._facts[key] = answer

    def _finalize(self) -> None:
        if not self._facts:
            return

        # Derive a couple of preferences from the answers.
        style = self._facts.get("style", "")
        self._prefs["communication_style"] = style or "calm and direct"

        use = self._facts.get("use_case", "").lower()
        if "agency" in use or "outreach" in use or "leads" in use or "client" in use:
            self._prefs["mode"] = "agency"
        elif "personal" in use or "notes" in use or "planning" in use or "chat" in use:
            self._prefs["mode"] = "personal"
        else:
            self._prefs["mode"] = "personal"

        # Write everything into memory in one shot.
        self.memory.set_facts(self._facts)
        for k, v in self._prefs.items():
            self.memory.set_pref(k, v)

        # Record the onboarding itself as a history entry so there's continuity.
        self.memory.remember_interaction(
            "onboarding",
            "First-run onboarding completed. Collected %d fact(s): %s"
            % (len(self._facts), ", ".join(self._facts.keys())),
            {"prefs": self._prefs},
        )

    # --- re-run -------------------------------------------------------------

    def rerun(self) -> dict[str, Any]:
        """Re-run onboarding from scratch (clears existing facts/prefs first)."""
        self.memory.set_facts({})
        for k in list(self.memory.get_prefs()):
            self.memory.forget_fact(k)
        return self.run()

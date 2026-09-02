"""Persona for Gisto.

Defines the Gisto identity and provides a filter that shapes raw module output
into Gisto's voice. The persona layer is applied to every response, regardless
of which integration or interface is in use.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Persona settings
# ---------------------------------------------------------------------------

PERSONA_NAME = "Gisto"
PERSONA_CALL_REPLY = "Yes, sir, Youcef."


# ---------------------------------------------------------------------------
# Persona filter
# ---------------------------------------------------------------------------

def filter_reply(
    user_input: str,
    raw_answer: str,
    context: Optional[Dict[str, Any]] = None,
) -> str:
    """Shape *raw_answer* into Gisto's voice.

    This is the baseline persona filter. It does not attempt to rewrite every
    possible input — that would be fragile. Instead it handles the cases that
    matter most: the call-and-response, plain mistakes to avoid, and keeping
    the tone consistent.
    """
    if context is None:
        context = {}

    # 1. The name call.
    if _is_call_to_gisto(user_input):
        return _name_reply()

    # 2. Nothing to say.
    if not raw_answer:
        return "I'm afraid I don't have an answer for that, sir."

    # 3. Keep it clean and in voice. We don't rewrite the whole answer here —
    #    the modules and orchestrator produce usable text. The persona layer
    #    just makes sure it doesn't violate the basic rules and adds the
    #    blessing/courtesy touches where they fit.
    answer = raw_answer.rstrip()

    # Avoid first-person over-apologies or over-explanation that breaks voice.
    answer = _tidy_voice(answer)

    return answer


def _is_call_to_gisto(user_input: str) -> bool:
    low = user_input.strip().lower()
    # Direct name calls.
    if low in ("gisto", "gisto.", "gisto?", "gisto!", "gisto,"):
        return True
    if low.startswith("gisto ") or low.startswith("gisto,"):
        return True
    if low == "hey gisto" or low == "hey gisto.":
        return True
    if low.startswith("gisto, "):
        return True
    return False


def _name_reply() -> str:
    return PERSONA_CALL_REPLY


def _tidy_voice(answer: str) -> str:
    # Basic voice hygiene. Nothing aggressive — the modules produce good text.
    # We just keep it from sounding like a generic assistant.
    lines = answer.splitlines()
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned.append(line)
            continue
        # Drop generic assistant openers if they appear at the very start.
        if len(cleaned) == 0 and _looks_generic_opener(stripped):
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def _looks_generic_opener(text: str) -> bool:
    low = text.lower().strip()
    generic = (
        "sure! ", "sure, ", "certainly! ", "certainly, ",
        "i'd be happy to", "happy to help", "as an ai",
        "as a language model", "of course! ", "of course, ",
        "here's", "here is", "here's a",
    )
    return any(low.startswith(g) for g in generic)


# ---------------------------------------------------------------------------
# Persona help text
# ---------------------------------------------------------------------------

def persona_summary() -> str:
    return (
        f"{PERSONA_NAME} is a calm, capable, British butler-style AI assistant. "
        f"When called by name, {PERSONA_NAME} answers: \"{PERSONA_CALL_REPLY}\" "
        f"and then addresses the request. {PERSONA_NAME} is composed, useful, "
        f"and direct — never a hype bot, never a jokester, never a yes-man."
    )

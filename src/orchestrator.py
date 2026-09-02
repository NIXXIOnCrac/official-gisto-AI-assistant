"""Orchestrator for Gisto.

The orchestrator is the main loop. It receives input from whatever integration
or interface is active, loads the user's memory, decides on a thread, runs the
enabled modules, produces a reply in Gisto's persona, and updates memory.

Usage::

    from src.orchestrator import Orchestrator

    orch = Orchestrator()
    reply = await orch.handle("user-1", "help me draft an email")
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from src.memory import UserMemory
from src.modules.base import Module
from src.modules.personal import PersonalModule
from src.modules.agency import AgencyModule
from src.threading import ThreadStore, ThreadContext


# ============================================================================
# Orchestrator
# ============================================================================

class Orchestrator:
    """Main loop for Gisto.

    Coordinates memory, threading, modules, and persona into one path from
    user input to reply.
    """

    def __init__(
        self,
        memory: UserMemory,
        threads: ThreadStore,
        persona: "Persona",
        modules: List[Module],
        *,
        fallback_module: Optional[Module] = None,
    ) -> None:
        self.memory = memory
        self.threads = threads
        self.persona = persona
        self.modules = modules
        self.fallback_module = fallback_module or PersonalModule()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def handle(
        self,
        user_id: str,
        user_input: str,
        *,
        source: Optional[str] = None,
        thread_id_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process one user input and return the orchestrator's reply.

        Returns a dict with:
        - ``answer``: the text Gisto should send back
        - ``thread_id``: the thread this belongs to
        - ``memory_actions``: list of (content, kind) tuples to store
        """
        if not user_input or not user_input.strip():
            return {
                "answer": "I didn't catch that — could you say it again?",
                "thread_id": self._current_thread_id(user_id, thread_id_override),
                "memory_actions": [],
                "source": source,
            }

        # 1. Load memory.
        memory_snapshot = self._load_memory_context(user_id)

        # 2. Decide thread.
        thread = self._decide_thread(user_id, user_input, thread_id_override)

        # 3. Build context for modules.
        context = self._build_context(user_id, user_input, thread, memory_snapshot)

        # 4. Run modules.
        module_result = self._run_modules(user_input, context)

        # 5. Build persona-filtered reply.
        answer = self.persona.filter_reply(user_input, module_result["answer"], context)

        # 6. Collect memory actions.
        memory_actions = module_result.get("memory_actions", [])
        memory_actions.append(("user asked: " + user_input.strip()[:200], "history"))

        # 7. Mark thread active.
        self.threads.mark_active(thread["id"], user_id)

        return {
            "answer": answer,
            "thread_id": thread["id"],
            "thread_title": thread["title"],
            "memory_actions": memory_actions,
            "source": source,
        }

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------

    def _load_memory_context(self, user_id: str) -> Dict[str, Any]:
        facts = self.memory.recent(kind="fact", limit=25)
        prefs = self.memory.recent(kind="preference", limit=15)
        threads = self.threads.list_for_user(user_id)
        return {
            "facts": [f.content for f in facts],
            "preferences": [p.content for p in prefs],
            "thread_summaries": [t.summary for t in threads],
            "thread_count": len(threads),
        }

    def _build_context(
        self,
        user_id: str,
        user_input: str,
        thread: Dict[str, Any],
        memory_snapshot: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "user_id": user_id,
            "memory": self.memory,
            "thread": thread,
            "thread_context": self.threads.context_for(thread["id"]),
            "memory_snapshot": memory_snapshot,
            "history": [],  # filled in by module result if needed
            "source": None,
        }

    # ------------------------------------------------------------------
    # Threading
    # ------------------------------------------------------------------

    def _current_thread_id(self, user_id: str, override: Optional[str]) -> str:
        if override:
            return override
        thread = self.threads.current_for(user_id)
        return thread["id"] if thread else self.threads.create(user_id, "general")["id"]

    def _decide_thread(
        self,
        user_id: str,
        user_input: str,
        override: Optional[str],
    ) -> Dict[str, Any]:
        if override:
            thread = self.threads.get(override)
            if thread:
                return thread
            # Fall back to creating a new thread if the override doesn't exist.
            return self.threads.create(user_id, "custom")

        current = self.threads.current_for(user_id)
        if current and self.threads.should_continue(current["id"], user_input):
            return current

        # New topic — let the thread store decide the title.
        title = self.threads.suggest_title(user_input)
        return self.threads.create(user_id, title)

    # ------------------------------------------------------------------
    # Modules
    # ------------------------------------------------------------------

    def _run_modules(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        for module in self.modules:
            if module.can_handle(user_input, context):
                result = module.handle(user_input, context)
                result.setdefault("module", module.name)
                return result
        # Fallback.
        result = self.fallback_module.handle(user_input, context)
        result.setdefault("module", self.fallback_module.name)
        return result

    # ------------------------------------------------------------------
    # Debug / introspection
    # ------------------------------------------------------------------

    def status(self, user_id: str) -> Dict[str, Any]:
        """Return a snapshot of the orchestrator state for one user."""
        current = self.threads.current_for(user_id)
        all_threads = self.threads.list_for_user(user_id)
        return {
            "user_id": user_id,
            "current_thread": current,
            "thread_count": len(all_threads),
            "memory_entry_count": len(self.memory.all_entries),
            "memory_facts": len(self.memory.facts),
            "memory_preferences": len(self.memory.preferences),
            "memory_history": len(self.memory.history),
        }

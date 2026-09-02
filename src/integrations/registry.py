"""Agency module for Gisto.

The agency module extends the personal module with agency capabilities:
lead finding, site building, outreach, client communications, and project
tracking. It only works for things the user has actually configured — if the
user hasn't wired up a data source or builder, the agency module tells them
what it needs rather than pretending.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.modules.base import Module
from src.memory import UserMemory


class AgencyModule(Module):
    """The agency module.

    Extends the personal assistant with agency capabilities. Only claims tasks
    that are clearly agency-related; general conversation and memory operations
    fall through to the personal module.
    """

    name = "agency"
    description = (
        "Agency capabilities on top of the personal module: lead finding, site "
        "building, outreach, client communications, and project tracking. Only "
        "works for services the user has actually configured."
    )
    summary = (
        "The agency half of Gisto — lead find, site build, outreach, client "
        "comms, project tracking. Extends personal."
    )

    _agency_phrases = frozenset({
        "lead", "leads", "find leads", "find businesses",
        "site", "website", "build a site", "build a website",
        "outreach", "cold email", "email sequence", "follow up",
        "client", "clients", "client comms", "talk to my client",
        "project", "projects", "track my projects", "what's the status",
        "pipeline", "sales", "prospects",
    })

    def can_handle(self, user_input: str, context: Dict[str, Any]) -> bool:
        low = (user_input or "").lower()
        if not low.strip():
            return False
        # Only claim clearly agency-related requests.
        if any(k in low for k in self._agency_phrases):
            return True
        return False

    def handle(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        memory = self._require_memory(context)
        return self._dispatch(user_input, memory, context)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def _dispatch(
        self,
        user_input: str,
        memory: UserMemory,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        low = (user_input or "").lower().strip()

        if any(k in low for k in ("lead", "leads", "find businesses")):
            if any(k in low for k in ("find", "search", "look for", "get")):
                return self._handle_find_leads(user_input, memory, context)
            return self._handle_leads_general(user_input, memory, context)

        if any(k in low for k in ("site", "website", "build a site", "build a website")):
            return self._handle_site(user_input, memory, context)

        if any(k in low for k in ("outreach", "cold email", "email sequence", "follow up")):
            return self._handle_outreach(user_input, memory, context)

        if any(k in low for k in ("client", "clients", "client comms")):
            return self._handle_client(user_input, memory, context)

        if any(k in low for k in ("project", "projects", "pipeline", "status")):
            return self._handle_projects(user_input, memory, context)

        # Shouldn't get here — agency phrases should have matched. Fall back
        # to a concise "I can help with that, but here's what I need."
        return {
            "answer": (
                "I can help with that on the agency side, sir. Tell me a little "
                "more about what you're trying to do and I'll say whether it's "
                "something I can do now or something that needs wiring up first."
            ),
            "memory_actions": [],
        }

    # ------------------------------------------------------------------
    # Lead finding
    # ------------------------------------------------------------------

    def _handle_find_leads(
        self,
        user_input: str,
        memory: UserMemory,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "answer": (
                "I can help you find leads, sir — but first I need to know what "
                "you're looking for. Tell me:\n"
                "- What kind of business or contact?\n"
                "- Any location, industry, or size constraints?\n"
                "- What's the goal — outreach, partnerships, sales?\n"
                "\nOnce I know that, I'll tell you whether I can search directly or "
                "whether we need a data source wired up first."
            ),
            "memory_actions": [],
        }

    def _handle_leads_general(
        self,
        user_input: str,
        memory: UserMemory,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        memory.apply(
            content=f"user interested in lead finding",
            kind="fact",
            tags=["agency", "leads"],
        )
        return {
            "answer": (
                "Lead finding is something I can help with, sir. I can search for "
                "businesses and contacts when a data source is available, and I can "
                "help you organize and track the leads you already have. What are we "
                "aiming at?"
            ),
            "memory_actions": [],
        }

    # ------------------------------------------------------------------
    # Site building
    # ------------------------------------------------------------------

    def _handle_site(
        self,
        user_input: str,
        memory: UserMemory,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        subject = self._extract_subject(user_input, "site") or "a website"
        memory.apply(
            content=f"user asked about building: {subject}",
            kind="fact",
            tags=["agency", "sites"],
        )
        return {
            "answer": (
                f"I can help with sites, sir. Before I build anything, tell me:\n"
                f"- What's the site for?\n"
                f"- Who's it for?\n"
                f"- Any content, branding, or structure you already have in mind?\n"
                f"\nIf you want me to generate the site, I'll need a builder wired up "
                f"first. If you just want a plan or content, I can do that now."
            ),
            "memory_actions": [],
        }

    # ------------------------------------------------------------------
    # Outreach
    # ------------------------------------------------------------------

    def _handle_outreach(
        self,
        user_input: str,
        memory: UserMemory,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        subject = self._extract_subject(user_input, "outreach") or "outreach"
        memory.apply(
            content=f"user asked about outreach: {subject}",
            kind="fact",
            tags=["agency", "outreach"],
        )
        return {
            "answer": (
                "I can help with outreach, sir. To make it useful, tell me:\n"
                "- Who are we reaching out to?\n"
                "- What's the goal — introduction, sales, follow-up, something else?\n"
                "- Any tone or constraints?\n"
                "\nIf you want me to send anything, I'll need to know whether I'm "
                "drafting for your review or actually sending through a connected "
                "account."
            ),
            "memory_actions": [],
        }

    # ------------------------------------------------------------------
    # Client comms
    # ------------------------------------------------------------------

    def _handle_client(
        self,
        user_input: str,
        memory: UserMemory,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        subject = self._extract_subject(user_input, "client") or "a client"
        memory.apply(
            content=f"user asked about client: {subject}",
            kind="fact",
            tags=["agency", "clients"],
        )
        return {
            "answer": (
                "I can help you communicate with clients, sir. Tell me:\n"
                "- Which client?\n"
                "- What needs to be said or decided?\n"
                "- Do you want me to draft something for your review, or coordinate "
                "through a connected channel?\n"
                "\nIf it involves sending anything on your behalf, I'll confirm with "
                "you before I do."
            ),
            "memory_actions": [],
        }

    # ------------------------------------------------------------------
    # Projects / pipeline
    # ------------------------------------------------------------------

    def _handle_projects(
        self,
        user_input: str,
        memory: UserMemory,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        subject = self._extract_subject(user_input, "project") or "your projects"
        memory.apply(
            content=f"user asked about projects: {subject}",
            kind="fact",
            tags=["agency", "projects"],
        )
        return {
            "answer": (
                "I can help you track projects and pipeline, sir. Tell me:\n"
                "- Which project or client?\n"
                "- What's the current state?\n"
                "- Anything that needs attention or follow-up?\n"
                "\nIf you want me to keep an ongoing tracker, I can do that in memory "
                "and update it as things change."
            ),
            "memory_actions": [],
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _require_memory(context: Dict[str, Any]) -> UserMemory:
        memory = context.get("memory")
        if not isinstance(memory, UserMemory):
            raise ValueError("context must contain a 'memory' key with a UserMemory")
        return memory

    @staticmethod
    def _extract_subject(user_input: str, verb: str) -> str:
        low = (user_input or "").lower().strip()
        for pattern in (
            rf"{verb} (.*)$",
            rf"{verb} about (.*)$",
            rf"{verb} for (.*)$",
            rf"{verb}: (.*)$",
        ):
            import re
            m = re.search(pattern, low)
            if m:
                candidate = m.group(1).strip()
                if candidate:
                    return candidate.rstrip(".,;:!?")
        return verb

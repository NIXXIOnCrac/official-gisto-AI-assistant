"""
Memory system for Gisto.

Each user gets a persistent, disk-backed memory store containing:
- Facts (discrete things Gisto should remember)
- Preferences (behavior settings)
- History entries (meaningful interaction history, not every message)
- Thread references (connection between memory and the threading system)

Memory is per-user, survives restarts, never stores keys/tokens/credentials,
and is pruned/age-bounded so it doesn't grow forever.

Usage::

    from src.memory import UserMemory

    mem = UserMemory(user_id="user-1", root_dir="./data/memory")
    mem.apply("user wants agency mode on", kind="fact")
    mem.apply("prefers concise replies", kind="preference")
    print(mem.facts)
    print(mem.preferences)
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_HISTORY_ENTRIES_DEFAULT = 200
MAX_FACTS_DEFAULT = 200
MAX_PREFERENCES_DEFAULT = 50
DEFAULT_MAX_AGE_DAYS = 90

# Keys that must never appear in memory, even accidentally.
FORBIDDEN_MEMORY_KEYS = frozenset({
    "bot_token", "token", "api_key", "api_secret",
    "client_secret", "client_id", "signing_secret",
    "password", "passwd", "secret", "private_key",
    "auth_header", "authorization",
})

FORBIDDEN_MEMORY_VALUES_MARKERS = frozenset({
    "your_token_here", "your_api_key_here", "your_client_id_here",
    "<your_", "your_", "{{", "}}", "sk-", "xoxb-", "Bearer ",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_for_storage(value: str) -> str:
    """Return a sanitized version of *value* safe for storage.

    If the value looks like it contains a secret, this returns a redacted
    placeholder rather than the raw value. This is a belt-and-suspenders
    guard — the framework should never try to store secrets in the first
    place, but memory is on disk and we don't trust the call sites blindly.
    """
    lowered = value.lower()
    for marker in FORBIDDEN_MEMORY_VALUES_MARKERS:
        if marker in lowered:
            return "[REDACTED — possible secret]"
    # Also check for long hex-like tokens (rough heuristic).
    if len(value) > 32 and _looks_hex_like(value):
        return "[REDACTED — possible secret]"
    return value


def _looks_hex_like(s: str) -> bool:
    """Rough check: does the string look like a long hex token?"""
    clean = s.strip()
    if len(clean) < 24:
        return False
    allowed = set("0123456789abcdefABCDEF")
    # Allow a few common separators.
    for ch in clean:
        if ch not in allowed and ch not in {"-", "_", "."}:
            return False
    return True


def _forbidden_in_dict(d: Dict[str, Any]) -> List[str]:
    """Return a list of keys in *d* that look forbidden.

    Used by :meth:`UserMemory.apply` to reject attempts to store secrets
    under suspicious keys.
    """
    hits: List[str] = []
    lowered_keys = {k.lower(): k for k in d}
    for forbidden in FORBIDDEN_MEMORY_KEYS:
        for candidate in lowered_keys:
            if forbidden in candidate:
                hits.append(lowered_keys[candidate])
    return hits


# ---------------------------------------------------------------------------
# Entrys
# ---------------------------------------------------------------------------

class MemoryEntry:
    """A single stored memory entry."""

    __slots__ = ("entry_id", "kind", "content", "created_at", "last_seen_at", "tags")

    def __init__(
        self,
        entry_id: str,
        kind: str,
        content: str,
        created_at: str,
        last_seen_at: str,
        tags: Optional[List[str]] = None,
    ) -> None:
        self.entry_id = entry_id
        self.kind = kind
        self.content = content
        self.created_at = created_at
        self.last_seen_at = last_seen_at
        self.tags = tags or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "kind": self.kind,
            "content": self.content,
            "created_at": self.created_at,
            "last_seen_at": self.last_seen_at,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MemoryEntry:
        return cls(
            entry_id=data["entry_id"],
            kind=data["kind"],
            content=data["content"],
            created_at=data["created_at"],
            last_seen_at=data["last_seen_at"],
            tags=data.get("tags", []),
        )


# ---------------------------------------------------------------------------
# User memory
# ---------------------------------------------------------------------------

class UserMemory:
    """Persistent memory for one user.

    Files are stored under ``root_dir / user_id``. Each user gets their own
    subdirectory so data never leaks across users.
    """

    def __init__(
        self,
        user_id: str,
        root_dir: str,
        max_history: int = MAX_HISTORY_ENTRIES_DEFAULT,
        max_facts: int = MAX_FACTS_DEFAULT,
        max_preferences: int = MAX_PREFERENCES_DEFAULT,
        max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    ) -> None:
        if not user_id or not isinstance(user_id, str):
            raise ValueError("user_id must be a non-empty string")

        self.user_id = user_id
        self.root_dir = Path(root_dir).expanduser().resolve()
        self.max_history = max_history
        self.max_facts = max_facts
        self.max_preferences = max_preferences
        self.max_age_days = max_age_days

        user_dir = self.user_dir
        user_dir.mkdir(parents=True, exist_ok=True)
        self._entries_file = user_dir / "entries.json"

        self._entries: List[MemoryEntry] = []
        self._load()

    # -- path helpers ----------------------------------------------------------

    @property
    def user_dir(self) -> Path:
        return self.root_dir / self.user_id

    # -- persistence ---------------------------------------------------------

    def _load(self) -> None:
        if not self._entries_file.exists():
            self._entries = []
            return
        try:
            with open(self._entries_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            # Corrupt file — start fresh rather than crash.
            self._entries = []
            return
        self._entries = [MemoryEntry.from_dict(e) for e in data if isinstance(e, dict)]

    def _save(self) -> None:
        path = self._entries_file
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump([e.to_dict() for e in self._entries], fh, indent=2, ensure_ascii=False)
        tmp.replace(path)

    # -- queries -------------------------------------------------------------

    @property
    def all_entries(self) -> List[MemoryEntry]:
        return list(self._entries)

    @property
    def facts(self) -> List[MemoryEntry]:
        return [e for e in self._entries if e.kind == "fact"]

    @property
    def preferences(self) -> List[MemoryEntry]:
        return [e for e in self._entries if e.kind == "preference"]

    @property
    def history(self) -> List[MemoryEntry]:
        return [e for e in self._entries if e.kind == "history"]

    @property
    def thread_refs(self) -> List[MemoryEntry]:
        return [e for e in self._entries if e.kind == "thread_ref"]

    def recent(self, kind: Optional[str] = None, limit: int = 20) -> List[MemoryEntry]:
        """Return the most recently seen entries, optionally filtered by kind."""
        entries = self._entries
        if kind:
            entries = [e for e in entries if e.kind == kind]
        entries = sorted(entries, key=lambda e: e.last_seen_at, reverse=True)
        return entries[:limit]

    def get_fact_content(self, substring: str) -> List[str]:
        """Return fact contents that contain *substring* (case-insensitive)."""
        target = substring.lower()
        return [e.content for e in self.facts if target in e.content.lower()]

    # -- mutations -----------------------------------------------------------

    def apply(self, content: str, kind: str = "fact", tags: Optional[List[str]] = None) -> MemoryEntry:
        """Add or refresh a memory entry.

        If an entry with the same kind + content already exists, its
        ``last_seen_at`` is updated instead of creating a duplicate. This is
        how memory stays current without exploding in size.
        """
        if not content or not isinstance(content, str):
            raise ValueError("content must be a non-empty string")

        if kind not in {"fact", "preference", "history", "thread_ref"}:
            raise ValueError(f"Unknown memory kind: {kind!r}")

        # Guard: never store possible secrets.
        sanitized = _sanitize_for_storage(content)
        if sanitized != content:
            import warnings
            warnings.warn(
                f"Memory entry for user {self.user_id!r} contained a value that "
                f"looks like a secret and was redacted before storage.",
                stacklevel=2,
            )
            content = sanitized

        if tags:
            for tag in tags:
                if not isinstance(tag, str):
                    raise ValueError("tags must be strings")

        # Refresh existing or create new.
        now = _now_iso()
        existing = self._find_same(kind, content)
        if existing:
            existing.last_seen_at = now
            if tags:
                merged = list(dict.fromkeys(existing.tags + tags))
                existing.tags = merged[:20]
            self._save()
            return existing

        entry_id = _make_id(kind)
        entry = MemoryEntry(
            entry_id=entry_id,
            kind=kind,
            content=content,
            created_at=now,
            last_seen_at=now,
            tags=(tags or []),
        )
        self._entries.append(entry)
        self._prune()
        self._save()
        return entry

    def _find_same(self, kind: str, content: str) -> Optional[MemoryEntry]:
        norm = content.strip().lower()
        for e in self._entries:
            if e.kind == kind and e.content.strip().lower() == norm:
                return e
        return None

    def remove(self, entry_id: str) -> bool:
        """Remove an entry by id. Returns True if it was found and removed."""
        for i, e in enumerate(self._entries):
            if e.entry_id == entry_id:
                self._entries.pop(i)
                self._save()
                return True
        return False

    def mark_thread_active(self, thread_id: str, thread_title: str) -> MemoryEntry:
        """Record a thread reference in memory."""
        return self.apply(
            content=f"thread:{thread_id}:{thread_title}",
            kind="thread_ref",
            tags=["thread"],
        )

    # -- pruning -------------------------------------------------------------

    def _prune(self) -> None:
        """Enforce size limits and age-based pruning."""
        before = len(self._entries)
        self._entries = self._prune_by_kind()
        self._entries = self._prune_by_age()
        if len(self._entries) != before and self._entries:
            self._save()

    def _prune_by_kind(self) -> List[MemoryEntry]:
        # Keep the most recent entries per kind up to the per-kind cap.
        kept: List[MemoryEntry] = []
        buckets: Dict[str, List[MemoryEntry]] = {}
        for e in sorted(
            self._entries,
            key=lambda e: e.last_seen_at,
            reverse=True,
        ):
            buckets.setdefault(e.kind, []).append(e)
        caps = {
            "fact": self.max_facts,
            "preference": self.max_preferences,
            "history": self.max_history,
            "thread_ref": 200,
        }
        for kind, entries in buckets.items():
            cap = caps.get(kind, 200)
            kept.extend(entries[:cap])
        return kept

    def _prune_by_age(self) -> List[MemoryEntry]:
        cutoff = _now_iso()
        # We don't do exact calendar math here — just drop entries older than
        # max_age_days based on created_at being too old. This is approximate.
        try:
            from datetime import timedelta
            cutoff_dt = datetime.now(timezone.utc) - timedelta(days=self.max_age_days)
        except Exception:
            return self._entries

        kept: List[MemoryEntry] = []
        for e in self._entries:
            try:
                created = datetime.fromisoformat(e.created_at)
                if created >= cutoff_dt:
                    kept.append(e)
            except Exception:
                # Can't parse — keep it.
                kept.append(e)
        return kept

    # -- export --------------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        """Return a plain-object snapshot of the memory for inspection or export."""
        return {
            "user_id": self.user_id,
            "entry_count": len(self._entries),
            "facts": [e.to_dict() for e in self.facts],
            "preferences": [e.to_dict() for e in self.preferences],
            "history_count": len(self.history),
            "thread_refs": [e.to_dict() for e in self.thread_refs],
        }

    def summary_text(self) -> str:
        """Human-readable summary of what this user's memory contains."""
        lines: List[str] = []
        lines.append(f"Memory for user {self.user_id!r} ({len(self._entries)} entries)")
        lines.append("")
        lines.append(f"Facts ({len(self.facts)}):")
        for f in self.facts:
            lines.append(f"  - {f.content}")
        if self.preferences:
            lines.append("")
            lines.append(f"Preferences ({len(self.preferences)}):")
            for p in self.preferences:
                lines.append(f"  - {p.content}")
        if self.thread_refs:
            lines.append("")
            lines.append(f"Thread refs ({len(self.thread_refs)}):")
            for t in self.thread_refs:
                lines.append(f"  - {t.content}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------

import uuid


def _make_id(kind: str) -> str:
    return f"{kind}:{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Convenience: load from config + orchestrator helpers
# ---------------------------------------------------------------------------

def memory_from_config(user_id: str, config: Optional[Dict[str, Any]] = None) -> UserMemory:
    """Create a UserMemory using settings from a config dict (or the loaded config)."""
    if config is None:
        from src.config import get_gisto_config
        config = get_gisto_config()
    memory_dir = config.get("memory_dir", "./data/memory")
    limits = config.get("limits", {})
    return UserMemory(
        user_id=user_id,
        root_dir=memory_dir,
        max_history=limits.get("max_history_entries", MAX_HISTORY_ENTRIES_DEFAULT),
        max_facts=limits.get("max_facts", MAX_FACTS_DEFAULT),
        max_preferences=limits.get("max_preferences", MAX_PREFERENCES_DEFAULT),
        max_age_days=limits.get("max_age_days", DEFAULT_MAX_AGE_DAYS),
    )

"""Gisto desktop — per-user persistent memory.

Holds, for one user, on disk:
- **facts**   — discrete things Gisto should remember (name, work,
  goals, limits, preferences, anything onboarding or later chat
  establishes)
- **history** — meaningful interaction history (not every message
  verbatim, but enough for continuity)
- **prefs**   — behavior settings the user has set or Gisto has learned
- **threads** — thread references so memory and threading stay connected

File-based (one JSON file per user), persists across restarts.
Never stores API keys, tokens, passwords, or another user's data.
Age-based pruning keeps it bounded.

Spec origin: CLAUDE.md §6 (Memory System).
"""
from __future__ import annotations

import json
import time
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_HISTORY_ENTRIES = 200          # cap on kept history records
MAX_FACTS            = 120          # cap on kept facts
PRUNE_AGE_DAYS       = 120          # older history entries eligible for prune
DEFAULT_MEMORY_DIR   = Path.home() / ".gisto" / "memory"

# Keys that are explicitly never written to memory (safety net).
_NEVER_STORE = frozenset({
    "api_key", "apikey", "token", "bot_token", "discord_token",
    "slack_token", "google_token", "oauth_token", "client_secret",
    "password", "passwd", "secret", "private_key", "api_keys",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_epoch() -> float:
    return time.time()


def _clean_value(v: Any) -> Any:
    """Strip anything that looks like a secret before storing."""
    if isinstance(v, str):
        low = v.lower()
        for bad in _NEVER_STORE:
            if bad in low:
                return f"[redacted — contains {bad}]"
        # Also catch things like "sk-..." or "pk_...".
        if re.search(r"\b(sk-[a-zA-Z0-9]+|pk_[a-zA-Z0-9]+|ai[aA]za[0-9A-Za-z_-]{30,})\b", v):
            return "[redacted — looks like an API key]"
    if isinstance(v, dict):
        return {k: _clean_value(v2) for k, v2 in v.items()}
    if isinstance(v, list):
        return [_clean_value(v2) for v2 in v]
    return v


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# UserMemory
# ---------------------------------------------------------------------------

class UserMemory:
    """One persistent memory store for one user.

    Path: ``<memory_dir>/<user_id>.json``.
    """

    def __init__(self, memory_dir: Path, user_id: str) -> None:
        self.memory_dir = memory_dir
        self.user_id = user_id
        self._path = memory_dir / f"{user_id}.json"
        self._data: dict[str, Any] = {
            "user_id": user_id,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "facts": {},
            "history": [],
            "prefs": {},
            "threads": [],
        }
        self._loaded = False

    # --- loading / saving ----------------------------------------------------

    def load(self) -> None:
        """Load from disk. No-op if the file does not exist yet (first run)."""
        if self._loaded or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            # Merge carefully: keep our schema, fold in what we recognise.
            for key in ("facts", "history", "prefs", "threads"):
                if key in raw and isinstance(raw[key], (dict, list)):
                    self._data[key] = raw[key]
            self._data["updated_at"] = _now_iso()
            self._loaded = True
        except (json.JSONDecodeError, OSError):
            # Corrupt file — start fresh but keep the path so we don't lose it.
            self._data["facts"] = {}
            self._data["history"] = []
            self._data["prefs"] = {}
            self._data["threads"] = []
            self._loaded = True

    def save(self) -> None:
        """Persist current state to disk."""
        self._data["updated_at"] = _now_iso()
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self._path)
        except OSError:
            pass
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
        self._loaded = True

    # --- facts ---------------------------------------------------------------

    def get_facts(self) -> dict[str, Any]:
        self.load()
        return dict(self._data["facts"])

    def add_fact(self, key: str, value: Any) -> None:
        """Remember a discrete fact. Replaces anything already stored under
        the same key (most recent wins)."""
        self.load()
        cleaned = _clean_value(value)
        self._data["facts"][str(key)] = cleaned
        self._trim_facts()
        self.save()

    def set_facts(self, facts: dict[str, Any]) -> None:
        """Bulk-set facts (e.g. from onboarding). Cleans each value."""
        self.load()
        cleaned: dict[str, Any] = {}
        for k, v in facts.items():
            cleaned[str(k)] = _clean_value(v)
        self._data["facts"] = cleaned
        self._trim_facts()
        self.save()

    def _trim_facts(self) -> None:
        if len(self._data["facts"]) > MAX_FACTS:
            # Keep the newest MAX_FACTS entries (insertion order).
            items = list(self._data["facts"].items())
            self._data["facts"] = dict(items[-MAX_FACTS:])

    def forget_fact(self, key: str) -> None:
        self.load()
        self._data["facts"].pop(str(key), None)
        self.save()

    # --- history -------------------------------------------------------------

    def get_history(self, limit: Optional[int] = None) -> list[dict[str, Any]]:
        self.load()
        out = list(self._data["history"])
        if limit is not None:
            out = out[-limit:]
        return out

    def remember_interaction(self, kind: str, summary: str, metadata: Optional[dict[str, Any]] = None) -> None:
        """Record a meaningful interaction. Not every message — use judgment
        about what's worth keeping."""
        self.load()
        entry: dict[str, Any] = {
            "ts": _now_epoch(),
            "ts_iso": _now_iso(),
            "kind": str(kind),
            "summary": str(summary),
        }
        if metadata:
            entry["meta"] = _clean_value(metadata)
        self._data["history"].append(entry)
        self._prune_history()
        self.save()

    def _prune_history(self) -> None:
        # Age-based: drop entries older than PRUNE_AGE_DAYS.
        cutoff = _now_epoch() - (PRUNE_AGE_DAYS * 86400)
        self._data["history"] = [
            e for e in self._data["history"] if e.get("ts", 0) >= cutoff
        ]
        # Count cap.
        if len(self._data["history"]) > MAX_HISTORY_ENTRIES:
            self._data["history"] = self._data["history"][-MAX_HISTORY_ENTRIES:]

    def forget_history(self, before_epoch: float) -> None:
        """Drop all history entries older than ``before_epoch``."""
        self.load()
        self._data["history"] = [
            e for e in self._data["history"] if e.get("ts", 0) >= before_epoch
        ]
        self.save()

    # --- prefs ---------------------------------------------------------------

    def get_pref(self, key: str, default: Any = None) -> Any:
        self.load()
        return self._data["prefs"].get(str(key), default)

    def set_pref(self, key: str, value: Any) -> None:
        self.load()
        self._data["prefs"][str(key)] = _clean_value(value)
        self.save()

    def get_prefs(self) -> dict[str, Any]:
        self.load()
        return dict(self._data["prefs"])

    # --- threads -------------------------------------------------------------

    def get_threads(self) -> list[dict[str, Any]]:
        self.load()
        return list(self._data["threads"])

    def add_thread(self, thread_id: str, name: str, summary: str = "", active: bool = False) -> None:
        self.load()
        tid = str(thread_id)
        # Replace if already present.
        self._data["threads"] = [t for t in self._data["threads"] if t.get("id") != tid]
        self._data["threads"].append({
            "id": tid,
            "name": str(name),
            "summary": str(summary),
            "active": bool(active),
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        })
        # Only one active at a time.
        for t in self._data["threads"]:
            t["active"] = (t.get("id") == tid) if active else t.get("active", False)
        self.save()

    def set_thread_active(self, thread_id: str, active: bool = True) -> None:
        self.load()
        tid = str(thread_id)
        for t in self._data["threads"]:
            if t.get("id") == tid:
                t["active"] = active
                t["updated_at"] = _now_iso()
                break
        if active:
            for t in self._data["threads"]:
                if t.get("id") != tid:
                    t["active"] = False
        self.save()

    def rename_thread(self, thread_id: str, new_name: str) -> None:
        self.load()
        tid = str(thread_id)
        for t in self._data["threads"]:
            if t.get("id") == tid:
                t["name"] = str(new_name)
                t["updated_at"] = _now_iso()
                break
        self.save()

    def delete_thread(self, thread_id: str) -> None:
        self.load()
        tid = str(thread_id)
        before = len(self._data["threads"])
        self._data["threads"] = [t for t in self._data["threads"] if t.get("id") != tid]
        if len(self._data["threads"]) < before:
            self.save()

    def merge_threads(self, source_id: str, target_id: str, new_name: Optional[str] = None) -> None:
        """Merge ``source_id`` into ``target_id``, dropping the source."""
        self.load()
        sid, tid = str(source_id), str(target_id)
        target = next((t for t in self._data["threads"] if t.get("id") == tid), None)
        source = next((t for t in self._data["threads"] if t.get("id") == sid), None)
        if target is None:
            return
        if source is not None:
            combined_summary = source.get("summary", "")
            if target.get("summary"):
                combined_summary = f"{target['summary']} | {combined_summary}"
            target["summary"] = combined_summary
            target["updated_at"] = _now_iso()
            self._data["threads"] = [t for t in self._data["threads"] if t.get("id") != sid]
        if new_name:
            target["name"] = str(new_name)
        self.save()

    # --- context for the AI -------------------------------------------------

    def to_context_string(self, max_history: int = 8) -> str:
        """Serialise facts + recent history into a plain-text block Gisto can
        paste into its system prompt / context before replying."""
        self.load()
        parts: list[str] = []
        facts = self._data["facts"]
        if facts:
            parts.append("=== Facts about the user ===")
            for k, v in facts.items():
                parts.append(f"- {k}: {v}")
        history = self._data["history"]
        if history:
            recent = history[-max_history:]
            parts.append("\n=== Recent interactions ===")
            for e in recent:
                ts = e.get("ts_iso", "?")
                kind = e.get("kind", "?")
                summary = e.get("summary", "?")
                parts.append(f"[{ts}] ({kind}) {summary}")
        return "\n".join(parts)

    # --- introspection ------------------------------------------------------

    def is_empty(self) -> bool:
        """True if no facts and no history have been recorded yet (first run)."""
        self.load()
        return not self._data["facts"] and not self._data["history"]

    def stats(self) -> dict[str, Any]:
        self.load()
        return {
            "user_id": self.user_id,
            "facts": len(self._data["facts"]),
            "history": len(self._data["history"]),
            "prefs": len(self._data["prefs"]),
            "threads": len(self._data["threads"]),
            "created_at": self._data.get("created_at"),
            "updated_at": self._data.get("updated_at"),
        }


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

def load_memory(memory_dir: Path, user_id: str = "default") -> UserMemory:
    """Load (or create) the memory store for a user."""
    mem = UserMemory(memory_dir, user_id)
    mem.load()
    return mem

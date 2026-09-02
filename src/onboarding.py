"""Threading system for Gisto.

Each user has a set of threads. Threads carry their own recent context, while
the user's broader memory (facts, prefs, ongoing projects) is shared across
threads.

Threads are created automatically when the topic shifts, but the user can also
rename, merge, split, list, and jump into threads manually.
"""

from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.memory import UserMemory


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_thread_id() -> str:
    return f"thread:{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Title suggestion
# ---------------------------------------------------------------------------

def suggest_title(user_input: str) -> str:
    """Suggest a short thread title from *user_input*."""
    cleaned = _clean_for_title(user_input)
    if not cleaned:
        return "general"
    # Take the first meaningful chunk.
    words = cleaned.split()
    if len(words) <= 6:
        return cleaned[:60] or "general"
    head = " ".join(words[:6])
    return head[:60] or "general"


def _clean_for_title(text: str) -> str:
    text = text.strip()
    # Drop very common openers.
    low = text.lower()
    for prefix in (
        "how do i", "how can i", "how to", "what is", "what are",
        "can you", "could you", "would you", "i want to", "i need to",
        "help me", "i'm trying to", "i'm trying", "i want", "i need",
        "tell me", "explain", "can you tell me", "i was wondering",
        "just", "so", "hey", "hi", "hello", "gisto", "hey gisto",
    ):
        if low.startswith(prefix):
            text = text[len(prefix):].strip()
            low = text.lower()
    # Strip trailing punctuation and question marks for a cleaner title.
    text = re.sub(r"[^a-z0-9\s]", " ", low)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    return text


# ---------------------------------------------------------------------------
# Thread metadata
# ---------------------------------------------------------------------------

class Thread:
    """One conversation thread for one user."""

    def __init__(
        self,
        thread_id: str,
        user_id: str,
        title: str,
        created_at: Optional[str] = None,
        last_active_at: Optional[str] = None,
        context: Optional[List[str]] = None,
        summary: str = "",
    ) -> None:
        self.thread_id = thread_id
        self.user_id = user_id
        self.title = title
        self.created_at = created_at or _now_iso()
        self.last_active_at = last_active_at or self.created_at
        self.context = context or []  # recent message snippets for this thread
        self.summary = summary

    def to_dict(self) -> Dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "user_id": self.user_id,
            "title": self.title,
            "created_at": self.created_at,
            "last_active_at": self.last_active_at,
            "context": self.context,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Thread:
        return cls(
            thread_id=data["thread_id"],
            user_id=data["user_id"],
            title=data["title"],
            created_at=data.get("created_at"),
            last_active_at=data.get("last_active_at"),
            context=data.get("context", []),
            summary=data.get("summary", ""),
        )

    def update_context(self, snippet: str, max_items: int = 20) -> None:
        """Push a new snippet into the thread context, dropping old ones."""
        self.context.append(snippet)
        if len(self.context) > max_items:
            self.context = self.context[-max_items:]
        self.last_active_at = _now_iso()


# ---------------------------------------------------------------------------
# Thread store
# ---------------------------------------------------------------------------

class ThreadStore:
    """Persistent thread storage for one Gisto instance.

    Threads are stored under *root_dir* as one JSON file per user. Each user
    gets their own file so data never leaks across users.
    """

    def __init__(self, root_dir: str = "./data/threads") -> None:
        self.root_dir = Path(root_dir).expanduser().resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    # -- per-user file paths -----------------------------------------------

    def _user_path(self, user_id: str) -> Path:
        return self.root_dir / f"{self._safe_user_id(user_id)}.json"

    @staticmethod
    def _safe_user_id(user_id: str) -> str:
        # Make a filename-safe version. Keep it simple.
        return re.sub(r"[^\w\-]", "_", str(user_id))

    # -- load / save ------------------------------------------------------

    def _load_user_threads(self, user_id: str) -> List[Thread]:
        path = self._user_path(user_id)
        if not path.exists():
            return []
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = __import__("json").load(fh)
        except (ValueError, OSError):
            return []
        return [Thread.from_dict(item) for item in data if isinstance(item, dict)]

    def _save_user_threads(self, user_id: str, threads: List[Thread]) -> None:
        path = self._user_path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            __import__("json").dump(
                [t.to_dict() for t in threads],
                fh,
                indent=2,
                ensure_ascii=False,
            )
        tmp.replace(path)

    # -- thread CRUD ------------------------------------------------------

    def list_for_user(self, user_id: str) -> List[Thread]:
        threads = self._load_user_threads(user_id)
        # Return sorted by last_active_at descending (most recent first).
        return sorted(threads, key=lambda t: t.last_active_at, reverse=True)

    def get(self, thread_id: str) -> Optional[Thread]:
        for user_dir in self.root_dir.glob("*.json"):
            try:
                with open(user_dir, "r", encoding="utf-8") as fh:
                    data = __import__("json").load(fh)
            except (ValueError, OSError):
                continue
            for item in data:
                if isinstance(item, dict) and item.get("thread_id") == thread_id:
                    return Thread.from_dict(item)
        return None

    def create(self, user_id: str, title: str) -> Thread:
        thread_id = _make_thread_id()
        thread = Thread(thread_id=thread_id, user_id=user_id, title=title)
        threads = self._load_user_threads(user_id)
        threads.insert(0, thread)
        self._save_user_threads(user_id, threads)
        return thread

    def current_for(self, user_id: str) -> Optional[Thread]:
        threads = self._load_user_threads(user_id)
        if not threads:
            return None
        # The first thread in the list is treated as the current one (we keep
        # it at index 0 when marking active). That's a simple convention.
        return threads[0]

    def mark_active(self, thread_id: str, user_id: str) -> Optional[Thread]:
        threads = self._load_user_threads(user_id)
        for i, t in enumerate(threads):
            if t.thread_id == thread_id:
                # Move to front.
                threads.pop(i)
                threads.insert(0, t)
                t.update_context(f"active:{_now_iso()}")
                self._save_user_threads(user_id, threads)
                return t
        return None

    def context_for(self, thread_id: str) -> List[str]:
        thread = self.get(thread_id)
        if thread:
            return list(thread.context)
        return []

    def should_continue(self, thread_id: str, user_input: str) -> bool:
        """Decide whether *user_input* should stay in this thread.

        This is a lightweight heuristic. It's good enough for normal use, but
        not perfect — the user can always override via manual controls.
        """
        thread = self.get(thread_id)
        if not thread:
            return False
        if not user_input or not user_input.strip():
            return False

        low = user_input.lower().strip()
        if len(low) < 4:
            return False

        # If the thread has context, check for topical continuity.
        context_text = " ".join(thread.context[-8:]).lower()
        if context_text:
            # If the input shares substantive words with recent context, it's
            # probably a continuation.
            input_words = set(re.findall(r"[a-z0-9]+", low))
            context_words = set(re.findall(r"[a-z0-9]+", context_text))
            if input_words & context_words:
                return True

        # If the thread title shares words with the input, continue.
        title_words = set(re.findall(r"[a-z0-9]+", thread.title.lower()))
        input_words = set(re.findall(r"[a-z0-9]+", low))
        if title_words & input_words and len(title_words & input_words) >= 1:
            # But if the input is clearly a new topic (question words + new
            # subject), prefer a new thread.
            question_y = any(w in low for w in ("how", "what", "why", "can", "could", "would", "should", "do i", "i want", "i need", "tell me", "explain"))
            if question_y and len(input_words) > 3:
                # Check if the new topic is substantially different from the
                # title. If so, start a new thread.
                new_topic_words = input_words - title_words
                if len(new_topic_words) >= 2:
                    return False

            return True

        # Default: new topic, new thread.
        return False

    def rename_thread(self, thread_id: str, new_title: str) -> bool:
        if not new_title or not new_title.strip():
            return False
        for user_dir in self.root_dir.glob("*.json"):
            try:
                with open(user_dir, "r", encoding="utf-8") as fh:
                    data = __import__("json").load(fh)
            except (ValueError, OSError):
                continue
            for item in data:
                if isinstance(item, dict) and item.get("thread_id") == thread_id:
                    item["title"] = new_title.strip()[:100]
                    item["last_active_at"] = _now_iso()
                    with open(user_dir, "w", encoding="utf-8") as fh:
                        __import__("json").dump(data, fh, indent=2, ensure_ascii=False)
                    return True
        return False

    def merge_threads(self, source_ids: List[str], target_id: str) -> bool:
        if not source_ids or not target_id:
            return False
        target = self.get(target_id)
        if not target:
            return False
        for source_id in source_ids:
            source = self.get(source_id)
            if not source or source.thread_id == target.thread_id:
                continue
            # Append source context to target, then delete source.
            target.context.extend(source.context)
            target.context = target.context[-40:]
            target.last_active_at = _now_iso()
            if not target.summary:
                target.summary = source.title
            # Remove source from its user file.
            user_id = source.user_id
            threads = self._load_user_threads(user_id)
            threads = [t for t in threads if t.thread_id != source_id]
            self._save_user_threads(user_id, threads)
        # Save updated target.
        threads = self._load_user_threads(target.user_id)
        for i, t in enumerate(threads):
            if t.thread_id == target_id:
                threads[i] = target
                break
        self._save_user_threads(target.user_id, threads)
        return True

    def split_thread(self, thread_id: str, new_title: str, snippets: List[str]) -> Optional[str]:
        """Split a thread: keep the existing thread, create a new one with the given snippets.

        Returns the new thread id, or None on failure.
        """
        if not new_title or not new_title.strip():
            return None
        thread = self.get(thread_id)
        if not thread:
            return None
        # Remove the split snippets from the existing thread.
        keep = [c for c in thread.context if c not in snippets]
        thread.context = keep[-40:]
        thread.last_active_at = _now_iso()
        # Save existing thread.
        threads = self._load_user_threads(thread.user_id)
        for i, t in enumerate(threads):
            if t.thread_id == thread_id:
                threads[i] = thread
                break
        self._save_user_threads(thread.user_id, threads)
        # Create new thread.
        new_thread = self.create(thread.user_id, new_title.strip()[:100])
        for snippet in snippets:
            new_thread.update_context(snippet)
        return new_thread.thread_id

    # -- cleanup ----------------------------------------------------------

    def prune_old_threads(self, user_id: str, max_threads: int = 50) -> None:
        """Keep only the most recent *max_threads* threads for a user."""
        threads = self._load_user_threads(user_id)
        if len(threads) <= max_threads:
            return
        threads = sorted(threads, key=lambda t: t.last_active_at, reverse=True)
        kept = threads[:max_threads]
        self._save_user_threads(user_id, kept)

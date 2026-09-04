"""Gisto memory system.

Re-export of the UserMemory and MemoryEntry classes from src.cli.

Usage::

    from src.memory import UserMemory

    mem = UserMemory(user_id="user-1", root_dir="./data/memory")
    mem.apply("user wants agency mode on", kind="fact")
    mem.apply("prefers concise replies", kind="preference")
    print(mem.facts)
    print(mem.preferences)
"""

from __future__ import annotations

from src.cli import MemoryEntry, UserMemory, memory_from_config

__all__ = ["MemoryEntry", "UserMemory", "memory_from_config"]

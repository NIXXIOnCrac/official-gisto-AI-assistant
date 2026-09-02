"""Gisto integration adapters.

Each integration (Discord, Slack, Google, Composio) conforms to the
``Integration`` interface defined in ``base.py``.
"""

from __future__ import annotations

# This package init deliberately does NOT import the integration classes
# eagerly, to avoid circular imports with src.modules. Import them where
# they're used (e.g. in the integration registry or the bot entry point).

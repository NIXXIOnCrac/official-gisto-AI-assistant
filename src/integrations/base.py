"""Integration base class for Gisto.

Every integration adapter (Discord, Slack, Google, Composio) subclasses
``Integration`` so the orchestrator and other modules can treat them uniformly.
"""

from __future__ import annotations

from typing import Any, Dict


class Integration:
    """Base interface for a Gisto integration adapter."""

    name: str = ""
    description: str = ""
    summary: str = ""

    def can_handle(self, request: Dict[str, Any]) -> bool:
        raise NotImplementedError

    def handle(self, request: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def is_configured(self) -> bool:
        raise NotImplementedError

    def config_summary(self) -> Dict[str, Any]:
        raise NotImplementedError

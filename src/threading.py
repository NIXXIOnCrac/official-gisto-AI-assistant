"""Composio integration adapter for Gisto.

Composio is a connector layer that lets Gisto connect to external services
without wiring each one directly. The user supplies their own Composio API key.

This is an optional path — the user can wire integrations directly instead.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.integrations.base import Integration


class ComposioIntegration(Integration):
    """Gisto via Composio as a connector layer.

    If the user chooses to use Composio, this adapter uses the Composio API to
    connect Gisto to services without the user wiring each one directly.
    """

    name = "composio"
    description = (
        "Composio connector layer. Lets Gisto connect to external services "
        "through Composio instead of wiring each integration directly. You supply "
        "your own Composio API key."
    )
    summary = "Composio connector — one API key, many service connections."

    _required_config_keys = ("api_key",)

    def __init__(self) -> None:
        self._config: Dict[str, Any] = {}
        self._load_config()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        try:
            self._config = get_integration_config("composio")
        except Exception:
            self._config = {}

    def is_configured(self) -> bool:
        api_key = self._config.get("api_key")
        if not api_key or not isinstance(api_key, str) or not api_key.strip():
            return False
        if self._looks_like_placeholder(api_key):
            return False
        return True

    def config_summary(self) -> Dict[str, Any]:
        return {
            "enabled": self._config.get("enabled", False),
            "has_api_key": bool(self._config.get("api_key")),
        }

    @staticmethod
    def _looks_like_placeholder(value: str) -> bool:
        lowered = value.strip().lower()
        return (
            lowered in {"", "your_api_key_here", "your_composio_api_key_here"}
            or lowered.startswith("your_")
            or lowered.startswith("<")
            or lowered.endswith(">")
        )

    # ------------------------------------------------------------------
    # Request handling
    # ------------------------------------------------------------------

    def can_handle(self, request: Dict[str, Any]) -> bool:
        return bool(request.get("integration") == "composio")

    def handle(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "answer": (
                "The Composio integration is configured in the framework, but the "
                "live Composio connector is not started from here. To use Gisto via "
                "Composio, add your Composio API key to config.yaml and use the "
                "Composio entry point (to be built)."
            ),
            "memory_actions": [],
            "integration": "composio",
        }

    def intended_setup(self) -> Dict[str, Any]:
        return {
            "steps": [
                "Create a Composio account and get an API key.",
                "Copy the API key into config.yaml under integrations.composio.api_key.",
                "Enable the integration in config.",
                "Use the Composio entry point (to be built) to connect Gisto to the services you want.",
            ],
            "note": (
                "Composio is an optional connector layer. You can also wire "
                "integrations directly. Gisto does not ship with a Composio API key."
            ),
        }


_default: Optional[ComposioIntegration] = None


def get_default() -> ComposioIntegration:
    global _default
    if _default is None:
        _default = ComposioIntegration()
    return _default

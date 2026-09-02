"""Google integration adapter for Gisto.

Gives Gisto access to Google services (Gmail, calendar, docs, etc.) through the
user's own Google project via OAuth, or through Composio as a connector.

This is an optional integration. The user supplies their own credentials.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.integrations.base import Integration


class GoogleIntegration(Integration):
    """Gisto with Google service access.

    Supports two modes:
    - OAuth mode: the user supplies their own Google API credentials
    - Composio mode: the user uses Composio as the connector layer instead
    """

    name = "google"
    description = (
        "Google services integration. Lets Gisto interact with Gmail, calendar, "
        "docs, and other Google services. You supply your own OAuth credentials or "
        "use Composio as the connector."
    )
    summary = "Google services — Gmail, calendar, docs, via OAuth or Composio."

    _required_oauth_keys = ("client_id", "client_secret")

    def __init__(self) -> None:
        self._config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        try:
            from src.config import get_integration_config
            self._config = get_integration_config("google")
        except Exception:
            self._config = {}

    def is_configured(self) -> bool:
        composio_block = self._config.get("composio")
        if composio_block and isinstance(composio_block, dict):
            api_key = composio_block.get("api_key")
            if api_key and isinstance(api_key, str) and api_key.strip():
                if not self._looks_like_placeholder(api_key):
                    return True
        oauth_ok = True
        for key in self._required_oauth_keys:
            value = self._config.get(key)
            if not value or not isinstance(value, str) or not value.strip():
                oauth_ok = False
                break
            if self._looks_like_placeholder(value):
                oauth_ok = False
                break
        return oauth_ok

    def config_summary(self) -> Dict[str, Any]:
        return {
            "enabled": self._config.get("enabled", False),
            "mode": "composio" if self._config.get("composio") else "oauth",
            "has_client_id": bool(self._config.get("client_id")),
            "has_client_secret": bool(self._config.get("client_secret")),
            "has_composio_api_key": bool(
                self._config.get("composio", {}).get("api_key")
            ),
        }

    @staticmethod
    def _looks_like_placeholder(value: str) -> bool:
        lowered = value.strip().lower()
        return (
            lowered in {"", "your_client_id_here", "your_client_secret_here",
                        "your_api_key_here"}
            or lowered.startswith("your_")
            or lowered.startswith("<")
            or lowered.endswith(">")
        )

    def can_handle(self, request: Dict[str, Any]) -> bool:
        return bool(request.get("integration") == "google")

    def handle(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "answer": (
                "The Google integration is configured in the framework, but the live "
                "Google service connection is not started from here. To use Gisto with "
                "Google, either supply your own OAuth credentials or use Composio as "
                "the connector, then run the Google entry point (to be built)."
            ),
            "memory_actions": [],
            "integration": "google",
        }

    def intended_setup(self) -> Dict[str, Any]:
        return {
            "modes": {
                "oauth": {
                    "description": "Use your own Google Cloud project and OAuth credentials.",
                    "steps": [
                        "Create a Google Cloud project or use an existing one.",
                        "Enable the APIs you need (Gmail, Calendar, Docs, etc.).",
                        "Create OAuth 2.0 credentials (client ID and client secret).",
                        "Add the client ID and client secret to config.yaml under integrations.google.",
                        "Configure the OAuth consent screen and add test users if needed.",
                        "Run the Google entry point (to be built) to complete OAuth flow.",
                    ],
                },
                "composio": {
                    "description": "Use Composio as the connector layer instead of direct OAuth.",
                    "steps": [
                        "Set integrations.composio.enabled to true.",
                        "Add your Composio API key to config.yaml under integrations.composio.api_key.",
                        "Add integrations.google.composio.api_key pointing to the same Composio key.",
                        "Run the Composio entry point (to be built) to connect Google services.",
                    ],
                },
            },
            "note": (
                "Gisto does not ship with Google credentials. You use your own "
                "Google project, or use Composio as an alternative connector."
            ),
        }


_default: Optional[GoogleIntegration] = None


def get_default() -> GoogleIntegration:
    global _default
    if _default is None:
        _default = GoogleIntegration()
    return _default

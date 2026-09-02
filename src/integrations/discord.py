"""Slack integration adapter for Gisto.

The user supplies their own bot token and signing secret in config. This
adapter does not ship with any credentials.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.integrations.base import Integration


class SlackIntegration(Integration):
    """Gisto as a Slack app.

    Reads messages from allowed channels and replies in-character as Gisto.
    """

    name = "slack"
    description = (
        "Slack app integration. Lets Gisto read messages and reply in channels "
        "you configure. You supply your own bot token and signing secret."
    )
    summary = "Slack app — Gisto reads and replies in your workspace."

    def __init__(self) -> None:
        self._config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        try:
            from src.config import get_integration_config
            self._config = get_integration_config("slack")
        except Exception:
            self._config = {}

    def is_configured(self) -> bool:
        token = self._config.get("bot_token")
        secret = self._config.get("signing_secret")
        if not token or not isinstance(token, str) or not token.strip():
            return False
        if not secret or not isinstance(secret, str) or not secret.strip():
            return False
        if self._looks_like_placeholder(token) or self._looks_like_placeholder(secret):
            return False
        return True

    def config_summary(self) -> Dict[str, Any]:
        return {
            "enabled": self._config.get("enabled", False),
            "has_token": bool(self._config.get("bot_token")),
            "has_signing_secret": bool(self._config.get("signing_secret")),
            "channel_ids": self._config.get("channel_ids", []),
        }

    @staticmethod
    def _looks_like_placeholder(value: str) -> bool:
        lowered = value.strip().lower()
        return (
            lowered in {"", "your_token_here", "your_signing_secret_here", "your_bot_token_here"}
            or lowered.startswith("your_")
            or lowered.startswith("<")
            or lowered.endswith(">")
        )

    def can_handle(self, request: Dict[str, Any]) -> bool:
        return bool(request.get("integration") == "slack")

    def handle(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "answer": (
                "The Slack integration is configured in the framework, but the live "
                "Slack app is not started from here. To use Gisto on Slack, set up a "
                "Slack app with your own bot token and signing secret, then run the "
                "Gisto Slack entry point (to be built)."
            ),
            "memory_actions": [],
            "integration": "slack",
        }

    def intended_bot_setup(self) -> Dict[str, Any]:
        return {
            "steps": [
                "Create a Slack app at api.slack.com.",
                "Add bot scopes (e.g. chat:write, channels:read, im:read as needed).",
                "Install the app to your workspace.",
                "Copy the bot token (xoxb-...) into config.yaml under integrations.slack.bot_token.",
                "Copy the signing secret into config.yaml under integrations.slack.signing_secret.",
                "Optionally restrict to specific channel IDs in config.",
                "Run the Gisto Slack entry point (to be built).",
            ],
            "note": (
                "Gisto does not ship with a Slack bot token or signing secret. "
                "You create and connect your own Slack app."
            ),
        }


_default: Optional[SlackIntegration] = None


def get_default() -> SlackIntegration:
    global _default
    if _default is None:
        _default = SlackIntegration()
    return _default

"""Discord integration adapter for Gisto.

The user supplies their own bot token, client ID, and optional guild/channel
restrictions in config. This adapter does not ship with any credentials and
does not assume any particular server or channel.

Usage::

    from src.integrations.discord import DiscordIntegration

    discord = DiscordIntegration()
    if discord.is_configured():
        # use discord.can_handle / discord.handle within the orchestrator
        ...
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.integrations.base import Integration


class DiscordIntegration(Integration):
    """Gisto as a Discord bot.

    Reads messages from allowed channels and replies in-character as Gisto.
    """

    name = "discord"
    description = (
        "Discord bot integration. Lets Gisto read messages and reply in servers "
        "and channels you configure. You supply your own bot token and client ID."
    )
    summary = "Discord bot — Gisto reads and replies in your servers."

    # Config keys the user must fill in.
    _required_config_keys = ("bot_token",)

    def __init__(self) -> None:
        self._config: Dict[str, Any] = {}
        self._load_config()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        try:
            self._config = get_integration_config("discord")
        except Exception:
            self._config = {}

    def is_configured(self) -> bool:
        """Return True if the user has supplied the basic credentials."""
        token = self._config.get("bot_token")
        if not token or not isinstance(token, str) or not token.strip():
            return False
        # Don't treat a placeholder as configured.
        if self._looks_like_placeholder(token):
            return False
        return True

    def config_summary(self) -> Dict[str, Any]:
        """Return a safe summary of the Discord config (no secrets)."""
        return {
            "enabled": self._config.get("enabled", False),
            "has_token": bool(self._config.get("bot_token")),
            "has_client_id": bool(self._config.get("client_id")),
            "guild_ids": self._config.get("guild_ids", []),
            "channel_ids": self._config.get("channel_ids", []),
            "intents": self._config.get("intents", "default"),
        }

    @staticmethod
    def _looks_like_placeholder(value: str) -> bool:
        lowered = value.strip().lower()
        return (
            lowered in {"", "your_token_here", "your_bot_token_here"}
            or lowered.startswith("your_")
            or lowered.startswith("<")
            or lowered.endswith(">")
        )

    # ------------------------------------------------------------------
    # Request handling
    # ------------------------------------------------------------------

    def can_handle(self, request: Dict[str, Any]) -> bool:
        """Return True if this request is intended for Discord."""
        return bool(request.get("integration") == "discord")

    def handle(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a request via Discord.

        This is a placeholder implementation. The real adapter would run the
        Discord bot event loop and route messages through the orchestrator.
        """
        return {
            "answer": (
                "The Discord integration is configured in the framework, but the "
                "live bot event loop is not started from here. To use Gisto on "
                "Discord, run the Discord bot entry point with your config in place "
                "and supply your own bot token."
            ),
            "memory_actions": [],
            "integration": "discord",
        }

    # ------------------------------------------------------------------
    # What the real adapter would need
    # ------------------------------------------------------------------

    def intended_bot_setup(self) -> Dict[str, Any]:
        """Describe how the Discord bot should be set up, for docs and setup help."""
        return {
            "steps": [
                "Create a Discord application and bot at the Discord Developer Portal.",
                "Enable the Message Content Intent and any other intents you need.",
                "Copy the bot token into config.yaml under integrations.discord.bot_token.",
                "Add the bot to your server(s) using the OAuth2 URL generator with bot scope.",
                "Optionally restrict to specific guilds/channels in config.",
                "Run the Gisto Discord bot entry point (not yet provided — to be built).",
            ],
            "note": (
                "Gisto does not ship with a bot token and does not add itself to "
                "any server automatically. You connect your own bot."
            ),
        }


# ---------------------------------------------------------------------------
# Default instance
# ---------------------------------------------------------------------------

_default: Optional[DiscordIntegration] = None


def get_default() -> DiscordIntegration:
    global _default
    if _default is None:
        _default = DiscordIntegration()
    return _default

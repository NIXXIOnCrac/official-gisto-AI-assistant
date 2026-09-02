"""Gisto Discord bot entry point.

A working Discord bot that connects Gisto's framework (persona, memory,
threading, onboarding, orchestrator, modules, integrations) to Discord.

This is the bot a user runs after filling in their own config.yaml. It does
not ship with any bot token. The user supplies their own.

Usage::

    # 1. Install dependencies
    pip install -r requirements.txt

    # 2. Copy config and fill it in
    cp config.example.yaml config.yaml
    # edit config.yaml — set integrations.discord.enabled true and add your token

    # 3. Run the bot
    python -m src.discord_bot
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import discord
from discord.ext import commands

from src.config import get_config, is_module_enabled, get_integration_config
from src.memory import UserMemory
from src.threading import ThreadStore, suggest_title, Thread
from src.onboarding import run_onboarding_if_needed
from src.orchestrator import Orchestrator
from src.persona import filter_reply, PERSONA_CALL_REPLY
from src.modules.personal import PersonalModule
from src.modules.agency import AgencyModule
from src.modules.registry import ModuleRegistry
from src.integrations.discord import DiscordIntegration


# ============================================================================
# Logging
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="[gisto-discord] %(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("gisto.discord")


# ============================================================================
# Bot
# ============================================================================

class GistoBot(commands.Bot):
    """The Gisto Discord bot.

    Each Discord user gets their own UserMemory, ThreadStore entry, and
    onboarding state. The bot routes messages through the orchestrator and
    replies in Gisto's persona.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._memory_by_user: dict[int, UserMemory] = {}
        self._threads = ThreadStore(root_dir="./data/threads")
        self._module_registry = ModuleRegistry()
        self._module_registry.register(PersonalModule())
        self._module_registry.register(AgencyModule())
        self._ready = False

    # ------------------------------------------------------------------
    # Per-user memory
    # ------------------------------------------------------------------

    def memory_for(self, user_id: int, config: dict) -> UserMemory:
        if user_id not in self._memory_by_user:
            self._memory_by_user[user_id] = UserMemory(
                user_id=str(user_id),
                root_dir=config.get("memory_dir", "./data/memory"),
                max_history=config.get("limits", {}).get("max_history_entries", 200),
                max_facts=config.get("limits", {}).get("max_facts", 200),
                max_preferences=config.get("limits", {}).get("max_preferences", 50),
                max_age_days=config.get("limits", {}).get("max_age_days", 90),
            )
        return self._memory_by_user[user_id]

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    async def on_ready(self) -> None:
        self._ready = True
        log.info("connected as %s (%s)", self.user, self.user.id)
        log.info("servers: %d", len(self.guilds))

    async def on_message(self, message: discord.Message) -> None:
        # Ignore our own messages.
        if message.author == self.user:
            return

        # Ignore messages from bots (optional — some users may want to allow
        # other bots to talk to Gisto; keep it simple for now).
        if message.author.bot:
            return

        # Only respond in guilds/channels the user has allowed, or DMs.
        if not self._channel_allowed(message.channel):
            return

        # Build the user's memory.
        cfg = get_config().raw
        gisto_cfg = cfg.get("gisto", {})
        memory = self.memory_for(message.author.id, gisto_cfg)

        # Onboarding on first use.
        await self._maybe_onboard(message, memory, gisto_cfg)

        # Route to orchestrator.
        reply = await self._orchestrate(message, memory, gisto_cfg)
        if reply:
            await self._send_reply(message, reply)

    # ------------------------------------------------------------------
    # Channel allowlist
    # ------------------------------------------------------------------

    def _channel_allowed(self, channel: discord.abc.GuildChannel | discord.DMChannel) -> bool:
        cfg = get_config().raw
        integrations = cfg.get("integrations", {})
        discord_cfg = integrations.get("discord", {})
        guild_ids = discord_cfg.get("guild_ids", [])
        channel_ids = discord_cfg.get("channel_ids", [])

        # DMs are always allowed if the integration is enabled and configured.
        if isinstance(channel, discord.DMChannel):
            return True

        # If no restrictions are set, allow all guild channels.
        if not guild_ids and not channel_ids:
            return True

        guild_id = getattr(channel, "guild", None)
        if guild_id is None:
            return False
        guild_id = guild_id.id
        if guild_ids and guild_id not in guild_ids:
            return False
        channel_id = channel.id
        if channel_ids and channel_id not in channel_ids:
            return False
        return True

    # ------------------------------------------------------------------
    # Onboarding
    # ------------------------------------------------------------------

    async def _maybe_onboard(
        self,
        message: discord.Message,
        memory: UserMemory,
        gisto_cfg: dict,
    ) -> None:
        onboarding_enabled = gisto_cfg.get("onboarding_enabled", True)
        if not onboarding_enabled:
            return
        # Only onboard once per user: if they have any facts or preferences,
        # assume onboarding already happened.
        if memory.facts or memory.preferences:
            return

        async def ask(prompt: str) -> str:
            await self._send_reply(message, prompt, skip_onboarding=True)
            # Wait for a reply from the same user in the same channel.
            def check(m: discord.Message) -> bool:
                return m.author.id == message.author.id and m.channel == message.channel
            try:
                response = await self.wait_for("message", check=check, timeout=300.0)
                return response.content
            except asyncio.TimeoutError:
                return ""

        async def emit(text: str) -> None:
            await self._send_reply(message, text, skip_onboarding=True)

        # Run onboarding synchronously-ish via the event loop.
        async def run() -> None:
            result = run_onboarding_if_needed(
                memory=memory,
                ask=lambda text: asyncio.run_coroutine_threadsafe(ask(text), self.loop).result(),
                emit=lambda text: asyncio.run_coroutine_threadsafe(emit(text), self.loop).result(),
                onboarding_enabled=onboarding_enabled,
            )
            log.info("onboarding for user %s: %s", message.author.id, result.get("notes"))

        await run()

    # ------------------------------------------------------------------
    # Orchestrator
    # ------------------------------------------------------------------

    async def _orchestrate(
        self,
        message: discord.Message,
        memory: UserMemory,
        gisto_cfg: dict,
    ) -> str | None:
        user_input = message.content.strip()
        if not user_input:
            return None

        # Threading.
        author_id = str(message.author.id)
        thread = self._threads.current_for(author_id)
        if thread is None or not self._threads.should_continue(thread.thread_id, user_input):
            title = suggest_title(user_input)
            thread = self._threads.create(author_id, title)
        self._threads.mark_active(thread.thread_id, author_id)

        # Context.
        context = {
            "memory": memory,
            "user_id": author_id,
            "thread": {
                "id": thread.thread_id,
                "title": thread.title,
            },
            "thread_context": self._threads.context_for(thread.thread_id),
            "history": [],
            "source": "discord",
        }

        # Find a module to handle this.
        module = self._module_registry.find_handler(user_input, context)
        if module is None:
            module = PersonalModule()

        # Run the module.
        try:
            result = module.handle(user_input, context)
        except Exception as exc:
            log.exception("module %s failed for user %s", module.name, author_id)
            result = {
                "answer": "I'm afraid I ran into a problem there, sir. Give me a moment and try again.",
                "memory_actions": [],
            }

        # Persona filter.
        answer = filter_reply(user_input, result.get("answer", ""), context)

        # Memory actions.
        for content, kind in result.get("memory_actions", []):
            try:
                memory.apply(content, kind=kind)
            except Exception:
                log.exception("failed to apply memory action for user %s", author_id)

        # Record the turn in thread context.
        thread.update_context(f"{message.author.display_name}: {user_input}", max_items=20)
        thread.update_context(f"Gisto: {answer}", max_items=20)

        return answer

    # ------------------------------------------------------------------
    # Sending replies
    # ------------------------------------------------------------------

    async def _send_reply(
        self,
        message: discord.Message,
        text: str,
        *,
        skip_onboarding: bool = False,
    ) -> None:
        if not text:
            return
        # Don't respond to our own onboarding questions.
        if skip_onboarding and text == PERSONA_CALL_REPLY:
            # The call-and-response is handled separately.
            pass
        try:
            await message.channel.send(text)
        except discord.Forbidden:
            log.warning("cannot send message in channel %s (no permission)", message.channel.id)
        except Exception:
            log.exception("failed to send reply in channel %s", message.channel.id)


# ============================================================================
# Main
# ============================================================================

def main() -> None:
    cfg = get_config().raw
    integrations = cfg.get("integrations", {})
    discord_cfg = integrations.get("discord", {})

    if not discord_cfg.get("enabled", False):
        log.error(
            "Discord integration is not enabled. Set integrations.discord.enabled "
            "to true in config.yaml and supply a bot_token."
        )
        sys.exit(1)

    token = discord_cfg.get("bot_token", "")
    if not token or not isinstance(token, str) or not token.strip():
        log.error(
            "Discord bot token is missing. Add integrations.discord.bot_token to "
            "config.yaml with your own bot token."
        )
        sys.exit(1)

    intents = discord_cfg.get("intents", "default")
    discord_intents = discord.Intents.default()
    if intents == "all":
        discord_intents = discord.Intents.all()
    # Always need message content to read user messages.
    discord_intents.message_content = True

    bot = GistoBot(
        command_prefix="!gisto ",
        intents=discord_intents,
    )

    async def _run() -> None:
        # Sync the command tree on startup.
        await bot.wait_until_ready()
        try:
            synced = await bot.tree.sync()
            log.info("command tree synced: %d", len(synced))
        except Exception:
            log.exception("command tree sync failed")

    bot.loop.create_task(_run())
    bot.run(token)


if __name__ == "__main__":
    main()

# Gisto — AI Assistant Framework

A memory-backed AI assistant framework you run yourself. It remembers you across
sessions, organizes conversations into topics automatically, and connects to the
tools you give it access to — Discord, Slack, Google Workspace, or a connector
layer like Composio.

Built so a single user or small operator can run their own assistant without
depending on a hosted platform and without handing their keys to one.

## What it does

- **Memory** — persistent per-user store: facts, preferences, history, active
  projects. Loads before acting, updates as it goes. Survives restarts. Never
  stores your keys or tokens.

- **Threading** — conversations organized into topic threads automatically. You
  don't say "start a new chat." Gisto detects topic shifts and keeps things
  organized. You can also rename, merge, split, and jump into threads manually.

- **Modules** — toggleable capability modules. Base modules: *personal*
  (assistant: memory, notes, drafts, planning, research, chat) and *agency*
  (lead finding, site building, outreach, client comms, project tracking).
  Agency includes everything in personal and adds the agency engine on top.
  Toggle them from config.

- **Integrations** — Discord, Slack, Google Workspace, Composio adapters.
  Each is optional, each needs your own keys/credentials, nothing is wired by
  default. No keys shipped in the framework.

- **Onboarding** — on first run, Gisto interviews you to seed your memory: what
  you want to use it for, which modules and integrations you want, your work,
  your goals, your limits, your style.

- **Persona** — calm, capable, direct. Honest about what it can and cannot do.
  Does not overpromise. Does not pretend to be human. The same Gisto everywhere
  — CLI, home screen, Discord, Slack.

## What it is not

- Not a hosted chatbot you log into.
- Not a demo or a toy.
- Not a single-script chatbot with no memory.
- Not a product with hardcoded keys or baked-in credentials.
- Not a product that pretends to do things it cannot do without the right config.

## Project structure

```
gisto-AI-assistant/
  src/
    core/            # engine, persona, PC control operations
    permissions/     # trust dial, permission gate, operation registry
    integrations/    # Discord, Slack, Google, Composio adapters
    modules/         # personal module, agency module, registry
    memory.py        # persistent per-user memory store
    onboarding.py    # first-run interview
    orchestrator.py  # central message router + self-healing wrapper
    cli.py           # `python -m gisto ...` entry point
    config.py        # config loader
    discord_bot.py   # Discord client wiring
  CLAUDE.md          # master build prompt
  README.md
  requirements.txt
  .gitignore
```

## Status

Active development. Core framework in place:

- Permission system with four levels (VIEW, ASSIST, CONTROL, FULL_ACCESS) and a
  real enforcement gate.
- Agent engine with memory, persona, and operation registry.
- PC control operations with real implementations (system info, process list,
  file read/write/move/delete, process kill, command run, app launch, browser
  navigate).
- Desktop app shell with login, trust dial, chat, actions, and integrations.
- Backend skeleton with auth, permissions, vault, and threat detection.
- Discord bot wiring with persona, memory, threading, and onboarding.
- CLI entry point (`python -m gisto run|onboard|status`).

Some pieces still being finished: the full backend API endpoints, the web UI,
the Discord bot integration, real detection rules for the threat engine.

## Requirements

- Python 3.10+
- Node.js 18+ for the web UI
- A Discord bot token (for the Discord integration, optional)

## Development

```bash
cd gisto-AI-assistant
pip install -r requirements.txt
python -m gisto status   # check setup
python -m gisto onboard  # first-run setup
python -m gisto run      # start the bot
```

## License

Private while in development.

## Author

Youcef Salemtedj

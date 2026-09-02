# Gisto — AI Assistant Framework

A memory-backed AI assistant framework you run yourself.

Gisto remembers you across sessions, organizes conversations into topics
automatically, and connects to the tools you give it access to — Discord, Slack,
Google Workspace, or a connector layer like Composio. You run it. You supply your
own keys. Nothing is wired by default.

It is built so a single user or small operator can run their own assistant
without depending on a hosted platform and without handing their keys to one.

## What it does

- **Memory.** Persistent per-user store: facts, preferences, history, active
  projects. Loads before it acts. Updates as it goes. Survives restarts. Never
  stores your keys or tokens.

- **Threading.** Conversations are organized into topic threads automatically.
  You do not have to say "start a new chat." Gisto detects topic shifts and keeps
  things organized. You can also rename, merge, split, and jump into threads
  manually.

- **Modules.** Toggleable capability modules. The base modules are *personal*
  (assistant: memory, notes, drafts, planning, research, chat) and *agency*
  (lead finding, site building, outreach, client comms, project tracking).
  Agency includes everything in personal and adds the agency engine on top.
  Toggle them from config.

- **Integrations.** Discord, Slack, Google Workspace, and Composio adapters.
  Each is optional. Each needs your own keys/credentials. Nothing is wired by
  default. No keys are shipped in the framework.

- **Onboarding.** On first run, Gisto interviews you to seed your memory: what
  you want to use it for, which modules and integrations you want, your work,
  your goals, your limits, your style.

- **Persona.** Calm, capable, direct. Honest about what it can and cannot do.
  Does not overpromise. Does not pretend to be human. The same Gisto everywhere
  — CLI, home screen, Discord, Slack.

## What it can do on your machine

When you grant it permission, Gisto can act on your computer through the PC
control operation registry:

- **Observe:** system info, process list, read files, list directories, capture
  screen or browser viewport.
- **Files:** read files, list directories, write files, move files, delete files.
- **Processes:** list processes, kill processes, run shell commands.
- **Applications:** launch applications, focus windows.
- **Browser:** capture browser viewport, navigate to a URL.

Every operation is gated by a permission level. A low-permission Gisto cannot
write files, run commands, or kill processes. A full-access Gisto can do all of
it, with everything logged.

## Permission levels

| Level | What Gisto can do |
|---|---|
| **View** | Observe only. Screen, files, system info, processes, logs. No changes. |
| **Assist** | Assist through approved surfaces. Answer from what it sees, take notes, preview files, do only the safe operations you explicitly approve. |
| **Control** | Take action. Run commands and scripts, manage files, control applications. Sensitive operations (system settings, installs, anything involving money or credentials) stay gated and logged. |
| **Full Access** | Full PC access. Everything is logged and visible to you. Exists for when you want Gisto to actually run the machine, not just advise on it. |

The permission system is not cosmetic. Every PC operation declares the level it
needs, and the gate enforces it before any action runs.

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

Active development. The core framework is in place:

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

Some pieces are still being finished:

- Full backend API endpoints
- Web UI
- Discord bot integration
- Real detection rules for the threat engine
- The desktop app as a published product

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

## Authored for

This project was submitted to the
[Claude for Open Source Program](https://claude.com/contact-sales/claude-for-oss)
in September 2026. The application text is in
[CLAUDE_APPLICATION_FIELDS.txt](CLAUDE_APPLICATION_FIELDS.txt) in this repo.

## License

Private while in development.

## Author

Youcef Salemtedj

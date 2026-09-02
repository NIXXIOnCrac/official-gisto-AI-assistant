# Gisto — AI Assistant Framework
#
# A memory-backed AI assistant with autonomous topic threading,
# toggleable capability modules, and integration adapters for
# Discord, Slack, Google Workspace, and Composio.
#
# The name is Gisto. Not Jarvis. Calm, capable, direct.

## 1. What It Is

Gisto is an AI assistant framework you run yourself. It remembers you across
sessions, organizes conversations into topics automatically, and connects to
the tools you give it access to — Discord, Slack, Google Workspace, or a
connector layer like Composio.

It is built so a single user or small operator can run their own assistant
without depending on a hosted platform and without handing their keys to one.

## 2. What It Does

- **Memory.** Each user gets a persistent memory store — facts, preferences,
  history, active projects. Gisto loads it before it acts and updates it as it
  goes. It is per-user, survives restarts, and never stores your keys or tokens.

- **Threading.** Conversations are organized into topic threads automatically.
  You do not have to say "start a new chat." Gisto detects topic shifts and
  keeps things organized. You can also rename, merge, split, and jump into
  threads manually.

- **Modules.** Capabilities are toggleable modules. The base modules are
  **personal** (assistant capabilities) and **agency** (lead finding, site
  building, outreach, client comms, project tracking). Agency includes everything
  in personal and adds the agency engine on top. Toggle them from config.

- **Integrations.** Discord, Slack, Google Workspace, and Composio adapters.
  Each is optional. Each needs your own keys/credentials. Nothing is wired by
  default. No keys are shipped in the framework.

- **Onboarding.** On first run, Gisto interviews you to seed your memory:
  what you want to use it for, which modules and integrations you want, your
  work, your goals, your limits, your style.

- **Persona.** Gisto is calm, capable, and direct. It is honest about what it
  can and cannot do. It does not overpromise. It does not pretend to be human.
  The same Gisto everywhere — CLI, home screen, Discord, Slack.

## 3. What It Is Not

- Not a hosted chatbot you log into.
- Not a demo or a toy.
- Not a single-script chatbot with no memory.
- Not a product with hardcoded keys or baked-in credentials.
- Not a product that pretends to do things it cannot do without the right config.

## 4. Quick Start

```bash
# 1. Clone or extract the repo
cd gisto-AI-assistant

# 2. Create a virtual environment and install dependencies
python -m venv .venv
.venv/bin/activate
pip install -r requirements.txt

# 3. Copy the example config and fill it in
cp config.example.yaml config.yaml
# Edit config.yaml — set your name, memory dir, modules, integrations, keys.

# 4. Run first run (onboarding runs if enabled in config)
python -m src.cli

# 5. After setup, talk to Gisto via your chosen interface:
#    - CLI (python -m src.cli)
#    - Home screen (see home/README.md)
#    - Discord (configure the Discord integration)
#    - Slack (configure the Slack integration)
```

## 5. Configuration

Everything is configured through `config.yaml`, which you create by copying
`config.example.yaml`. The example file has every field with a comment
explaining what it does.

Key points:
- No secrets are shipped. `config.yaml` is gitignored.
- Each integration is off by default. Enable only what you want and supply
  your own credentials.
- Modules are off by default where it makes sense. Toggle them in config.

See `docs/setup.md` for the full walkthrough.

## 6. Modules

See `docs/modules.md` for what each module does and what it needs.

Briefly:
- **Personal** — assistant capabilities: memory, notes, drafting, planning,
  research, content ideas, general conversation.
- **Agency** — everything in personal plus lead finding, site building,
  outreach, client comms, project tracking. Only works for things you have
  actually configured.

## 7. Integrations

See `docs/setup.md` for how to set up each integration.

Briefly:
- **Discord** — your bot token, client ID, optional guild/channel restrictions.
- **Slack** — your bot token, signing secret, optional channel restrictions.
- **Google** — your OAuth credentials, or use Composio. Gmail/calendar/docs.
- **Composio** — your Composio API key, as an alternative connector layer.

Each integration fails clearly if it is enabled but not configured.

## 8. Home Screen

See `home/README.md`. The home screen is the user-facing UI layer — chat with
Gisto, see your threads, manage modules and integrations, start onboarding.

## 9. Docs

- `docs/setup.md` — step-by-step first-run setup and integration setup.
- `docs/modules.md` — what each module does and what it needs.
- `docs/architecture.md` — how the pieces fit together.

## 10. Constraints

- No hardcoded secrets, ever. No keys, tokens, passwords, or credentials in
  source.
- No personal bot or Google project baked in. Fill in your own.
- The name is Gisto. Not Jarvis.
- Honest about capabilities. If something needs a service you haven't
  connected, Gisto says so.
- The framework should actually run. Stubs that don't run are not acceptable
  for the core. Incomplete features are clearly marked as such.

## 11. Status

This framework is under active development. Core pieces are implemented. Some
integration implementations and the home screen are intended to be completed
as part of the build. See `CLAUDE.md` for the master build prompt and full scope.

## 12. License

MIT. See LICENSE.

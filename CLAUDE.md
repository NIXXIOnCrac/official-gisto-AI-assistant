# CLAUDE.md — Gisto Build Prompt

**Read this first. This is the entire Gisto project, the design decisions already made, the architecture, the constraints, and what you are expected to build. Treat it as the single source of truth. Do not improvise on the decisions that are locked in here — implement them.**

---

## 1. What Gisto Is

Gisto is a memory-backed AI assistant framework. One user, one persistent memory store, autonomous topic threading, toggleable capability modules, and integration adapters for Discord, Slack, Google Workspace, and a connector layer like Composio.

The product vision: a single user or small operator runs their own assistant that remembers them across sessions, organizes conversations into topics automatically, and connects to the tools they actually use — without depending on a hosted platform and without hardcoding any secrets.

**Name:** Gisto. Not Jarvis. Not "Jarvis-inspired" in the code. The name Gisto appears in config, persona, logs, docs. The JARVIS vibe is a reference point for tone/UX, not the product name.

**Target user:** a person who wants their own AI assistant they can run themselves, give their own keys to, shape with modules, and connect to their own Discord/Slack/Google — not a SaaS they log into and hope doesn't leak their data.

**What it is not:** a hosted chatbot, a demo, a toy, a single-script chatbot with no memory.

---

## 2. The Core Design Decisions (Locked In — Do Not Change These)

These are settled. Implement them as written. If something here conflicts with a "better idea," keep what's written and note the conflict in a comment rather than silently changing it.

### 2.1 One user memory store, not siloed memory

Every user gets one persistent memory store. It holds:
- Facts about the user (name, work, goals, limits, preferences)
- History of meaningful interactions (not every message, but what matters)
- Preferences and behavior settings
- References to threads (so memory and threading are connected, not separate)

Memory is **per user**, never shared across users, never committed with real data, never stores raw keys or tokens.

### 2.2 Autonomous topic threading, with manual fallback

Conversations are organized into threads automatically. The user does **not** have to say "start a new chat" or "make a new thread." Gisto detects topic shifts and creates/organizes threads on its own.

But the auto-detection is not perfect. The user can also:
- Rename a thread
- Merge threads
- Split a thread
- Jump into an existing thread

So the system is: auto-threading first, manual control as fallback. Never force the user to manage threads manually, never pretend the auto-detection is flawless.

### 2.3 Toggleable capability modules

Capabilities are modules. They are turned on/off from config. The two base modules are:
- **Personal** — personal assistant capabilities (memory, notes, drafts, planning, chat, research, content ideas)
- **Agency** — agency capabilities (lead finding, site building, outreach, client comms, project tracking)

Agency includes everything in Personal and adds the agency engine on top. Personal is the lighter "ok" version. Agency is the full version.

Modules are real capabilities, not labels. If a module is on, Gisto can actually do the things in it.

### 2.4 Integration adapters, user-supplied keys

Integrations are adapters that conform to a common interface. Each integration is something the user opts into and supplies their own keys/credentials for. Gisto does not ship with any real keys, does not bake in the author's personal bot, does not connect to anything by default.

Supported integrations (adapters to build):
- **Discord** — user supplies bot token, client ID, optional guild/channel restrictions
- **Slack** — user supplies bot token, signing secret, optional channel restrictions
- **Google** — Gmail/calendar/docs access. User supplies OAuth credentials OR uses Composio
- **Composio** — a connector layer the user can use instead of wiring each service directly

Each adapter is optional, independently toggleable, and fails clearly if the user hasn't configured it.

### 2.5 No hardcoded secrets, ever

The framework ships with `config.example.yaml` containing placeholders and comments. The real `config.yaml` is gitignored. No secrets in source, no secrets in memory, no secrets in logs. If a piece of code needs a key, it reads it from config at runtime and errors clearly if it's missing.

### 2.6 Onboarding interview on first run

When a user runs Gisto for the first time (or when onboarding is enabled in config), Gisto runs an interview: asks about the user's work, goals, limits, which modules/integrations they want, their style, anything else worth remembering. The answers get written into the user's memory. This is not a one-off wizard that forgets everything — it's how the memory gets seeded.

### 2.7 Persona is Gisto, not Jarvis

Gisto is a calm, capable, direct assistant. Not a joke. Not a yes-man. Not overpromising. The persona lives in `src/persona.py` and the system prompt layer. It should be coherent across every integration and module — the same Gisto whether you talk to it in Discord, Slack, the home screen, or a CLI.

---

## 3. Repo Structure (Created As Part of the Build)

Create the repo at **`C:\Users\Student\Desktop\github repos\gisto-AI-assistant`** with this exact structure. Every directory and file listed here should exist when you're done, even if some are initial stubs.

```
gisto-AI-assistant/
├── README.md
├── LICENSE
├── .gitignore
├── config.example.yaml
├── requirements.txt
├── CLAUDE.md                     # this file — the master build prompt
├── src/
│   ├── __init__.py
│   ├── config.py                 # load + validate config.yaml, no hardcoded secrets
│   ├── memory.py                 # per-user persistent memory: facts, history, prefs, thread refs
│   ├── threading.py              # autonomous topic detection + thread storage per user
│   ├── persona.py                # Gisto identity, behavior rules, system prompt layer
│   ├── onboarding.py             # first-run interview — seeds user memory
│   ├── orchestrator.py           # main loop: receive input → route thread → run modules → reply
│   ├── modules/
│   │   ├── __init__.py
│   │   ├── base.py               # module interface: what a capability module looks like
│   │   ├── personal.py           # personal assistant capabilities
│   │   ├── agency.py             # agency capabilities (lead find, site build, outreach, comms)
│   │   └── registry.py           # resolves which modules are active from config
│   ├── integrations/
│   │   ├── __init__.py
│   │   ├── base.py               # integration adapter interface
│   │   ├── discord.py            # Discord adapter — user supplies bot token, intents, channel IDs
│   │   ├── slack.py              # Slack adapter — user supplies bot token, signing secret
│   │   ├── google.py             # Google adapter — Gmail/calendar/docs via OAuth or Composio
│   │   └── composio.py           # Composio connector layer (optional path)
│   └── cli.py                    # command-line entry point for running Gisto locally
├── home/
│   ├── README.md                 # what the home screen is, how it connects to core
│   └── ...                       # the home screen / dashboard — build as a real usable UI
└── docs/
    ├── setup.md                  # step-by-step setup for each integration + first run
    ├── modules.md                # what each module does, how to toggle it, what it can/can't do
    └── architecture.md           # how the pieces fit together, data flow, memory model, threading model
```

Do not create extra top-level directories unless there's a real reason. Keep the structure clean.

---

## 4. What You Are Expected to Build (Full Scope)

You are building the entire framework — core and surface area. The core pieces are specified in detail below. The surface area (home screen, integration implementations, module flesh-out, docs examples) is also yours — implement it all, not just stubs.

### 4.1 Core framework (spec in detail)

### 4.2 Home screen / dashboard (`home/`)

### 4.3 Integration adapters (`src/integrations/`)

### 4.4 Modules (`src/modules/`)

### 4.5 Docs (`docs/`)

---

## 5. The Config System (Spec)

### 5.1 `config.example.yaml`

Ship this with the repo. It is the template. Every field the framework cares about appears here with a comment explaining what it does and what the user should put in it. No real values. Placeholders only.

Key sections:
- `gisto.name` — the assistant's name (default "Gisto")
- `gisto.memory_dir` — where per-user memory is stored on disk
- `gisto.onboarding_enabled` — whether first-run interview runs
- `gisto.modules.personal` / `gisto.modules.agency` — default module toggles
- `gisto.integrations.discord` / `.slack` / `.google` / `.composio` — each with its own `enabled` flag and the fields that integration needs
- `gisto.limits` — optional usage/lifecycle limits (messages per minute, memory max age, etc.)

### 5.2 `config.yaml` (user-created, gitignored)

The user copies `config.example.yaml` to `config.yaml` and fills in real values. `config.yaml` is in `.gitignore`. The framework never commits it.

### 5.3 `config.py`

- Loads `config.yaml` (or the path config says) at startup
- Validates required fields per enabled integration and per enabled module
- Errors clearly if something required is missing — tells the user exactly what's missing and where to put it
- Never logs or prints real secret values
- Provides a clean Python API the rest of the framework uses to ask "is X integration enabled?" and "what's the config for X?"

---

## 6. Memory System (Spec)

### 6.1 What memory holds

Per user, store:
- **Facts** — discrete things Gisto should remember: user's name, work, goals, limits, preferences, anything the onboarding interview or later conversations establish
- **History** — meaningful interaction history, not every message verbatim but enough that Gisto has continuity
- **Preferences** — behavior settings the user has set or that Gisto has learned
- **Thread references** — a mapping so memory and threading are connected (which threads exist, which are active, summary refs)

### 6.2 Storage

Memory lives on disk in the directory `config.gisto.memory_dir`. It is per-user and persists across restarts. Pick a storage approach that is simple and reliable (file-based is fine; do not over-engineer with a database unless there's a real reason).

### 6.3 What memory must never contain

- Raw API keys, tokens, passwords, or credentials
- Another user's data
- Anything that should not survive in a file on disk unencrypted if it's sensitive — use judgment; at minimum, never write keys/tokens into memory

### 6.4 Pruning / lifecycle

Memory should not grow forever. Implement an age-based pruning strategy: older, less-relevant entries can be trimmed or summarized. Configurable via `gisto.limits.memory_max_age_days` or similar. The point is to keep memory useful and bounded, not to delete things arbitrarily.

### 6.5 Load before acting

Before Gisto responds to anything, it loads the relevant user's memory. After it acts, it updates memory with anything worth keeping. This is not optional — memory is why Gisto is memoryless-less.

---

## 7. Threading System (Spec)

### 7.1 How threads work

Each user has a set of threads. Each thread has:
- An identifier
- A name (auto-generated, editable by the user)
- A recent context window for that thread
- A reference in the user's memory

Threads are the unit the user can go back into. A thread is "about something" — Slack usage, Claude Code usage, a specific project, etc.

### 7.2 Autonomous topic detection

When the user sends input, Gisto decides:
- Does this continue the current thread?
- Or is this a new topic that should start a new thread?

The detection should be good enough that in normal use the user does not have to manage threads manually. It does not need to be perfect — it needs to be good enough that it feels right most of the time, with manual controls as fallback.

### 7.3 Manual controls

The user can:
- Rename a thread
- Merge two threads
- Split a thread
- List their threads
- Jump into a specific thread

These are real features, not stubs. The user must be able to correct the auto-detection when it's wrong.

### 7.4 Thread memory vs user memory

Each thread carries its own recent context. The user's broader memory (facts, prefs, ongoing projects) is shared across threads. A thread about "how to use Slack" should not forget that the user is building an agency — that's in user memory. But the Slack-thread-specific details live in the thread.

---

## 8. Persona (Spec)

### 8.1 Who Gisto is

Gisto is a calm, capable, direct assistant. Key qualities:
- Competent and useful first
- Honest about what it can and cannot do
- Doesn't overpromise
- Doesn't pretend to be human
- Doesn't joke excessively
- Doesn't flatter
- Doesn't act like it has authority it doesn't have
- Treats the user's keys, data, and limits seriously

### 8.2 Tone

Calm. Direct. Helpful without being saccharine. The JARVIS reference is a vibe reference — calm, capable, controlled — not a costume. Do not turn Gisto into a JARVIS parody. Do not call itself JARVIS. The name is Gisto.

### 8.3 Where the persona lives

`src/persona.py` holds the identity and behavior rules. The system prompt layer applies it to every response Gisto generates, regardless of integration or module. The persona is not something each integration reimplements — it's a core layer.

---

## 9. Onboarding (Spec)

### 9.1 When it runs

When `gisto.onboarding_enabled` is true and the user has no memory yet (first run), Gisto runs the onboarding interview.

### 9.2 What it asks

The interview should collect:
- What the user wants to use Gisto for (personal, agency, both)
- What modules they want on
- What integrations they want to set up
- Their work / what they're trying to do
- Their goals
- Any hard limits (what Gisto should not do, spending limits, access limits)
- Anything else worth remembering about how they work

### 9.3 What it produces

The answers get written into the user's memory as facts and preferences. Onboarding is not a form that disappears — it's how memory starts.

### 9.4 How it behaves

The interview is a conversation, not a giant form. Gisto asks, the user answers, Gisto follows up where it makes sense, and when it has enough it confirms and writes the memory. It should not be overly long. It should not block the user forever. If the user wants to skip it, config allows that.

---

## 10. The Orchestrator (Spec)

### 10.1 What it is

`src/orchestrator.py` is the main loop. It is the thing that receives input from whatever integration or interface is active, decides what to do, and produces a response.

### 10.2 The loop

For each user input:
1. Identify the user
2. Load that user's memory
3. Decide thread — continue current thread or start new one, using the threading system
4. Load that thread's context
5. Run enabled modules as needed (some inputs need no module, some need one, some need more)
6. Produce a response in Gisto's persona
7. Update memory and thread context with anything worth keeping
8. Return the response to the integration/interface that sent it

### 10.3 Module routing

The orchestrator should know which modules are enabled and when to use them. Not every input needs a module. Some inputs are just conversation. Some need a capability — lead find, site build, a Google action, a Discord action. The orchestrator decides based on what the user is asking and what's enabled.

### 10.4 Error handling

If something fails — a module errors, an integration is misconfigured, a key is missing — Gisto reports it clearly and honestly. It does not pretend it worked. It does not expose raw internals the user doesn't need. It tells the user what's wrong in a usable way.

---

## 11. Module System (Spec)

### 11.1 `src/modules/base.py`

Defines the interface every module conforms to. At minimum:
- A module has a name and a description of what it does
- A module can be queried: "can you handle this kind of request?"
- A module can be asked to do something, given context and the user's memory and config
- A module returns a result Gisto can use in its response

### 11.2 `src/modules/registry.py`

Resolves which modules are active from config. Provides the orchestrator a list of enabled modules and a way to ask each one whether it applies to a given request.

### 11.3 `src/modules/personal.py`

Personal assistant capabilities. Things like:
- Remembering and recalling facts
- Notes and drafting
- Planning and organizing
- Research and summarization
- Content ideas
- General conversation in Gisto's persona

Personal is the base. It's what a user gets when they want an assistant, not an agency.

### 11.4 `src/modules/agency.py`

Agency capabilities. Everything in Personal plus:
- Lead finding — find businesses or contacts that fit a criteria (this connects to an integration/data source the user has set up)
- Site building — generate simple websites for leads/clients (this connects to whatever site-building approach the user wires in)
- Outreach — draft and manage outreach sequences
- Client comms — communicate with clients via available integrations
- Project tracking — keep track of clients, jobs, status

Agency is the full version. It should only do things the user has actually configured and given access to. If the user hasn't wired up a data source for lead finding, agency can't magically find leads — it tells the user what it needs.

---

## 12. Integration Adapters (Spec)

### 12.1 `src/integrations/base.py`

Defines the interface every integration adapter conforms to. At minimum:
- An adapter has a name and a description
- An adapter reports whether it's configured (does the user have the keys/credentials it needs?)
- An adapter can receive input from the orchestrator and produce a response or action
- An adapter can be used by the orchestrator when a request needs that service

### 12.2 `src/integrations/discord.py`

Discord adapter. The user supplies:
- Bot token
- Client ID
- Optional guild IDs / channel IDs to restrict to

The adapter should let Gisto read messages and reply in the contexts the user has allowed. It should not assume any particular server or channel. It should fail clearly if the token is missing or invalid.

### 12.3 `src/integrations/slack.py`

Slack adapter. The user supplies:
- Bot token
- Signing secret
- Optional channel IDs to restrict to

Same general shape as Discord: read messages, reply in allowed contexts, fail clearly if misconfigured.

### 12.4 `src/integrations/google.py`

Google adapter. Gives Gisto access to Google services (Gmail, calendar, docs, etc.) for the user. The user supplies OAuth credentials for their own Google project, OR uses Composio as the connector. The adapter should make clear what it needs and what it can do, and fail clearly if not configured.

Do not hardcode any Google credentials. Do not bake in the author's Google project.

### 12.5 `src/integrations/composio.py`

Composio connector layer. If the user chooses to use Composio, this adapter uses the Composio API to connect Gisto to services without the user wiring each one directly. The user supplies their Composio API key. This is an optional path, not the only path.

---

## 13. Home Screen / Dashboard (Spec)

### 13.1 What it is

The home screen is the user-facing UI layer. It's where a user talks to Gisto directly, sees their threads, manages modules and integrations, and gets a sense of what Gisto is doing. It connects to the core via the orchestrator and the integration adapters.

### 13.2 What it should let the user do

At minimum:
- Chat with Gisto directly
- See their threads and jump into one
- Rename, merge, split threads
- See which modules are on/off and toggle them
- See which integrations are configured and their status
- Start onboarding if they skipped it or want to redo it
- Read the docs that ship with the framework

### 13.3 How it connects

The home screen is a consumer of the core. It does not reimplement memory, threading, persona, or orchestrator logic. It talks to the core. Keep the boundary clean.

### 13.4 Form

Build a real usable home screen. The user intends to have Claude set this up, but the framework should not require a specific UI — the home screen is one interface among potentially several (CLI, Discord, Slack, home screen). Whatever you build, make it actually work and make the connection to the core clean.

---

## 14. Docs (Spec)

### 14.1 `docs/setup.md`

Step-by-step first-run setup. Include:
- Installing dependencies
- Copying config.example.yaml to config.yaml
- Filling in config
- Running first run / onboarding
- Setting up each integration one by one, with what credentials each needs
- What to do if something goes wrong

### 14.2 `docs/modules.md`

What each module does, what it can and cannot do, how to toggle it, what it needs to work. Be honest about limitations. If agency can't find leads without a data source, say so.

### 14.3 `docs/architecture.md`

How the pieces fit together. The data flow from input to response. The memory model. The threading model. The module system. The integration adapter system. Enough that someone reading it understands how Gisto is put together and where to add something new.

---

## 15. Constraints and Quality Bar

### 15.1 No hardcoded secrets, ever

No keys, tokens, passwords, or credentials anywhere in source. No personal bot baked in. No personal Google project baked in. The framework is for other people to fill in their own keys. If you catch yourself about to hardcode something, stop and use config.

### 15.2 It must actually run

The framework should be runnable. A user following the setup docs should be able to get Gisto going. Stubs that don't run are not acceptable for the core. If something is not finished, leave it clearly marked as a known limitation, not as a half-implementation that looks complete.

### 15.3 Honest about capabilities

Do not pretend Gisto can do things it can't. If a module needs a service the user hasn't connected, Gisto says so. If an integration isn't configured, Gisto says so. If a feature is not built yet, docs say so. No marketing vaporware in the code or the docs.

### 15.4 Clean boundaries

Memory, threading, persona, modules, integrations, orchestrator, home screen — each is its own concern. Don't let one bleed into another's job. If something is the orchestrator's job, don't put it in the home screen. If something is memory's job, don't put it in the persona.

### 15.5 Clear errors

When something is missing or wrong, tell the user clearly: what's missing, where to put it, what to do. Not a raw traceback as the primary experience. A traceback in the logs is fine; the user-facing message should be usable.

### 15.6 Python

The core framework is Python. Use it properly: virtual environment, requirements.txt, clean imports, no spaghetti. If you add dependencies, list them in requirements.txt and explain why.

---

## 16. What NOT to Do

- Do not hardcode any keys, tokens, passwords, bot tokens, Google credentials, Composio keys, or anything like that.
- Do not bake in the author's personal Discord bot, Slack app, Google project, or any personal credentials.
- Do not name the product Jarvis. The name is Gisto.
- Do not turn Gisto into a JARVIS parody or a hype bot. Calm and capable, not theatrical.
- Do not claim Gisto can do things it cannot do without the right config/integrations.
- Do not build a framework that only works for one specific user's setup. It must work for anyone who fills in their own config.
- Do not over-engineer the storage layer before the rest works. Simple and reliable first.
- Do not leave stubs that look complete but don't run. Either make it work or mark it clearly as not done.
- Do not skip the docs. A framework with no setup docs is not usable.

---

## 17. Working Directory and Setup

**Working directory:** `C:\Users\Student\Desktop\github repos\gisto-AI-assistant`

**Everything in this prompt applies to that directory.** The repo, the source, the home screen, the docs — all of it lives there.

**Python:** Use a virtual environment. List dependencies in `requirements.txt`. Make it possible to install and run from that directory.

**Git:** Initialize the repo. `.gitignore` should exclude `config.yaml`, the memory data directory, virtual environment, `__pycache__`, and any other generated/local artifacts. Do not commit real config or real memory data.

---

## 18. How to Use This Prompt

This is the master build prompt. It defines the entire Gisto project as it should be built. When you work on Gisto, read this first and refer back to it. If you are about to make a decision that conflicts with something here, stop and resolve the conflict rather than silently overriding what's written.

The architecture, the module system, the integration adapter system, the memory model, the threading model, the persona, the onboarding flow, the config system, and the constraints are all specified here. Your job is to implement them as a coherent, runnable framework that another person can set up, configure with their own keys, and use.

Do not summaries this prompt back to the user. Do not ask whether you should follow it. Follow it. If something is ambiguous, pick the interpretation that makes the framework more usable and more honest, and note the choice in a comment or in the docs.

---

*End of CLAUDE.md — master build prompt for Gisto.*

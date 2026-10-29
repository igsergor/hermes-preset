---
name: hermes-multi-agent
description: "Use when setting up Hermes profiles, kanban, delegation."
version: 1.0.0
author: Hermes session (user)
license: MIT
metadata:
  hermes:
    tags: [hermes, profiles, kanban, delegation, multiplexing, telegram, multi-agent]
---

# Hermes Multi-Agent: profiles, kanban, delegation, gateways

Class-level map of the mechanisms users conflate when asking "how do I run
multiple agents in Hermes". Verified against hermes-agent source
(v2026.7.1-4997) and website/docs; routing detail in
`references/routing-and-gateways.md`.

## The mechanisms (do not confuse)

| | Profiles | Kanban workers | delegate_task | Personality (`/personality`) |
|---|---|---|---|---|
| What | Persistent identity: own config, memory, skills, model, sessions under `~/.hermes/profiles/<name>/` | An existing profile spawned as a worker process by the kanban dispatcher | Ephemeral child agent inside current process | Session-level system-prompt overlay |
| Memory between tasks | yes | yes | none — dies after returning summary | no |
| Own model/skills | yes | yes | no (inherits parent unless `delegation.*` override) | no |
| Survives restart | yes | yes | no | no |
| Coordination | — | comments/links/blocks on SQLite board | orchestrator polls children, returns summaries to parent | — |
| Lifespan | permanent | durable | minutes, one turn | one session |

Key facts:
- **delegate_task children are NOT profiles.** No name, no folder, no memory.
  Orchestrator role only grants the child the ability to spawn more ephemeral
  children (bounded by `delegation.max_spawn_depth`). Orchestrators cannot
  spawn profiles directly — but any agent with the `terminal` toolset can run
  `hermes -p <name> chat -q "..."` as a subprocess.
- **Kanban = durable inter-agent communication.** Not free chat: workers
  coordinate via task comments, links (`kanban link` for dependencies), and
  block/unblock. Blocked task = escalation signal; the agent holding
  unblock rights (product/orchestrator profile) resolves disputes. Dispatcher
  in gateway (`kanban.dispatch_in_gateway: true`) auto-spawns assigned
  profiles when tasks become ready, reclaims stale claims, auto-blocks after
  `failure_limit` consecutive failures.
- **Agent communication ≠ bots chatting in a channel.** On Discord/Slack and
  **also Telegram** there is `allow_bots: none|mentions|all` (Telegram:
  `platforms.telegram.extra.allow_bots` → env `TELEGRAM_ALLOW_BOTS`).
  Docs warn two auto-replying agents at `all` ack-loop forever. `mentions`
  (explicit per-turn summons) is the safe mode; default `none` means bot
  messages are rejected at authz before any allowlist check.

## Desktop Bot Mode & remote gateways

- **A desktop Bot IS a profile** (Bot Mode is a UI over `~/.hermes/profiles/`:
  own memory/skills/model/chat; bots message each other and share group
  chats). Do not treat desktop bots as a separate primitive from profiles.
- **Remote-gateway connections are views, not execution movers.** The desktop
  app attaches to a remote dashboard/gateway, but the agent that runs is that
  machine's own profile with its own memory — a home profile never executes
  on the remote host. Execution happens where the session's backend lives.
- **Cross-machine work needs an explicit bridge.** Either bot-to-bot messages
  (desktop group chat, or Telegram `@mention` with `allow_bots: mentions` —
  the phone-reachable bus that needs no VPN), or the home backend reaching
  the other host over SSH/WinRM. Kanban boards do NOT sync across machines
  (per-machine SQLite) — kanban is for same-machine durability, mentions for
  cross-machine handoff.

## Dashboard Profiles page (web UI)

- **BUILD** → full builder at `/profiles/new` (ProfileBuilderPage.tsx): 5 steps
  Identity → Model → Skills → MCPs → Review. Nothing written to disk until the
  final single `POST /api/profiles`. Skills use REPLACE semantics: default
  bundle seeded server-side, unkept seeded skills get disabled; "Start from
  full bundle" toggle keeps everything.
- **Create (СОЗДАТЬ)** → quick modal: name, clone-from (existing profile),
  description, model. Everything else default.
- Card menu **⋮** includes Edit SOUL.md — the closest thing to Grok-style
  "create a bot": profile + SOUL.md = named personality with isolated
  memory/skills. There is no dedicated "Bots" gallery page in the web UI
  (checked web/src/pages/ as of 2026-09); `/personality` presets
  (agent.personalities in config.yaml) are the lightweight alternative.

## Delegation config (config.yaml)

```yaml
delegation:
  max_concurrent_children: 3
  max_spawn_depth: 2        # >1 enables orchestrator children (was 1 on user's box, raised 2026-09)
  orchestrator_enabled: true
  child_timeout_seconds: 600
```
Takes effect on new session (`/reset`), not mid-conversation.

## Choosing a topology for "multiple agents working together"

- Need profile with own memory/skills on durable tasks → **kanban** (canonical).
- Need parallel subtasks right now, token economy via context isolation →
  **delegate_task** (intermediate tool output stays in child).
- Need several named bots user can summon per message in Telegram → **one bot
  token per profile, one gateway per profile** (`require_mention: true`,
  `exclusive_bot_mentions: true` — default; @botA @botB in one message is
  processed by both, others silent).
- Need one token, thread-per-profile hard binding → **gateway.multiplex_profiles
  + gateway.profile_routes** (static config, restart to change; no
  dynamic "/profile <name>" slash command exists to rebind a thread).
- One shared bot token polled by two running gateways → Telegram rejects
  concurrent polling; also a config-error skip in multiplex mode.

## RAM constraint pattern (user's host)

3.8G RAM, prior oom-kill. One gateway process per profile adds footprint —
prefer `multiplex_profiles: true` when >2-3 profiles, keep secondary profiles
on light models. Multiplex mode: single inbound process serves all profiles,
each keeps own credentials/sessions (`agent:<profile>:...` namespace, default
stays `agent:main:`), secondary profiles must NOT bind ports (webhook,
api_server, sms, etc. → config error skips whole profile) and must not run
their own `gateway start` (hard error pointing at the multiplexer).

## Pitfalls

- Profile routes match most-specific-first (thread_id > chat_id > guild_id);
  a chat_id route also matches threads whose parent is that chat — so a
  group-wide route shadows any thread you forgot to add explicitly.
- Route naming a nonexistent profile = warning + fallback to default home,
  not an error.
- Tool/skill changes apply on `/reset`; config changes on gateway `/restart`.
  Delegation depth is read at session start.
- Deletion of an active profile with running gateway triggers a warning
  confirm in the dashboard (gateway_running_warning).

## References

- `references/routing-and-gateways.md` — profile_routes / multiplexing /
  dm_topics / multi-bot Telegram / **Telegram bot-to-bot (`allow_bots`)**
  config detail with source file pointers.

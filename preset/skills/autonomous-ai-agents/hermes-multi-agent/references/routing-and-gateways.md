# Routing & gateway reference (verified 2026-09, hermes-agent v2026.7.1-4997)

Source pointers are relative to `~/.hermes/hermes-agent/`.

## 1. One bot token per profile (recommended for Telegram "summon per message")

Docs: `website/docs/user-guide/messaging/telegram.md` → "Multiple Hermes bots in one group".

- One Telegram bot token per profile, one gateway per profile:
  `hermes -p <name> gateway install/start`.
- Group config: `require_mention: true`, `exclusive_bot_mentions: true` (default).
  With it, `@botA @botB question` is processed by botA and botB only; other
  Hermes bots in the group stay silent even on replies/wake-words. Do NOT
  reuse one token across two running gateways — Telegram rejects concurrent
  polling.
- Dashboard equivalent per profile; user creates a new thread ("плюсиком") and
  just mentions whichever bot they want — no per-thread config needed.
  Binding is per-message mention, not per-thread, so agents can be switched
  mid-thread.

## 2. Multiplexing + profile_routes (one token, static thread→profile binding)

Docs: `website/docs/user-guide/multi-profile-gateways.md`.

```yaml
gateway:
  multiplex_profiles: true
  profile_routes:
    - name: work-thread
      platform: telegram
      chat_id: "-100xxxxxxxxxx"
      thread_id: "11189"        # most-specific-first: thread > chat > guild
      profile: work
```

- Requires `multiplex_profiles: true`; routes ignored otherwise.
- Matched profile gets full isolation: config, skills, memory, SOUL,
  credentials, session namespace (`agent:<profile>:...`; default keeps
  `agent:main:` — no migration).
- No match → default/active profile.
- **Static**: editing routes requires a gateway restart. There is NO
  `/profile <name>`-style slash command to rebind a running thread
  (checked hermes_cli/commands.py registry). Hard binding per thread.
- Route on a chat_id also matches threads whose parent is that chat — a
  group-wide route shadows unlisted threads.
- Route naming a nonexistent profile: warning + fallback to default home.
- Multiplex contract: secondary profiles must not run `gateway start` (hard
  error), must not enable port-binding platforms (webhook, api_server,
  msgraph_webhook, feishu, wecom_callback, bluebubbles, sms, whatsapp_cloud,
  line — else the whole profile is skipped with a naming warning). HTTP
  traffic for secondary profiles: `/p/<profile>/...` prefix on the default
  listener, auth follows the profile in the URL (`API_SERVER_KEY` from that
  profile's `.env`).
- Credentials never unioned across profiles — subprocesses (MCP, kanban
  workers) only see their own profile's secrets.

## 3. DM topics (private chat, Bot API 9.4)

Docs: telegram.md → "Private Chat Topics".

- User must enable Topics toggle in the DM manually (bot can't).
- `platforms.telegram.extra.dm_topics:` list of `{chat_id, topics:[{name,
  icon_color, skill, thread_id}]}`; Hermes auto-creates topics lacking
  `thread_id` and writes the id back to config.yaml.
- `skill:` field auto-loads a skill in new sessions of that topic.
- Topic sessions keyed `agent:main:telegram:dm:{chat_id}:{thread_id}`.
- `ignore_root_dm: true` turns root DM into a lobby (system commands only).
- Topics created manually are auto-discovered from `forum_topic_created`.
- Cron delivery in topic mode: set `TELEGRAM_CRON_THREAD_ID`.
- `telegram.ignored_threads` silences specific topics.

## 4. Bot-to-bot messaging (Discord / Slack / **Telegram**)

- `allow_bots: none|mentions|all` (Slack: `platforms.slack.extra.allow_bots`
  / `SLACK_ALLOW_BOTS`; Discord: `DISCORD_ALLOW_BOTS`; **Telegram:
  `platforms.telegram.extra.allow_bots` → env `TELEGRAM_ALLOW_BOTS`**).
- **Telegram has the flag too** (contrary to what the docs pages imply —
  verified in source 2026-09): adapter maps config key to env at startup
  (`plugins/platforms/telegram/adapter.py` ~line 9911: `if "allow_bots" in
  telegram_cfg and not os.getenv("TELEGRAM_ALLOW_BOTS")`). The authz gate is
  platform-neutral (`gateway/authz_mixin.py` ~line 464-473: `is_bot=True`
  messages are REJECTED unless `<PLATFORM>_ALLOW_BOTS` is `mentions|all`;
  bypasses user allowlists per #4466; checked before the no-user-id guard).
- Telegram adapter stamps `is_bot` from `message.from_user.is_bot`
  (`adapter.py` ~line 9635) — peer Hermes bots are detected natively.
- Docs warning: two auto-replying agents at `all` ack-loop indefinitely
  (Discord auto-@mentions on reply satisfy each other's mention gate); there
  is no circuit breaker. `mentions` = accept only messages that @mention this
  bot, breaks ack-loops by design. Thread history/replies don't count as
  mentions.
- **Multi-bot dialog pattern in one Telegram thread** (verified design):
  one token per profile + `require_mention: true` + `exclusive_bot_mentions:
  true` (default) + `allow_bots: "mentions"` on every profile → agents call
  each other by @mention per message, user can switch agents mid-thread and
  summon two bots at once. MANDATORY guardrail: each profile's system prompt
  (SOUL.md) must say "@mention a peer bot only when the task genuinely
  requires it, never in thanks/final answers" — no loop breaker exists
  server-side, discipline is prompt-level. Never use `all` for agent-to-agent.
- Docs page telegram.md doesn't mention the Telegram flag (as of 2026-09) and
  recommends one-token-per-profile for groups; the flag is the piece that
  makes that fleet able to talk to itself.

## 5. Kanban coordination model

Docs: `website/docs/user-guide/features/kanban.md`, `kanban-tutorial.md`,
`kanban-worker-lanes.md`.

- CLI verbs: init, create, list/ls, show, assign, link, unlink, comment,
  complete, block, unblock, archive, tail, watch, stats, runs, log, dispatch,
  daemon, gc.
- Worker toolset (dispatcher-spawned): kanban_show, kanban_complete,
  kanban_block, kanban_heartbeat, kanban_comment, kanban_create, kanban_link.
  Profiles with explicit `kanban` toolset also get kanban_list/kanban_unblock
  (broader rights — who can unblock others' work).
- Dispatcher in gateway (`kanban.dispatch_in_gateway: true`): reclaims stale
  claims, promotes ready tasks (respects dependency links), atomically
  claims, spawns assigned profiles. Auto-blocks task after
  `kanban.failure_limit` (default 2) consecutive spawn failures; per-task
  `max_retries` overrides.
- Boards are the hard boundary (workers get `HERMES_KANBAN_BOARD` pinned);
  tenant = soft namespace for workspace-path + memory-key isolation.
- Escalation pattern: blocked task + comments = the "dispute thread";
  resolution always by whoever holds unblock/assign rights. Disputes are not
  auto-resolved; auditable via `kanban log/show`.

## 6. delegate_task vs profiles

Docs: `website/docs/user-guide/features/delegation.md`.

- Children: no identity, no persistence, model inherited (or global
  `delegation.model/provider` override — cannot set per-call).
- Roles: leaf (default, no re-delegation) / orchestrator (can spawn children
  up to `delegation.max_spawn_depth`).
- Config (user's current): max_concurrent_children=3, max_spawn_depth=2
  (raised from 1 on 2026-09-16 via `hermes config set`), orchestrator_enabled
  =true, child_timeout_seconds=600, subagent_auto_approve=false.
- Depth/env changes take effect on next session, not mid-conversation.
- Orchestrator cannot create profiles; workaround: child with terminal
  toolset runs `hermes -p <profile> chat -q "..."` (one-shot) or tmux for
  interactive (prompt_toolkit needs real PTY; tmux recommended over raw PTY
  due to \r\n issues).

## 7. Personality / "Grok-style bots"

Docs: `website/docs/user-guide/features/personality.md`.

- No "Bots" gallery page in dashboard (checked web/src/pages/ 2026-09).
- SOUL.md = durable identity (slot #1 of system prompt, loaded only from
  HERMES_HOME so cwd doesn't change personality). Dashboard: profile card
  ⋮ → "Редактировать SOUL.md".
- `/personality [preset|custom]` = session overlay, stack position 8 (after
  SOUL, tool guidance, memory, skills, context files, timestamp, platform
  hints). Built-ins: helpful, concise, technical, creative, teacher, kawaii,
  catgirl, pirate, shakespeare, surfer, noir, uwu, philosopher, hype.
- Custom named personalities: `agent.personalities.<name>: >` in config.yaml.
- Profile + SOUL.md = the durable "bot" equivalent.

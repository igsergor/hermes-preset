# Configuration, Toolsets & Voice

Edit with `hermes config edit` or `hermes config set section.key value`.
Full reference: https://hermes-agent.nousresearch.com/docs/user-guide/configuration

### Config Sections (most-used keys)

| Section | Key options |
|---------|-------------|
| `model` | `default`, `provider`, `base_url`, `api_key`, `context_length`, `aliases` |
| `agent` | `max_turns` (90), `tool_use_enforcement`, `service_tier`, `verify_on_stop`, `reasoning_effort`, `reasoning_overrides` |
| `terminal` | `backend` (local/docker/ssh/modal/daytona/singularity), `cwd`, `timeout` (180) |
| `compression` | `enabled`, `threshold` (0.50), `target_ratio` (0.20) |
| `display` | `skin`, `interface` (cli/tui), `language`, `show_reasoning`, `show_cost`, `pet` |
| `approvals` | `mode` (smart/manual/off), `timeout`, `cron_mode` |
| `stt` | `enabled`, `provider` (local/groq/openai/mistral/elevenlabs/deepinfra) |
| `tts` | `provider` (edge/elevenlabs/openai/minimax/mistral/neutts/gemini/piper/kittentts/deepinfra/xai) |
| `memory` | `memory_enabled`, `user_profile_enabled`, `provider`, `write_approval` |
| `security` | `redact_secrets`, `tirith_enabled`, `website_blocklist` |
| `delegation` | `model`, `provider`, `max_concurrent_children`, `max_iterations` (50), `max_spawn_depth` |
| `browser` | `engine`, `cdp_url`, `use_real_profile` (false), `inactivity_timeout` |
| `curator` | `enabled`, `consolidate` (false, opt-in aux-model consolidation), `interval_hours`, `stale_after_days` |

`hermes config check` reports sections missing from an older config.

### Reasoning effort (global + per model)

Two knobs, per-model wins. `hermes_constants.resolve_reasoning_config` is the single chokepoint for every surface (CLI, gateway, TUI, cron, `/model`, fallback activation).

| Key | Scope |
|-----|-------|
| `agent.reasoning_effort` | every model without an override; `""` = provider default, `false` = disabled |
| `agent.reasoning_overrides` | map of model id → level, that model only |

- Levels: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, `ultra`. Bare strings are strict — a typo is ignored with a warning and never reaches the wire; the dict form `{enabled: true, effort: <tier>}` passes a provider-specific tier verbatim.
- "Set reasoning <level> for the default model" means a per-model override on the id in `model.default`, not the global key — the global key also re-levels every other model the user did not ask about.
- **Dot-escape model ids that contain dots** in the config key, or `hermes config set` builds bogus nested segments: `hermes config set agent.reasoning_overrides.deepseek-v4\\.1-flash-1017 high` (quote the argument in the shell). `_split_key_path` honors the backslash.
- Matching is spelling-tolerant (`_canonical_model_variants`: dots↔dashes, provider prefix stripped, reverse lookup of `provider/model` keys), so a bare slug key is enough and a prefixed key still matches the bare string a fallback swap feeds.
- Per-run: `hermes --reasoning high`, or in-session `/model <id> --reasoning high [--once]`. Subagents take `delegation.reasoning_effort`; cron jobs and `auxiliary.<task>.reasoning_effort` set their own.
- Applies on the next session: a live session resolved `reasoning_config` at startup and re-resolves only on `/model` or a switch/fallback. Do not restart the gateway to apply it — state that it lands in a new session and leave running processes alone unless the user asks.
- Verify before reporting: `scripts/check_reasoning.py` (run with the checkout's `venv/bin/python`) prints the effective config for the default model plus any ids passed as arguments. Write such probes to a file — piping an inline heredoc into `python3 -` can trip the gateway command guard.

### Real-profile browsing (use your own logins)

Off by default (`browser.use_real_profile: false`; desktop toggle at Capabilities → Tools → Browser → "Use My Real Browser Profile"). When on, Hermes copies the active Chromium-family profile (cookies, saved logins, preferences) into a managed snapshot under the Hermes directory and drives the copy with its own Chromium — the live profile is never opened directly (avoids the profile lock and the Chrome ≥136 remote-debugging block on the default profile). Auth files re-sync from the real profile on every fresh session. Pin one profile when several exist (a pin naming a nonexistent profile fails closed, no fallback); turning the toggle off deletes the snapshot store on next browser use.

Upstream framing, quote as the rule: consent-gated convenience, not an isolation boundary — every page the agent visits runs with the user's real logins, so enable it only when the agent should act as the user. Platform caveats: on macOS Chrome cookies are Keychain-encrypted, so a copied profile can open logged-out; on Windows the browser must be fully closed including background processes or the files stay locked. Supported: Chrome, Edge, Brave, Chromium — a Firefox default stops with a notice.

### Toolsets

Enable/disable via `hermes tools` (interactive) or `hermes tools enable/disable NAME`.
Full enumeration: `TOOLSETS` dict in `toolsets.py` (`_HERMES_CORE_TOOLS` is the default bundle most platforms inherit).

| Toolset | What it provides |
|---------|-----------------|
| `web` / `search` | Web search + extraction / search-only subset |
| `browser` | Browser automation (Browserbase, Camofox, or local Chromium) |
| `terminal` | Shell commands and process management |
| `file` | File read/write/search/patch |
| `code_execution` | Sandboxed Python execution |
| `coding` | Code-editing helpers (LSP-backed) |
| `computer_use` | Desktop GUI control (cua-driver) |
| `vision` | Image analysis |
| `image_gen` | Image generation and image-to-image editing |
| `video` / `video_gen` | Video analysis / video generation |
| `x_search` | X (Twitter) search (X OAuth or API key) |
| `tts` | Text-to-speech |
| `skills` | Skill browsing and management |
| `memory` | Persistent cross-session memory |
| `session_search` | Search past conversations |
| `context_engine` | Pluggable context-engine hooks |
| `project` | Named multi-folder workspace tools |
| `delegation` | Subagent task delegation |
| `cronjob` | Scheduled task management |
| `clarify` | Ask user clarifying questions |
| `todo` | In-session task planning |
| `kanban` | Multi-agent work-queue tools (gated to workers) |
| `debugging` | Extra introspection tools (off by default) |
| `safe` | Minimal low-risk toolset for locked-down sessions |
| `spotify`, `homeassistant`, `discord`, `discord_admin`, `feishu_doc`, `feishu_drive`, `yuanbao` | Service integrations (gated on their credentials) |

Tool changes take effect on `/reset` (new session) — never mid-conversation, to preserve prompt caching.

## Voice

### STT (Voice → Text)

Voice messages from messaging platforms are auto-transcribed.

```yaml
stt:
  enabled: true
  provider: local   # local (faster-whisper, free) | groq | openai | mistral | elevenlabs | deepinfra
  local:
    model: base     # tiny, base, small, medium, large-v3
```

Auto-detect priority: local faster-whisper (`python -c "import pm; pm.sync_venv(['stt-whisper'], explicit=True)"`) → Groq (`GROQ_API_KEY`, free tier) → OpenAI (`VOICE_TOOLS_OPENAI_KEY`) → Mistral Voxtral (`MISTRAL_API_KEY`).

### TTS (Text → Voice)

| Provider | Env var | Free? |
|----------|---------|-------|
| Edge TTS (default) | None | Yes |
| ElevenLabs | `ELEVENLABS_API_KEY` | Free tier |
| OpenAI | `VOICE_TOOLS_OPENAI_KEY` | Paid |
| MiniMax | `MINIMAX_API_KEY` | Paid |
| Mistral | `MISTRAL_API_KEY` | Paid |
| Gemini | `GOOGLE_API_KEY` | Free tier |
| NeuTTS / Piper / KittenTTS (local) | None | Free |

Voice commands: `/voice on` (voice-to-voice), `/voice tts` (always voice), `/voice off`.

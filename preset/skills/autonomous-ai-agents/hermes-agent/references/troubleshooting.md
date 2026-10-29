# Troubleshooting

### Voice not working
1. Check `stt.enabled: true` in config.yaml
2. Verify provider: `python -c "import pm; pm.sync_venv(['stt-whisper'], explicit=True)"` or set API key
3. In gateway: `/restart`. In CLI: exit and relaunch.

### Tool not available
1. `hermes tools` — check if toolset is enabled for your platform
2. Some tools need env vars (check `.env`)
3. `/reset` after enabling tools

### Model/provider issues
1. `hermes doctor` — check config and dependencies
2. `hermes auth` — re-authenticate OAuth providers (or `hermes auth add <provider>`)
3. Check `.env` has the right API key
4. **Copilot 403**: `gh auth login` tokens do NOT work for Copilot API. You must use the Copilot-specific OAuth device code flow via `hermes model` → GitHub Copilot.

### Changes not taking effect
- **Tools/skills:** `/reset` starts a new session with updated toolset
- **Config changes:** In gateway: `/restart`. In CLI: exit and relaunch.
- **Code changes:** Restart the CLI or gateway process

### web_extract shows a stale page (result caching)
`web_search`/`web_extract` cache results for 20 minutes (PR #94618) — a
repeat fetch of the same URL within the TTL is served from cache, which
can look like "my website changes aren't showing up."

Automatic carveouts (always fetched live, never cached):
- localhost / 127.0.0.1 / `*.local` / `*.localhost` / single-label LAN
  hostnames / private + link-local IP ranges (dev servers, hot-reload
  builds, chat-GUI artifact previews)
- URLs matched by `security.website_blocklist`
- failed responses and keyless-rescue-served responses

Developing a site tested over the PUBLIC internet (Vercel/Netlify
preview, ngrok/cloudflared tunnel, staging domain)? Public DNS isn't
auto-carved-out — list the host in config.yaml:

```yaml
web:
  cache_exempt_hosts:      # always fetched live; effective immediately
    - mysite.vercel.app
    - "*.ngrok-free.app"
    - mysite.dev           # suffix match: also covers preview.mysite.dev
```

Blunt instruments: `web.cache_ttl_minutes: 1` (min) or
`web.cache_enabled: false` disables both caches entirely.

### Skills not showing
1. `hermes skills list` — verify installed
2. `hermes skills config` — check platform enablement
3. Load explicitly: `hermes -s name` (or the skill's own `/<name>` slash command)

### Gateway issues
Check logs first:
```bash
grep -i "failed to send\|error" ~/.hermes/logs/gateway.log | tail -20
```

Common gateway problems:
- **Telegram goes deaf/blind (no replies at all)**: see "Telegram silent" below.
- **Gateway dies on SSH logout**: Enable linger: `sudo loginctl enable-linger $USER`
- **Gateway dies on WSL2 close**: WSL2 requires `systemd=true` in `/etc/wsl.conf` for systemd services to work. Without it, gateway falls back to `nohup` (dies when session closes).
- **Gateway crash loop**: Reset the failed state: `systemctl --user reset-failed hermes-gateway`

### Telegram silent (adapter never registered at startup)
Symptom: the gateway process is alive and cron still runs, but Telegram never answers. Confirm in logs:
```bash
grep "Failed to load plugin 'telegram-platform'\|No adapter available for telegram" ~/.hermes/logs/*.log | tail
```
Root cause is usually the per-plugin load deadline, not Telegram being down: the `telegram-platform` plugin has a
~7500-line adapter, so a slow/loaded box can push import + `register()` past the default `plugins.load_timeout_seconds: 10`
and the plugin is skipped for that process ("called register_platform() after its load timed out; ignored"). A restart may
not fix it if plugin discovery itself stalls (no `Plugin discovery complete` line) — that is load (swap/RAM), not Telegram.
Fix (config, survives `hermes update`):
```bash
hermes config set plugins.load_timeout_seconds 60   # 0 = no deadline (risks a hung start), max 600
systemctl --user restart hermes-gateway
```
Look for `✓ telegram connected` in `~/.hermes/logs/gateway.log` afterwards. Telegram's own connect ladder
(`HERMES_TELEGRAM_INIT_TIMEOUT`, default 30s per attempt, 8 attempts, DoH fallback IPs) runs AFTER the plugin loads, so
lowering it does not fix this symptom — only the load deadline matters.

### Telegram thread stuck on "paused: unknown_execution" after gateway restart
Turn was lost mid-flight across an unclean gateway restart. Every message gets `Session <id> paused: unknown_execution` + "Send /reset or ask the operator to resume". `/resume` does NOT clear it (`Already on session`). Fix from server: `hermes sessions discard <session_id> --yes` (clears the lost admission; input is acknowledged, not replayed — user resends it). Verify in `~/.hermes/logs/gateway.log`: next turn ends with `response ready` + `[Telegram] Sending response`.
When the user reaches Hermes exclusively through a messaging platform and that platform is the one down, the agent
cannot self-report. Give the user a one-line recovery they can paste into any OTHER agent/console they have, and keep a
copy of it locally so a future session can surface it immediately. Template:
```
systemctl --user restart hermes-gateway; sleep 20; tail -30 ~/.hermes/logs/gateway.log
```
Also tell them where the dashboard is (`hermes dashboard`, typically :9119) as a fallback channel.

### Platform-specific issues
- **Discord bot silent**: Must enable **Message Content Intent** in Bot → Privileged Gateway Intents.
- **Slack bot only works in DMs**: Must subscribe to `message.channels` event. Without it, the bot ignores public channels.
- **Windows-specific issues** (`Alt+Enter` newline, WinError 10106, UTF-8 BOM config, line endings): see `references/windows-quirks.md`.

### Auxiliary models not working
If `auxiliary` tasks (vision, compression, session_search) fail silently, the `auto` provider can't find a backend. Either set `OPENROUTER_API_KEY` or `GOOGLE_API_KEY`, or explicitly configure each auxiliary task's provider:
```bash
hermes config set auxiliary.vision.provider <your_provider>
hermes config set auxiliary.vision.model <model_name>
```

### "Reset permissions" / auto-approving everything
See `references/security-privacy.md` — wipe the "Always allow" stores, don't touch yolo mode.


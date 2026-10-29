# Session 2026-07-19: Daily Updates Check Script Evolution

## Context
User asked to fix the daily updates cron job (job_id: 09fc0b6ad529) which was failing with exit code 139 (segfault). Then requested "include ALL possible updates" — the script was expanded to cover every package manager and tool category.

## Cron Job
- **Job ID**: `09fc0b6ad529`
- **Name**: "Ежедневная проверка обновлений системы"
- **Schedule**: `0 9 * * *` (daily 09:00)
- **Deliver**: `origin` (this thread)
- **Mode**: `no_agent=true` (script output delivered directly)
- **Script**: `~/.hermes/skills/devops/system-audit/scripts/daily-updates-check.sh`

## Script Evolution

### v1 (initial) — Segfaulted
- Had `opencode` in CLI tools check → crashed with SIGSEGV
- No timeout wrappers on version checks
- Limited to apt, npm, cargo, pip, snap, flatpak, few binaries

### v2 (fixed segfault)
- Removed `opencode` from version check (crashes with `--version`)
- Added `timeout 5` to all binary version checks
- Added `set -euo pipefail`
- Still limited scope

### v3 (comprehensive — current production)
Full coverage of all package managers + generic binary scan:
- APT (packages, security, kernel)
- fwupdmgr (firmware)
- npm/pnpm/yarn/bun/deno
- pip/uv/poetry
- cargo/rustc
- go modules
- brew/nix
- snap/flatpak/appimage
- docker/podman images
- gem/ruby
- **Hermes Agent** (pip version + git upstream check)
- **Generic binary scan** — finds anything in common bin dirs not covered by known managers
- Cleanup hints

## Key Design Decisions

1. **`no_agent=true`** — avoids LLM rate limits (429), script output delivered directly
2. **All external commands wrapped in `timeout`** — prevents hangs/segfaults from killing the whole script
3. **`set -euo pipefail`** — fail fast on errors, but individual timeouts handled gracefully
4. **Generic binary scan** — future-proofs against new tools user installs manually
5. **Hermes Agent check** — dual source: pip version (reliable) + git upstream (detects upstream changes even if not pip-installed)

## Output Format
Telegram-ready Markdown with emoji status indicators:
- 🔴 = updates available
- ✅ = up to date
- ⚪ = not installed
- ℹ️ = info/hint

## Files Updated
- `scripts/daily-updates-check.sh` — production script (v3)
- `SKILL.md` — documentation updated to v2.0.0 with full table

## Testing
```bash
# Manual test
~/.hermes/scripts/daily-updates-check.sh

# Cron job test run
cronjob action=run job_id=09fc0b6ad529
```
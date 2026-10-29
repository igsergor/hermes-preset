---
name: system-audit
description: "System audits: infrastructure (VPN/proxy/network), system updates, and session analytics. Use when auditing servers, checking for updates, or analyzing Hermes session activity."
version: 2.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [audit, infrastructure, VPN, updates, session-analytics, monitoring]
    related_skills: [system-audit]
---

# System Audit

Three audit domains: infrastructure (VPN/proxy/network), system updates, and Hermes session analytics.

## Quick Decision Guide

| Task | Section |
|------|---------|
| Audit VPN, proxy, network infrastructure | → §1 Infrastructure Audit |
| Check for system/software updates | → §2 System Update Audit |
| Advise on OS/distro release upgrade (is it worth it, what breaks) | → §4 Distro Upgrade Advisory |
| Analyze Hermes session activity & costs | → §3 Session Analytics |

---

## §0 Disk/Swap Thrash Diagnosis

Symptom: «HDD постоянно шумит/работает» на машине с нехваткой RAM.

Chain of causation (typical): RAM exhausted → swap 100% full → page cache squeezed to ~400MB → every snap/browser process constantly re-reads code from disk (10s-100s MB/s) → looks like «swapping works» but reads dominate, not swap writes.

Diagnostic sequence:
1. `vmstat 1 5` — si/so nonzero + bi huge (hundreds MB/s) = thrash; `cat /proc/pressure/io memory`
2. `free -h; swapon --show` — swap full?
3. Per-proc swap: loop `/proc/*/status` VmSwap sorted — finds who sits in swap (e.g. llama-server 2.2GB)
4. `pidstat -d 1 5` — who reads now; `/proc/PID/io` read_bytes cumulative
5. `iostat -xz 2 3` — vda rkB/s; loop24-style loop device with high reads = snap squashfs re-read (snap firefox)
6. Root cause fix: free the swap occupant — `ollama stop <model>` instantly frees GB of swap on 8GB box (verify: free -h, swap usage drops immediately).

Server ubuntuai facts: 8GB RAM / 3.8G swapfile / vda=virtual disk ROTA=1, read_ahead=8MB (qemu default). Ollama override: KEEP_ALIVE=24h NUM_PARALLEL=2 (bge-m3 embeddings, used by obsidian memory) — on an 8GB box this permanently occupies 2.3GB; model reloads into RAM on demand anyway. sudo needs password (NOPASSWD only for reboot/hiddify) — sysctl/systemd changes must be handed to user as commands.

## §1 Infrastructure Audit

Audit VPN, proxy, gateway, router, or network infrastructure devices.

### Workflow

1. **Gather** — OS, version, running services, network interfaces, IP addresses, routing table
2. **Collect configs** — iptables/nft, ip rule, routing tables, ALL config files
3. **Trace packet flow** — Draw the path a packet takes end-to-end before reporting
4. **Test from RIGHT perspective** — TPROXY only catches FORWARDED traffic, not traffic originating from the device itself
5. **Report with evidence** — Show what IS and ISN'T working

### TPROXY Architecture

```
LAN client → PREROUTING → TPROXY rule → mark packet → deliver to local process (e.g. sing-box)
Server's own curl → OUTPUT chain → DIRECT (no TPROXY)
```

**CRITICAL**: Testing from the server with `curl` does NOT test the proxy. TPROXY only intercepts forwarded traffic. Check iptables counters and proxy logs instead.

### MikroTik RouterOS SSH Tips

- Command length limit: ~190 chars per SSH call
- Use `print detail` for full output
- Disabled rules show as `X` in flags
- Check routing tables: `/routing table print`

### Behavioral Rules

- **Don't ask the user to debug for you** — SSH in and investigate yourself
- **Recognize upstream blocking vs local config failure** — distinct failures with distinct evidence
- **Don't form conclusions before exhausting remote diagnostics**

---

## §2 System Update Audit

Check for available system updates on Ubuntu/Debian servers.

### What's Covered

| Source | Check Method |
|---|---|
| APT packages | `apt list --upgradable` |
| Snap packages | `snap refresh --list` |
| Hermes Agent | `git rev-list HEAD..origin/main` |
| OpenCode | GitHub API `anomalyco/opencode` releases |
| uv | PyPI JSON API |
| Node.js | `nodejs.org/dist/index.json` |
| npm global | `npm outdated -g --json` |
| CPU microcode | `dpkg-query` vs `apt-cache policy` |
| Kernel | `dpkg-query` vs `apt-cache policy` |

### Key Pitfalls

- **APT output format**: `pkg/repo version arch [upgradable from: oldver]`
- **OpenCode versioning**: Binary at `~/.opencode/bin/opencode`, latest from `api.github.com/repos/anomalyco/opencode/releases/latest` (NOT `opencode-ai/opencode`)
- **Hermes update**: `hermes --version` shows current, `hermes update` restarts gateway

**Daily Reports (System Updates)**

Two scripts available:

**1. Comprehensive check** (`check-updates.sh`) — all sources including firmware, kernels, multiple package managers:
```bash
~/.hermes/skills/devops/system-audit/scripts/check-updates.sh
```

**2. Daily cron job** (`daily-updates-check.sh`) — **comprehensive system-wide** checking, used by cron job `09fc0b6ad529`:
```bash
~/.hermes/skills/devops/system-audit/scripts/daily-updates-check.sh
```

**Create cron job (no_agent=true = script output delivered directly):**
```bash
cronjob action=create name="Ежедневная проверка обновлений системы" \
  schedule="0 9 * * *" deliver="origin" \
  no_agent=true script="~/.hermes/skills/devops/system-audit/scripts/daily-updates-check.sh"
```

**What the comprehensive script checks (v2026.07.19):**
| Source | Method |
|--------|--------|
| APT packages | `apt list --upgradable` (security vs regular) |
| APT Security | `apt list --upgradable \| grep -i security` |
| Kernel | `apt list --installed \| grep linux-image` + version compare |
| Firmware (fwupd) | `fwupdmgr refresh && fwupdmgr get-updates` |
| NPM global | `npm outdated -g --parseable` |
| PNPM global | `pnpm outdated -g --parseable` |
| YARN global | `yarn global outdated --json` |
| BUN | version check + `bun upgrade` hint |
| DENO | version check + `deno upgrade` hint |
| CARGO (Rust) | `cargo install --list` + rustc version |
| PIP (Python) | `pip3 list --outdated --format=freeze` + pip version |
| UV (Python) | version check + `uv self update` hint |
| POETRY | version check |
| SNAP | `snap refresh --list` |
| FLATPAK | `flatpak remote-ls --updates` |
| APPIMAGE | AppImageUpdate presence |
| DOCKER | `docker images` (local images, hint to pull) |
| PODMAN | version check |
| GO modules | `go list -u -m all` (if go.mod exists) + go version |
| NODE/NPM | version + nvm/fnm/volta detection |
| RUBY/GEMS | `gem outdated` + ruby version |
| HOMEBREW | `brew outdated` + brew version |
| NIX | version + update hint |
| AI CLI (claude/codex/cursor) | version check + common install paths |
| CLI tools (gh, docker, kubectl, helm, terraform, ansible, etc) | version check |
| VS Code extensions | `code --list-extensions --show-versions` |
| **HERMES AGENT** | `hermes --version` + git upstream check + pip version |
| Generic binary scan | scans `/usr/local/bin`, `~/.local/bin`, `~/.cargo/bin`, `~/.npm-global/bin`, `~/.hermes/node/bin`, `~/bin` — finds anything not in known managers |
| System cleanup hints | apt/snap/flatpak/docker/pip/npm/cargo/journal |

All external commands wrapped in 5-20s timeouts, script runs with `set -euo pipefail` and exits cleanly.

**Output format** — concise Telegram-ready:
```
🔄 System Update Check — 2026-06-11 09:00
📦 APT Packages
🐧 15 update(s) available
⚠️  Security: 8
  • apparmor: 4.0.1...6 → 4.0.1...7
  ...
📋 Regular: 7
...
🧊 Snap Packages
1 update(s) available
🤖 Hermes Agent
✅ Up to date (v0.x.x)
🧩 OpenCode
— Not installed
🐍 uv Package Manager
✅ Up to date (0.x.x)
🟢 Node.js
✅ Up to date (v22.x.x)
📦 npm Global Packages
2 package(s) outdated
  • npm: 10.9.8 → 11.16.0
  • corepack: 0.34.6 → 0.35.0
🔧 CPU Microcode
✅ intel-microcode (3.20250211.1)
🖥️  Kernel
✅ Kernel up to date (6.8.0-x)
─────────────────────
📊 Total: 18 update(s)
⚠️  8 security update(s) — prioritize!
```

**Why not LLM prompt:** The previous approach hit provider 429 rate limits. Script is deterministic, fast, and free.

---

---

## §4 Distro Upgrade Advisory

User asks whether the host should move to a newer OS release. **Read
`references/distro-upgrade-advisory.md` and follow it end to end** — host profile
probes, release-notes extraction, the change categories that break a live server
(kernel/OpenSSH/NTP-daemon/Wayland-only/removals/toolchains), and the verdict
format (profile → what's new for his role → numbered stay/upgrade reasons).

Two rules that decided real verdicts: an HWE kernel already at the new LTS's
major removes the headline upgrade motive, and free disk under ~25% of root is a
hard no-go for a release upgrade on a live server.

---

## §3 Session Analytics

Analyze Hermes session activity from SQLite state.db.

### Data Source

**Always use `~/.hermes/state.db`** — session JSON files do NOT contain token usage.

Key columns: `id`, `source`, `model`, `started_at`, `message_count`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `estimated_cost_usd`, `actual_cost_usd`.

**⚠️ Many columns are NULLable** — always use `COALESCE(column, 0)` in SQL queries.

### Week Boundaries

User's week = **пн-вс (Mon-Sun) in UTC+7** (user refers to this as "MSK+4"):

```python
from datetime import datetime, timezone, timedelta
tz = timezone(timedelta(hours=7))
# Last full week (Mon-Sun)
today = datetime.now(tz)
days_since_monday = today.weekday()
last_mon = today - timedelta(days=days_since_monday + 7)
week_start = last_mon.replace(hour=0, minute=0, second=0, microsecond=0)
week_end = week_start + timedelta(days=7)  # exclusive
```

### Running the Analysis

Use the bundled script (preferred for cron jobs):

```bash
python3 ~/.hermes/skills/devops/system-audit/scripts/analyze_snapshots.py
```

Or run ad-hoc via `terminal` with Python heredoc (**`execute_code` is BLOCKED in cron mode**):

```bash
python3 << 'PYEOF'
import sqlite3
from datetime import datetime, timezone, timedelta
# ... (see references/state-db-schema.md for query templates)
PYEOF
```

### Cost Calculation (CRITICAL)

`estimated_cost_usd` does NOT include `cache_read_tokens` cost. Calculate separately.

**⚠️ OpenRouter dashboard uses RETAIL pricing (no cache discount).** The retail/wholesale coefficient is ~1.6x. Always use retail prices for cost reports.

**Current retail pricing (June 2026):**

| Model | Input/1M | Output/1M | Cache Read/1M | Notes |
|-------|----------|-----------|---------------|-------|
| deepseek/deepseek-v4-pro | $0.692 | $1.383 | $0.692 | Retail; cache = input rate (no discount) |
| openrouter/owl-alpha | $0.00 | $0.00 | $0.00 | **FREE** |
| nvidia/nemotron-3-ultra:free | $0.00 | $0.00 | $0.00 | Free |
| nvidia/nemotron-3-super-120b-a12b:free | $0.00 | $0.00 | $0.00 | Free |

```python
PRICING_RETAIL = {
    'deepseek/deepseek-v4-pro':                {'in': 0.692, 'out': 1.383, 'cache_read': 0.692},
    'openrouter/owl-alpha':                    {'in': 0.0,   'out': 0.0,   'cache_read': 0.0},  # FREE
    'nvidia/nemotron-3-ultra:free':            {'in': 0.0,   'out': 0.0,   'cache_read': 0.0},
    'nvidia/nemotron-3-super-120b-a12b:free':  {'in': 0.0,   'out': 0.0,   'cache_read': 0.0},
}

# DeepSeek V4 Pro cost (retail, no cache discount):
# cost = (input_tokens + cache_read_tokens) * 0.692 / 1M + output_tokens * 1.383 / 1M
```

### Report Format (Russian)

```
📊 Снапшоты — неделя DD.MM-DD.MM
📁 Сессии: X total | Telegram X | TUI X | Cron X
🤖 Модели (sessions/in/out/cache)
🔢 Токены: Input X.XM | Output XXXK | Cache XX.XM
💰 DeepSeek V4 Pro: (in+cache) $X.XX + out $X.XX = ИТОГО $X.XX
🏆 Топ-10 сессий
📈 Baseline
```

### Pitfalls

- **Always use state.db for tokens** — session JSON files have no token data
- **`actual_cost_usd` is often $0`** — use `estimated_cost_usd`
- **Use RETAIL pricing for cost reports** — OpenRouter dashboard counts at retail rates; coefficient retail/wholesale ≈ 1.6x
- **Owl Alpha is FREE** — never include in cost totals
- **Cache read cost dominates** — typically 70-80% of total cost
- **`execute_code` is BLOCKED in cron mode** — use `terminal` with `python3 << 'PYEOF'` heredoc instead
- **Many columns are NULLable** — always use `COALESCE(column, 0)` in SQL queries and `row['col'] or 0` in Python
- **Week boundaries in UTC+7** — user's "MSK+4" = UTC+7 timezone for пн-вс week calculation

### Reference Files

- `references/state-db-schema.md` — full schema, query templates, NULL handling
- `references/cache-cost-findings.md` — pricing research, retail vs wholesale, cost calculation
- **`references/session-2026-07-19-daily-updates.md` — daily updates script evolution, cron job setup, testing
- `references/distro-upgrade-advisory.md` — §4: host profile probes, reading long release-notes pages, change categories that break a running host, verdict format
- `scripts/html_to_text.py` — strip an HTML docs page to text so long release notes can be grepped by section
- `scripts/analyze_snapshots.py` — ready-to-run snapshot analyzer (use via `terminal`, not `execute_code`)
- `scripts/daily-updates-check.sh` — production daily updates checker (cron job `09fc0b6ad529`)
- `scripts/check-updates.sh` — simpler update checker

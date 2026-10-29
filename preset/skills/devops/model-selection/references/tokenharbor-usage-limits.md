# TokenHarbor: usage & allowance monitoring (verified 2026-09-15)

## TL;DR

- **No public usage/limits API.** Probed with a live `thk_live_...` key:
  `/me /user /account /usage /limits /credits /balance /quota /subscription /billing /dashboard`, `/api/me /api/usage /api/credits /api/v1/*`, with both `Authorization: Bearer` and `x-api-key` → all 404 (HTML catch-all; `/dashboard` `/subscription` only 307-redirect to login). `/v1/models` returns 200 but no rate-limit headers and no usage metadata (top-level just `object`/`data`).
- **Exact remaining allowance: only the web dashboard** — tokenharbor.ai →
  **Dashboard → Billing**. Docs (/docs/billing/subscription) say literally:
  "Current usage and remaining allowance are shown in the dashboard".
  Dashboard needs browser login (Supabase auth at auth.tokenharbor.ai); the
  API key does NOT authenticate it.
- **OmniRoute can't see TH quota either**: no `quota_snapshots` / `provider_plans`
  rows for the TH connection; OmniRoute management API
  (`/api/stats|/api/usage|/api/metrics|/api/requests`) returns 403
  `AUTH_001 "Invalid management token"` with the Bearer API key — `/api/*`
  needs dashboard-cookie auth (same as other `/api/*` calls).
- **What works: local usage accounting** from OmniRoute's SQLite + $ estimation
  from TH's published per-token prices. Script:
  `scripts/tokenharbor_usage.py [days]` (deployed copy:
  `~/.hermes/scripts/tokenharbor_usage.py`).

## Local usage accounting from OmniRoute's SQLite

OmniRoute logs every proxied call to `~/.omniroute/storage.sqlite`. Open
read-only — safe while WAL is active:
`sqlite3.connect('file:~/.omniroute/storage.sqlite?mode=ro', uri=True)`

- Table `usage_history`: `provider, model, connection_id, account_label,
  tokens_input, tokens_output, tokens_cache_read, tokens_cache_creation,
  tokens_reasoning, status, success, latency_ms, ttft_ms, error_code, timestamp`.
- **Trap:** a custom openai-compatible node logs under its canonical id
  `openai-compatible-chat-<uuid>` (e.g. `...e62cc7bb-782c-4da0-b0bc-8c286d31ea31`
  for TokenHarbor), NOT the friendly prefix `th`. Discover via
  `select provider, count(*), max(timestamp) from usage_history group by provider`.
  The uuid changes if the TH connection is recreated — re-derive, don't trust
  the hardcoded default in the script.
- Also available: `call_logs/` JSON files per request (summary.tokens),
  `daily_usage_summary` / `hourly_usage_summary` tables.

## Estimating $ spend against the Pass allowance

1. **Prices**: scrape the catalog page `https://tokenharbor.ai/models` — the
   Next.js payload embeds escaped JSON; regex works:
   `surface\":\"<model-id>\", ... priceIn\":X,\"priceOut\":Y, ... isFree\":true|false`
   → $/Mtok in/out per model (~21 models priced as of 2026-09-15). No JSON API
   for the catalog (`/api/models` → 404).
2. **Cost model** used: `in×pin + out×pout + cache_read×pin×0.1` per Mtok.
   Cache-read discount assumed 0.1× (TH docs advertise prompt-cache savings
   up to 90%) — good enough for an estimate. Free models (`:free`,
   `isFree=true`) cost 0.
3. Several catalog surfaces have no price on the page (th-orchestra,
   claude-opus-4.8, kimi-k2.6, ...) — in practice their traffic was ~0 tokens,
   so the underestimate is negligible; check before trusting for other mixes.

## Pass structure (from /docs/billing/subscription, 2026-09-15)

- Passes: **Agent** $1.99/mo — $10 allowance (≈$20 value with Model Boost,
  PAYG −5%); **Office** $9.99 — $35 (≈$70, −10%); **Frontier** $99 — $180
  (≈$360, −15%). Allowance = subsidized *usage value*, NOT wallet credit;
  shared across all Pass-eligible models (boosted models consume it slower).
- **4-week cycle split into 4× 7-day windows — ¼ of the allowance each, NO
  rollover between windows.**
- After exhaustion: toggle in Billing — "Keep working after my Pass allowance
  runs out". On → continue via wallet PAYG at the Pass discount (hard spending
  cap still applies). Off → Pass is a hard usage limit until the next window.
- Free-tier allowance (`:free` models) is separate and unaffected by the Pass;
  resets on its own period.
- glm-5.3-flash is Agent-Pass-tier (tier gating / 402s: see
  `tokenharbor-glm-reasoning.md`).

## Calibration data point (2026-09-15)

~71M tokens / ≈$6.47 over 5 days, 99.9% on glm-5.3-flash ($0.15/$0.50 in/out);
peak day $2.86 (359 req, 17M in + 13M cache-read). Iginy's glm-5.3-flash-heavy
Hermes traffic ≈ $2–3/day → a $10 Agent-Pass window (¼ of 4 weeks) lasts
roughly 3–4 days at that rate.

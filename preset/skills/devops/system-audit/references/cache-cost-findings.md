# Session Snapshot Analytics — Key Findings

## The Cache Cost Bug (CRITICAL)

**Discovered: 2026-06-01**

The `estimated_cost_usd` field in `state.db → sessions` table does **NOT** include `cache_read_tokens` cost. This causes massive underreporting.

### Why this happens

Hermes tracks `estimated_cost_usd` from the provider's pricing API, but cache read pricing is often returned separately or not at all. The `cost_status` field shows:
- `estimated` — provider returned pricing (only 6 sessions, all DeepSeek V4 Pro)
- `unknown` — provider didn't return pricing (146 sessions, all Owl Alpha)

## OpenRouter Pricing — RETAIL vs Wholesale

**OpenRouter dashboard uses RETAIL pricing (no cache discount).** The retail/wholesale coefficient is ~1.6x.

When the user asks for cost reports, always use **retail** prices to match what the OpenRouter dashboard shows.

### Current Retail Pricing (June 2026)

| Model | Input/1M | Output/1M | Cache Read/1M | Notes |
|-------|----------|-----------|---------------|-------|
| deepseek/deepseek-v4-pro | $0.692 | $1.383 | $0.692 | Retail; cache = input rate (no discount!) |
| openrouter/owl-alpha | $0.00 | $0.00 | $0.00 | **FREE** |
| nvidia/nemotron-3-ultra:free | $0.00 | $0.00 | $0.00 | Free |
| nvidia/nemotron-3-super-120b-a12b:free | $0.00 | $0.00 | $0.00 | Free |

**⚠️ Owl Alpha is FREE.** Do not include in cost calculations.

**Note:** Prices change. Verify at https://openrouter.ai/models before reporting.

## How to calculate correctly (retail)

```python
# Retail pricing — matches OpenRouter dashboard
PRICING_RETAIL = {
    'deepseek/deepseek-v4-pro':  {'in': 0.692, 'out': 1.383, 'cache_read': 0.692},
    'openrouter/owl-alpha':      {'in': 0.0, 'out': 0.0, 'cache_read': 0.0},  # FREE
}

# DeepSeek V4 Pro cost (retail, no cache discount):
# cost = (input_tokens + cache_read_tokens) * 0.692 / 1M + output_tokens * 1.383 / 1M
ds_cost = (ds_in + ds_cache) * 0.692 / 1_000_000 + ds_out * 1.383 / 1_000_000
```

**No token scaling needed** — use raw DB token counts with retail prices. The 1.348x OR_SCALE from earlier findings is already factored into the retail pricing.

## Model Usage Patterns

- **Owl Alpha** — main workhorse, ~90% of sessions, **FREE**
- **DeepSeek V4 Pro** — heavy sessions, ~36% of tokens from only 5 sessions, all cost
- **Nemotron (free)** — occasional free model usage, $0 cost

## Cost Breakdown by Source (week 26.05-01.06)

| Source | Sessions | Tokens | Cost |
|--------|----------|--------|------|
| Telegram | 32 | 11.6M | ~$17.61 (all DS V4 Pro) |
| TUI | 4 | 4.8M | included in above |
| Cron | 128 | 1.1M | $0 (all Owl Alpha, free) |

Cron sessions are numerous but cheap (short, automated, free model). TUI sessions are few but expensive (long interactive sessions with DeepSeek V4 Pro).

## Cron Mode Pitfall

**`execute_code` is BLOCKED in cron jobs.** Use `terminal` with Python heredoc instead:

```bash
python3 << 'PYEOF'
import sqlite3
# ... your code ...
PYEOF
```

## NULL Handling

Many columns in the `sessions` table are NULLable. Always use `COALESCE`:

```python
# Python
inp = row['input_tokens'] or 0

# SQL
SUM(COALESCE(input_tokens, 0)) as total_input
```

Columns that can be NULL: `input_tokens`, `output_tokens`, `cache_read_tokens`, `message_count`, `tool_call_count`, `api_call_count`, `title`, `ended_at`, `actual_cost_usd`, `estimated_cost_usd`.

## Week Boundaries

User's week = пн-вс (Mon-Sun) in **UTC+7** timezone (referred to as "MSK+4" by user).

```python
from datetime import datetime, timezone, timedelta
tz = timezone(timedelta(hours=7))
week_start = datetime(2026, 6, 15, 0, 0, 0, tzinfo=tz)  # Monday
week_end = datetime(2026, 6, 22, 0, 0, 0, tzinfo=tz)    # Next Monday (exclusive)
```

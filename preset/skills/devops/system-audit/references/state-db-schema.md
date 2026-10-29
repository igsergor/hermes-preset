# state.db Reference

## Location
`~/.hermes/state.db`

## Key Table: `sessions`

```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    source TEXT,           -- 'telegram', 'tui', 'cron'
    model TEXT,
    model_config TEXT,
    system_prompt TEXT,
    parent_session_id TEXT,
    started_at REAL,       -- unix timestamp
    ended_at REAL,
    end_reason TEXT,
    message_count INTEGER,
    tool_call_count INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cache_read_tokens INTEGER,
    cache_write_tokens INTEGER,
    reasoning_tokens INTEGER,
    billing_provider TEXT,
    billing_base_url TEXT,
    billing_mode TEXT,
    estimated_cost_usd REAL,
    actual_cost_usd REAL,
    cost_status TEXT,
    cost_source TEXT,
    pricing_version TEXT,
    title TEXT,
    api_call_count INTEGER,
    handoff_state TEXT,
    handoff_platform TEXT,
    handoff_error TEXT
);
```

## Key Table: `messages`

```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY,
    session_id TEXT,
    role TEXT,             -- 'system', 'user', 'assistant', 'tool'
    content TEXT,
    tool_call_id TEXT,
    tool_calls TEXT,       -- JSON array
    tool_name TEXT,
    timestamp REAL,
    token_count INTEGER,
    finish_reason TEXT,
    reasoning TEXT,
    reasoning_content TEXT,
    reasoning_details TEXT,
    codex_reasoning_items TEXT,
    codex_message_items TEXT,
    platform_message_id TEXT,
    observed INTEGER
);
```

## Useful Queries

### Weekly token summary by source

```sql
-- Week boundaries in UTC+7
WITH bounds AS (
  SELECT 
    strftime('%s', datetime('now', '+7 hours', 'weekday 0', '-7 days', 'start of day')) AS week_start,
    strftime('%s', datetime('now', '+7 hours', 'weekday 0', 'start of day')) AS week_end
)
SELECT 
  source,
  model,
  COUNT(*) AS sessions,
  SUM(COALESCE(message_count, 0)) AS messages,
  SUM(COALESCE(input_tokens, 0)) AS input_tokens,
  SUM(COALESCE(output_tokens, 0)) AS output_tokens,
  SUM(COALESCE(estimated_cost_usd, 0)) AS est_cost,
  SUM(COALESCE(actual_cost_usd, 0)) AS act_cost
FROM sessions, bounds
WHERE started_at >= week_start
  AND started_at < week_end
GROUP BY source, model
ORDER BY est_cost DESC;
```

### Top-K sessions by total tokens

```sql
WITH bounds AS (
  SELECT 
    strftime('%s', datetime('now', '+7 hours', 'weekday 0', '-7 days', 'start of day')) AS week_start,
    strftime('%s', datetime('now', '+7 hours', 'weekday 0', 'start of day')) AS week_end
)
SELECT id, source, model, message_count,
       COALESCE(input_tokens,0) AS input_tokens,
       COALESCE(output_tokens,0) AS output_tokens,
       (COALESCE(input_tokens,0) + COALESCE(output_tokens,0)) AS total_tokens,
       COALESCE(estimated_cost_usd, 0) AS est_cost
FROM sessions, bounds
WHERE started_at >= week_start
  AND started_at < week_end
ORDER BY total_tokens DESC
LIMIT 10;
```

### Session count by source (last 7 days)

```sql
SELECT source, COUNT(*),
       SUM(COALESCE(input_tokens,0)),
       SUM(COALESCE(output_tokens,0))
FROM sessions
WHERE started_at >= strftime('%s', 'now', '-7 days')
GROUP BY source;
```

## Time Zone Handling

User's week = **Mon-Sun in UTC+7** (referred to as "MSK+4").

```python
from datetime import datetime, timezone, timedelta
tz = timezone(timedelta(hours=7))
today = datetime.now(tz)
days_since_monday = today.weekday()
last_mon = today - timedelta(days=days_since_monday + 7)
week_start = last_mon.replace(hour=0, minute=0, second=0, microsecond=0)
week_end = week_start + timedelta(days=7)

# Unix timestamps for SQL
week_start_ts = int(week_start.timestamp())
week_end_ts = int(week_end.timestamp())
```

## Running Analysis

```bash
# Full weekly report (used by cron)
python3 ~/.hermes/skills/devops/system-audit/scripts/analyze_snapshots.py

# Or ad-hoc query
sqlite3 ~/.hermes/state.db "
  SELECT model, COUNT(*), SUM(COALESCE(input_tokens,0)), SUM(COALESCE(output_tokens,0))
  FROM sessions
  WHERE started_at >= strftime('%s', 'now', '-7 days')
  GROUP BY model;
"
```

## Notes

- **state.db is the ONLY source for token usage** — session JSON files don't contain tokens
- The `analyze_snapshots.py` script outputs Telegram-ready markdown with:
  - Per-session token breakdown (input/output/total)
  - Top-10 sessions by tokens
  - Weekly totals + comparison to baseline
  - Cost estimates
- Cron job uses this script directly (no_agent=true for deterministic output)
- **Many columns are NULLable** — always use `COALESCE(column, 0)` in SQL and `row['col'] or 0` in Python. Known NULLable: `input_tokens`, `output_tokens`, `cache_read_tokens`, `message_count`, `tool_call_count`, `api_call_count`, `title`, `ended_at`, `estimated_cost_usd`, `actual_cost_usd`, `cache_write_tokens`, `reasoning_tokens`.
- **Week boundaries in UTC+7** — user's "MSK+4" = UTC+7 timezone for Mon-Sun week calculation.
- **`execute_code` is BLOCKED in cron mode** — use `terminal` with `python3 << 'PYEOF'` heredoc instead.
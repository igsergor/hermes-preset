# Token Cost Calculation — Methodology & DeepSeek V4 Pricing

## Token Types in state.db

| Field | Meaning | Billing |
|-------|---------|---------|
| `input_tokens` | New prompt tokens (cache miss) | Full input price |
| `output_tokens` | Generated response tokens | Output price |
| `cache_read_tokens` | Reused context from cache (cache hit) | ~98-99% discount |
| `cache_write_tokens` | Tokens written to cache | Usually free (DeepSeek ≤128K) |
| `reasoning_tokens` | Thinking/reasoning tokens | Billed as output (if model supports it) |

## DeepSeek V4 Pricing (May 2026, from api-docs.deepseek.com)

### V4 Flash
| Token Type | Price per 1M |
|-----------|-------------|
| Input (cache miss) | $0.14 |
| Cache hit | $0.0028 (98% discount) |
| Cache write | Free (≤128K context) |
| Output | $0.28 |
| Reasoning | Same as output ($0.28) |

### V4 Pro
| Token Type | Price per 1M |
|-----------|-------------|
| Input (cache miss) | $0.435 |
| Cache hit | $0.003625 (99% discount) |
| Cache write | Free (≤128K context) |
| Output | $0.87 |
| Reasoning | Same as output ($0.87) |

## Cost Formula

```
total_cost = (
    input_tokens × input_price +
    output_tokens × output_price +
    cache_read_tokens × cache_hit_price
) / 1_000_000
```

## How to Query Token Usage

Use `execute_code` to query `~/.hermes/state.db` (sqlite3 CLI may not be installed):

```python
import sqlite3, os
conn = sqlite3.connect(os.path.expanduser("~/.hermes/state.db"))
cursor = conn.cursor()
cursor.execute("""
    SELECT id, title, source, model,
           input_tokens, output_tokens, cache_read_tokens,
           cache_write_tokens, reasoning_tokens, api_call_count
    FROM sessions
    ORDER BY started_at DESC
""")
for row in cursor.fetchall():
    print(row)
conn.close()
```

## Key Insight: Cache Dominance

In typical usage, cache_read_tokens are 90-95% of total tokens. The system prompt, tools, skills, and conversation history are cached after the first request, so subsequent requests only pay the cache hit rate for reused context.

Example from real usage (54.3M total tokens):
- Input (cache miss): 3,987,588 (7.3%) → $0.56
- Output: 199,118 (0.4%) → $0.06
- Cache read (hit): 50,094,336 (92.3%) → $0.14
- **Total at V4 Flash rates: $0.75**

Without caching (all tokens at full input price): ~$7.50

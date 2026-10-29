# ClinePass Live API Reference

## Model Discovery

Cline's IDE/CLI gets its model list from:

```
GET https://api.cline.bot/api/v1/ai/cline/recommended-models
Authorization: Bearer sk-...
```

Source: `sdk/packages/llms/src/catalog/catalog-cline-recommended.ts` in `github.com/cline/cline`

### Response structure (as of 2026-08-21)

```json
{
  "recommended": [
    {"id": "moonshotai/kimi-k3", "name": "kimi-k3", "description": "...", "tags": ["NEW"]},
    {"id": "anthropic/claude-opus-5", "name": "claude-opus-5", "description": "", "tags": ["NEW"]},
    {"id": "x-ai/grok-4.5", "name": "grok-4.5", "description": "...", "tags": ["NEW"]},
    {"id": "openai/gpt-5.6-sol", "name": "gpt-5.6-sol", "description": "...", "tags": ["NEW"]}
  ],
  "free": [
    {"id": "stealth/ox-alpha", "name": "ox-alpha", "description": "..."},
    {"id": "deepseek/deepseek-v4-flash", "name": "deepseek-v4-flash", "description": "..."},
    {"id": "poolside/laguna-s-2.1:free", "name": "laguna-s-2.1:free", "description": "..."}
  ],
  "clinePass": [
    {"id": "cline-pass/deepseek-v4-flash", "name": "cline-pass/deepseek-v4-flash", "description": "..."},
    {"id": "cline-pass/glm-5.3", "name": "cline-pass/glm-5.3", "description": "..."},
    {"id": "cline-pass/kimi-k2.6", "name": "cline-pass/kimi-k2.6", "description": "..."},
    {"id": "cline-pass/kimi-k2.7-code", "name": "cline-pass/kimi-k2.7-code", "description": "..."},
    {"id": "cline-pass/minimax-m3", "name": "cline-pass/minimax-m3", "description": "..."},
    {"id": "cline-pass/qwen3.7-plus", "name": "cline-pass/qwen3.7-plus", "description": "..."},
    {"id": "cline-pass/kimi-k3", "name": "cline-pass/kimi-k3", "description": "..."},
    {"id": "cline-pass/qwen3.8-max", "name": "cline-pass/qwen3.8-max", "description": "..."},
    {"id": "cline-pass/qwen3.7-max", "name": "cline-pass/qwen3.7-max", "description": "..."},
    {"id": "cline-pass/deepseek-v4-pro", "name": "cline-pass/deepseek-v4-pro", "description": "..."},
    {"id": "cline-pass/glm-5.2", "name": "cline-pass/glm-5.2", "description": "..."},
    {"id": "cline-pass/mimo-v2.5-pro", "name": "cline-pass/mimo-v2.5-pro", "description": "..."},
    {"id": "cline-pass/mimo-v2.5", "name": "cline-pass/mimo-v2.5", "description": "..."}
  ]
}
```

## ClinePass Limits (from `/api/v1/plans`)

The plans endpoint reveals actual inference cap thresholds:

```
GET https://api.cline.bot/api/v1/plans
Authorization: Bearer sk-...
```

| Plan | Interval | Price | Inference Cap Thresholds |
|------|----------|-------|-------------------------|
| ClinePass (Monthly) | Monthly | $9.99 | 5h: $1,000, 7d: $2,500, 30d: $5,000 |
| ClinePass (Annual) | Annual | $79.92 | Same thresholds |
| Cline Seats: Pro (Monthly) | Monthly | $30/seat | Not specified |

The thresholds are in **USD cost-equivalent**, not token counts. With most models averaging ~$0.0001-0.003/request:
- 5h: ~330,000+ requests before hitting limit
- 7d: ~830,000+
- 30d: ~1,670,000+

Effectively **uncapped for normal individual use**.

## How Cline Internally Constructs Its Model Picker

1. Fetches `recommended-models` endpoint (live data)
2. Falls back to hardcoded `CLINE_RECOMMENDED_MODELS_FALLBACK` if endpoint is unavailable
3. Cross-references against OpenRouter catalog (`openRouterModels`) for context windows, pricing, and capabilities
4. Model names derived from OpenRouter catalog when available, otherwise uses entry's `name` field
5. Free models on the ClinePass provider ride usage-billing at $0 (not subscription quota)

See `sdk/packages/llms/src/catalog/catalog-cline-recommended.ts` lines 90-110 for the mapping logic.
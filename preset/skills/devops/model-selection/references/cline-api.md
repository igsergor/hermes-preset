# Cline API (app.cline.bot) — OpenAI-Compatible Provider for Hermes

## Overview

**Cline** (cline.bot) is an open-source AI coding agent (VS Code extension, CLI, SDK) that provides an **OpenAI-compatible Chat Completions API** at `https://api.cline.bot/api/v1`. 

This allows using Cline as a **custom provider** in Hermes Agent — single API key gives access to models from Anthropic, OpenAI, Google, Minimax, DeepSeek, etc. through a unified endpoint.

---

## Configuration for Hermes

```bash
hermes config set model.provider custom
hermes config set model.base_url "https://api.cline.bot/api/v1"
hermes config set model.api_key "sk_..."  # Your Cline API key from app.cline.bot
hermes config set model.default "minimax/minimax-m2.5"  # Or any supported model
```

**Verified working** — tested with `minimax/minimax-m2.5` (free model).

---

## API Details

| Parameter | Value |
|-----------|-------|
| **Base URL** | `https://api.cline.bot/api/v1` |
| **Chat Endpoint** | `POST /chat/completions` |
| **Models Endpoint** | `GET /models` (requires auth, returns 401/404 in tests) |
| **Auth** | `Authorization: Bearer <api_key>` |
| **Format** | OpenAI Chat Completions (streaming + non-streaming) |
| **Model ID Format** | `provider/model-name` (e.g., `anthropic/claude-sonnet-4-6`) |

---

## Supported Models (from docs)

| Model ID | Provider | Notes |
|----------|----------|-------|
| `anthropic/claude-sonnet-4-6` | Anthropic | Best coding, reasoning support |
| `openai/gpt-4o` | OpenAI | Multimodal (images) |
| `google/gemini-2.5-pro` | Google | 1M context, reasoning |
| `deepseek/deepseek-chat` | DeepSeek | Fast, cheap |
| `minimax/minimax-m2.5` | Minimax | **Free**, reasoning support |
| `x-ai/grok-3` | xAI | Reasoning |
| `qwen/qwen3-235b-a22b` | Alibaba | MoE architecture |

**Plus many more** — see [Cline Models Reference](https://docs.cline.bot/api/models) and verified list in `references/cline-models-verified.md`.

---

## ClinePass Models (Subscription Tier)

If you have an active **ClinePass** subscription ($9.99/month), the **same API key** gives access to ClinePass models with **2-5x higher rate limits** across 3 windows (5-hour, weekly, monthly).

**Model ID format:** `cline-pass/<model-slug>`

| Model ID | Base Model | Notes |
|----------|------------|-------|
| `cline-pass/glm-5.3` | GLM-5.3 | Latest |
| `cline-pass/glm-5.2` | GLM-5.2 | |
| `cline-pass/kimi-k3` | Kimi K3 | |
| `cline-pass/kimi-k2.7-code` | Kimi K2.7 Code | Coding-optimized |
| `cline-pass/kimi-k2.6` | Kimi K2.6 | |
| `cline-pass/deepseek-v4-pro` | DeepSeek V4 Pro | |
| `cline-pass/deepseek-v4-flash` | DeepSeek V4 Flash | |
| `cline-pass/mimo-v2.5-pro` | MiMo V2.5 Pro | |
| `cline-pass/mimo-v2.5` | MiMo V2.5 | |
| `cline-pass/minimax-m3` | MiniMax M3 | |
| `cline-pass/qwen3.8-max` | Qwen 3.8 Max | |
| `cline-pass/qwen3.7-max` | Qwen 3.7 Max | |
| `cline-pass/qwen3.7-plus` | Qwen 3.7 Plus | |

**Verified working** — tested `cline-pass/minimax-m3` with standard API key on ClinePass-enabled account.

Full ClinePass model list: https://docs.cline.bot/getting-started/clinepass#models

---

## Streaming Response

Default is `stream: true`. Returns Server-Sent Events (SSE):

```json
data: {"id":"gen-...","choices":[{"delta":{"role":"assistant"},"index":0}],"model":"..."}
data: {"id":"gen-...","choices":[{"delta":{"content":"Hello"},"index":0}],"model":"..."}
data: {"id":"gen-...","choices":[{"delta":{"content":"!"},"index":0}],"model":"..."}
data: {"id":"gen-...","choices":[{"delta":{},"finish_reason":"stop","index":0}],"model":"...","usage":{"prompt_tokens":14,"completion_tokens":8,"cost":0.000066}}
data: [DONE]
```

Final chunk includes `usage` with token counts and cost.

---

## Reasoning Models

Models with reasoning support (Claude, Gemini 2.5, Grok 3, etc.) return:
- `delta.reasoning` — thinking content during streaming
- `delta.reasoning_details` — encrypted reasoning blocks (some providers)
- `usage.completion_tokens_details.reasoning_tokens` — separate count

**Reasoning tokens count as OUTPUT tokens** for billing.

---

## Cost Model

Each model has its own pricing (provider-set). The API returns `cost` in USD per request in the usage object.

Example (Minimax free): `cost: 0` with `is_byok: true` (Bring Your Own Key model).

---

## Integration Notes for Hermes

1. **Custom provider** — No built-in "cline" provider in Hermes; use `model.provider: custom`
2. **Model switching** — Use `/model provider/model-name` in Telegram or `--model` CLI flag
3. **Reasoning** — `/reasoning high|xhigh|off` works for models where Hermes detects `supports_reasoning` prefix (anthropic/, openai/, google/, deepseek/, x-ai/, qwen/qwen3, tencent/, xiaomi/)
4. **Session-scoped overrides** — `/model` without `--global` affects only current Telegram topic/session
5. **Token tracking** — Usage returned in `usage` object; Hermes logs to `state.db`

---

## Getting an API Key

1. Go to https://app.cline.bot
2. Sign in (GitHub/Google/Email)
3. Navigate to API keys section
4. Create new key → copy (format: `sk_...`)

---

## Limitations / Gotchas

- `/models` endpoint may not work (returns 404/Not Found even with auth) — rely on docs for model list
- Some models return "model not found" — use exact ID from docs (`provider/model-name`)
- Free models (Minimax) may have rate limits
- No public benchmarks for all models — test qualitatively
- API is relatively new; may have occasional issues

---

## Verification Commands

```bash
# Test chat completion
curl -s -H "Authorization: Bearer YOUR_KEY" \
  -H "Content-Type: application/json" \
  "https://api.cline.bot/api/v1/chat/completions" \
  -X POST -d '{"model":"minimax/minimax-m2.5","messages":[{"role":"user","content":"hi"}]}'

# Test via Hermes
hermes chat -q "test" --model minimax/minimax-m2.5
```

---

## Related

- [Cline API Docs](https://docs.cline.bot/api/overview)
- [Cline Models Reference](https://docs.cline.bot/api/models)
- [OpenRouter Integration](references/openrouter-deepseek-v4.md) — similar multi-provider pattern
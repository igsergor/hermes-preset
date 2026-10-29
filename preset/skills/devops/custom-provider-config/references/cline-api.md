# Cline API Reference

## Base URL
```
https://api.cline.bot/api/v1
```

## Endpoints
- `POST /chat/completions` — OpenAI-compatible chat completions
- **There is NO `/v1/models` endpoint.** All `GET /models` paths return 404. Model list must be manually maintained in `custom_providers` — no auto-discovery.

## Free Models (critical limitation)
**Free models are NOT available through the Cline API.** The docs explicitly state: "Free model usage is not supported through the Cline API. Free models are only available in the Cline IDE Extension and CLI."

Free model promotions are periodic, rotating, and only accessible by:
- VS Code extension: Settings → API Provider → Cline → look for FREE-tagged models
- Cline CLI: `/settings` → select Cline → browse free models

After free quota: ClinePass ($9.99/mo) or Cline usage-billing (pay-as-you-go).
```
Authorization: Bearer <API_KEY>
```
API keys created at: https://app.cline.bot → Settings → API Keys

## Model ID Format
All models use `provider/model-name` format (like OpenRouter):
- Regular: `anthropic/claude-sonnet-4-6`, `openai/gpt-4o`, `minimax/minimax-m2.5`
- ClinePass: `cline-pass/qwen3.7-max`, `cline-pass/minimax-m3`, etc.

## ClinePass Models (13 total) — TESTED WORKING 2026-08-19

| Model ID | Resolved Model | Tokens (test) | Cost (test) | Notes |
|----------|----------------|---------------|-------------|-------|
| `cline-pass/glm-5.3` | `zai/glm-5.3` | 277 | $0.001180 | |
| `cline-pass/glm-5.2` | `private/glm-5p2-wave-cline` | 226 | $0.000955 | Cline private deploy |
| `cline-pass/kimi-k3` | `moonshotai/kimi-k3` | 308 | $0.003314 | Most expensive |
| `cline-pass/kimi-k2.7-code` | `private/kimi-k2p7-wave-cline` | 68 | $0.000408 | Code specialist |
| `cline-pass/kimi-k2.6` | `moonshotai/kimi-k2.6` | 84 | $0.000509 | |
| `cline-pass/deepseek-v4-pro` | `deepseek/deepseek-v4-pro` | 85 | $0.000398 | Best price/performance |
| `cline-pass/deepseek-v4-flash` | `private/deepseek-v4-flash-wave-cline` | 157 | $0.000203 | Fast/cheap |
| `cline-pass/mimo-v2.5-pro` | `xiaomi/mimo-v2.5-pro` | 428 | **$0.000000** | Free tier |
| `cline-pass/mimo-v2.5` | `xiaomi/mimo-v2.5` | 367 | **$0.000000** | Free tier |
| `cline-pass/minimax-m3` | `minimax/minimax-m3` | 173 | **$0.000040** | Near-free |
| `cline-pass/qwen3.8-max` | `private/qwen3p8-max-wave-cline` | 84 | $0.000423 | Top Qwen |
| `cline-pass/qwen3.7-max` | `private/qwen3p7-max-wave-cline` | 242 | $0.002933 | Expensive |
| `cline-pass/qwen3.7-plus` | `alibaba/qwen3.7-plus` | 244 | $0.000377 | Good balance |

**Key findings:**
- All 13 models work with active ClinePass subscription
- Many resolve to `private/*-wave-cline` (Cline's private deployments)
- MiMo V2.5/Pro and MiniMax M3 show near-zero cost
- Kimi K3 and Qwen 3.7 Max are costliest in ClinePass
- **No GPT models in the ClinePass tier** — the 13 `cline-pass/*` models are the only ones on subscription. Don't suggest `gpt-*`/`openai/gpt-*` as a ClinePass option; regular `openai/gpt-*` IDs require a separate (non-pass) billing.

## Context Lengths (per ClinePass model)

ClinePass `POST /chat/completions` and `GET /models` do **not** return context-length metadata, so Hermes falls back to its static catalog (`agent/model_metadata.py` → `DEFAULT_CONTEXT_LENGTHS`, substring-matched longest-first). These are the authoritative values Hermes will use unless you set a per-model `context_length` override in `custom_providers[].models.<id>`. Caution: models that resolve to `private/*-wave-cline` deployments may have a different *actual* window than the base model's spec.

| Model | Hermes uses | Status |
|-------|-------------|--------|
| `glm-5.3` | 202,752 (~200K) | fallback `glm:` — glm-5.2 is 1M, so 5.3 likely 1M too but unverified |
| `glm-5.2` | 1,048,576 (1M) | confirmed |
| `kimi-k3` | 1,048,576 (1M) | confirmed |
| `kimi-k2.7-code` | 262,144 (256K) | fallback `kimi:` — not explicitly listed |
| `kimi-k2.6` | 262,144 (256K) | confirmed |
| `deepseek-v4-pro` | 1,000,000 (1M) | confirmed |
| `deepseek-v4-flash` | 1,000,000 (1M) | confirmed |
| `mimo-v2.5-pro` | 1,048,576 (1M) | confirmed |
| `mimo-v2.5` | 1,048,576 (1M) | confirmed |
| `minimax-m3` | 1,000,000 (1M) | confirmed |
| `qwen3.8-max` | ~262,144 (256K) | fallback via qwen3-max — unverified |
| `qwen3.7-max` | ~262,144 (256K) | fallback — unverified |
| `qwen3.7-plus` | 1,048,576 (1M) | confirmed |

To pin a value per model, add `context_length` to the model entry in `custom_providers`:
```yaml
custom_providers:
  - name: "ClinePass"
    base_url: "https://api.cline.bot/api/v1"
    key_env: CLINE_API_KEY
    models:
      - id: cline-pass/glm-5.3
        name: cp/GLM-5.3
        context_length: 1000000
```

## Content Format Quirk (IMPORTANT for capability probes)

The Cline/Vercel-backed gateway rejects **structured text arrays**. Even a text-only message sent as `content: [{"type":"text","text":"hi"}]` fails on many deployments (esp. `private/*-wave-cline` and `zai/glm-*`) with:
```
messages.content.type is invalid, allowed values: ['text']
```
- **Plain text requests → use `content: "hi"` (plain string), NOT an array.**
- **Vision requests → the structured array IS required** (`content: [{"type":"text",...},{"type":"image_url","image_url":{"url":"data:image/jpeg;base64,..."}}]`), because images can't be a plain string.
- Consequence: a "baseline text request" that also uses the structured-array form will mislead you into thinking the model is broken. Always baseline text with a plain string; only use the array when actually sending an image.

## Probing Vision Support (which models accept images)

To test whether a ClinePass model supports vision, POST an image as a data URL directly to `/chat/completions` (bash, `$CLINE_API_KEY` from env):
```bash
B64=$(base64 -w0 /path/to/image.jpg)
curl -s -X POST https://api.cline.bot/api/v1/chat/completions \
  -H "Authorization: Bearer $CLINE_API_KEY" -H "Content-Type: application/json" \
  -d "{\"model\":\"cline-pass/qwen3.8-max\",\"max_tokens\":40,\
    \"messages\":[{\"role\":\"user\",\"content\":[{\"type\":\"text\",\"text\":\"Describe this image in one word.\"},\
    {\"type\":\"image_url\",\"image_url\":{\"url\":\"data:image/jpeg;base64,$B64\"}}]}]}"
```
- `OK` + content ⇒ model has vision.
- `HTTP 500` w/ `content.type is invalid` ⇒ likely the text-half of the array is the problem, not vision — retry with image-only array or plain-string baseline to disambiguate.
- `HTTP 400/404` from an OpenRouter-model resolution error ⇒ the deployment doesn't accept images / model has no vision.
- Related Hermes config: the `vision:` section (provider/model/timeout) controls the auxiliary vision model used when the active chat model has no native vision. A free OpenRouter vision model (e.g. `google/gemini-2.0-flash-exp:free`) can go 404/500; debug by calling it directly first.

## Free Models (no ClinePass needed)
- `minimax/minimax-m2.5` — free tier
- Others vary by provider

## Example Request
```bash
curl -X POST https://api.cline.bot/api/v1/chat/completions \
  -H "Authorization: Bearer $CLINE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "cline-pass/minimax-m3", "messages": [{"role": "user", "content": "hi"}]}'
```

## Documentation
- API Overview: https://docs.cline.bot/api/overview
- Models: https://docs.cline.bot/api/models
- ClinePass: https://docs.cline.bot/getting-started/clinepass

## Windows Hermes Setup
Config path: `%USERPROFILE%\.hermes\config.yaml`

```yaml
model:
  provider: custom
  base_url: "https://api.cline.bot/api/v1"
  api_key: "sk-..."
  default: "cline-pass/kimi-k3"

custom_providers:
  - name: "ClinePass"
    base_url: "https://api.cline.bot/api/v1"
    models:
      - id: "cline-pass/glm-5.3"
        name: "cp/GLM-5.3"
      - id: "cline-pass/kimi-k3"
        name: "cp/Kimi K3"
      - id: "cline-pass/minimax-m3"
        name: "cp/MiniMax M3"
      # ... add remaining models
```

After editing config.yaml: `systemctl --user restart hermes-gateway` (Linux) or restart Hermes process (Windows).
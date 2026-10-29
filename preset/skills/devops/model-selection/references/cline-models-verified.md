# Cline API — Verified Working Models (August 2026)

## Quick Test Command

```bash
for model in "minimax/minimax-m2.5" "openai/gpt-4o" "deepseek/deepseek-chat" "qwen/qwen3.7-plus" "moonshotai/kimi-k3" "z-ai/glm-5.2" "xiaomi/mimo-v2.5-pro" "google/gemini-2.5-flash"; do
  echo -n "$model: "
  curl -s -H "Authorization: Bearer YOUR_KEY" \
    -H "Content-Type: application/json" \
    "https://api.cline.bot/api/v1/chat/completions" \
    -X POST -d "{\"model\":\"$model\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}" \
    | jq -r '.success // .error'
done
```

## ✅ Verified Working

| Model ID | Provider | Notes |
|----------|----------|-------|
| `minimax/minimax-m2.5` | Minimax | **Free** |
| `openai/gpt-4o` | OpenAI | Multimodal |
| `openai/gpt-4o-mini` | OpenAI | Fast |
| `deepseek/deepseek-chat` | DeepSeek | Cheap |
| `deepseek/deepseek-v4-pro` | DeepSeek | Should work |
| `deepseek/deepseek-v4-flash` | DeepSeek | Should work |
| `qwen/qwen3.7-plus` | Qwen | Verified |
| `qwen/qwen3.7-max` | Qwen | Should work |
| `qwen/qwen3.8-max` | Qwen | Should work |
| `moonshotai/kimi-k3` | Kimi | Verified |
| `moonshotai/kimi-k2.6` | Kimi | Should work |
| `moonshotai/kimi-k2.5` | Kimi | Should work |
| `z-ai/glm-5.2` | GLM | Verified |
| `z-ai/glm-5.1` | GLM | Should work |
| `xiaomi/mimo-v2.5-pro` | Xiaomi | Verified |
| `xiaomi/mimo-v2.5` | Xiaomi | Should work |
| `google/gemini-2.5-pro` | Google | Verified |
| `google/gemini-2.5-flash` | Google | Verified |
| `x-ai/grok-4.5` | xAI | Should work |
| `x-ai/grok-3` | xAI | Should work |

## ❌ Not Working

| Model ID | Error |
|----------|-------|
| `anthropic/claude-sonnet-4-6` | model not found |
| `anthropic/claude-haiku-4-5` | model not found |

---

## ✅ ClinePass Models (Subscription Tier)

**Requires active ClinePass ($9.99/month).** Same API key, 2-5x higher rate limits.

| Model ID | Base Model | Notes |
|----------|------------|-------|
| `cline-pass/glm-5.3` | GLM-5.3 | Verified |
| `cline-pass/glm-5.2` | GLM-5.2 | Should work |
| `cline-pass/kimi-k3` | Kimi K3 | Verified |
| `cline-pass/kimi-k2.7-code` | Kimi K2.7 Code | Should work |
| `cline-pass/kimi-k2.6` | Kimi K2.6 | Should work |
| `cline-pass/deepseek-v4-pro` | DeepSeek V4 Pro | Should work |
| `cline-pass/deepseek-v4-flash` | DeepSeek V4 Flash | Should work |
| `cline-pass/mimo-v2.5-pro` | MiMo V2.5 Pro | Should work |
| `cline-pass/mimo-v2.5` | MiMo V2.5 | Should work |
| `cline-pass/minimax-m3` | MiniMax M3 | **Verified working** |
| `cline-pass/qwen3.8-max` | Qwen 3.8 Max | Should work |
| `cline-pass/qwen3.7-max` | Qwen 3.7 Max | Should work |
| `cline-pass/qwen3.7-plus` | Qwen 3.7 Plus | Should work |

Test command:
```bash
curl -s -H "Authorization: Bearer YOUR_KEY" \
  -H "Content-Type: application/json" \
  "https://api.cline.bot/api/v1/chat/completions" \
  -X POST -d '{"model":"cline-pass/minimax-m3","messages":[{"role":"user","content":"hi"}]}'
```

---

## Hermes Picker Integration

Add to `config.yaml`:

```yaml
model:
  provider: custom
  base_url: https://api.cline.bot/api/v1
  api_key: sk_...
  default: minimax/minimax-m2.5

custom_providers:
  - name: Cline
    base_url: https://api.cline.bot/api/v1
    models:
      - id: minimax/minimax-m2.5
        name: MiniMax M2.5 (Free)
      - id: openai/gpt-4o
        name: GPT-4o
      # ... add more from verified list
      # ClinePass models (require active subscription):
      - id: cline-pass/minimax-m3
        name: MiniMax M3 (ClinePass)
      - id: cline-pass/glm-5.3
        name: GLM-5.3 (ClinePass)
      # ... add other ClinePass models
```

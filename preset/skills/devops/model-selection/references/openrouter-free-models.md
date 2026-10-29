# OpenRouter Free Models — Live-Verified

**Rule: a `:free` badge in the catalog is NOT proof a model works.** Live-test every free model with a real `/v1/chat/completions` request before recommending it — a large share of the free catalog returns 403/404/provider errors despite being listed. A last-verified date in this file does not exempt you: the free roster churns weekly. Re-run the test procedure below before building any cascade on free models.

**Last full live test: 2026-10-22** (65 free-vision candidates probed with a real image; 11 verified working — list in 'Working free vision' table below).

---

## How to Count Free Models Correctly

- `/api/v1/models` returns ONLY chat-completions models. Zero-token-price filter (`prompt=0 AND completion=0`) gave 25 free chat models (23 text + 2 music Lyria).
- The website `openrouter.ai/models?max_price=0` shows ALL modalities: embedding, TTS, image, video, reranker. Most are NOT free (Seedream $0.035/image, Qwen3 Reranker $0.20/M) — the filter matches only input price. Never report website counts as free chat models.
- Free embedding models can appear on the site before the API serves them: `lfm-2.5-embedding-350m` showed on site but returned 404 `No endpoints found` via `/v1/embeddings`. Always probe the embeddings endpoint directly before relying on it.
- TTS models (e.g. deepgram/flux-tts) reject `/v1/chat/completions` — they live on `/v1/audio`.

## Free-Tier Limits (per key)

Depends on **credits purchased all-time**, not current balance:
- Never paid (`is_free_tier: true`): 50 free-model requests/day, 20/min
- Paid >= ~$10 lifetime: 1000 free-model requests/day, 20/min. Spending the balance down does NOT revoke this.
- Check: `GET /api/v1/key` -> `is_free_tier`, `usage` (lifetime $).
- Negative balance can throttle free models too. For weekly-cron workloads (fact extraction etc.) limits are irrelevant at either tier.

## Verified Working Free Chat Models (live test, RU + JSON output)

| Model ID | Context | Time | Notes |
|----------|---------|------|-------|
| `deepseek/deepseek-v4-flash-0731:free` | 1M | 8.7s | Same model as ClinePass; best Russian; JSON OK |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | 1M | 2.3s | Flagship MoE, RU ok |
| `nvidia/nemotron-3-super-120b-a12b:free` | 262K | 7.1s | RU ok |
| `google/gemma-4-26b-a4b-it:free` | 262K | 1.9s | Fast, RU ok; upstream 429 bursts happen — retry, or use the same model via a free Google AI Studio key |
| `nex-agi/nex-n2.5-pro:free` | 262K | 27.7s | Slow |
| `cohere/north-mini-code:free` | 256K | 1.5s | Translates RU->EN in answers |
| `openrouter/free` | 200K | 2.0s | Router; self-selects a working free model — good universal fallback |

## Verified NOT Working (live test — listed as free but broken)

| Model ID | Failure |
|----------|---------|
| `qwen/qwen3.8-27b:free` | Provider returned error |
| `google/gemma-4-31b-it:free` | Provider returned error |
| `z-ai/glm-5.2:free` | Provider returned error |
| `poolside/laguna-s-2.1:free` | HTTP 429 (rate-limited to death) |
| `poolside/laguna-xs-2.1:free` | Empty response |
| `thinkingmachines/inkling:free` | HTTP 403 |
| `thinkingmachines/inkling-small:free` | 'only available on agentic harnesses' |
| `minimax/minimax-m3:free` | HTTP 404 |
| `nvidia/nemotron-3.5-lightning:free` | Works but streams reasoning-as-text, unusable for JSON |
| `nvidia/nemotron-3-nano-omni-30b...:free` | Empty response |
| `liquid/lfm-2.5-2.6b:free` | 2.6B — too weak for extraction tasks |
| `inclusionai/ling-3.0-flash-vl:free` | 404 "unavailable for free" — free tier retired after first verification; roster churns |
| `nex-agi/nex-n2.5-mini:free` (+ :free-high/medium/none) | 404 "unavailable for free" — free tier retired; OmniRoute effort variants resolve to the base upstream slug |
| `dots-studio/dots-3-note-preview:free` | 404 "unavailable for free" — free tier retired |
| `oc/mimo-v2.5-free` (OmniRoute/OpenCode) | 403 "OpenCode's free tier can only be used from within OpenCode" — gated veneer, unusable from Hermes |

## Is THIS Model Free/Reachable? — single-model probe

`GET /api/v1/models/<vendor>/<model>:free/endpoints` answers the availability
question for one id without spending a completion: it proves the `:free` variant
exists, names the serving provider (`nvidia/nemotron-3.5-super-vl:free` is served
by NVIDIA itself, not a third party), and gives the real `max_completion_tokens` /
`max_prompt_tokens` plus 5m/30m/1d uptime.

**Card modalities ≠ routed modalities.** `nvidia/nemotron-3.5-super-vl:free`
lists `text+image+video->text` in the card, yet an image request returns
`404 No endpoints found that support image URLs` (routing funnel: "Filter by
Image Support") — the free endpoint is text-only in practice. Probe the modality
you need before promising it; the same model served directly on NIM does accept
images.

## Live-Test Procedure (use verbatim)

```python
# For each candidate — real request, not a models-list check:
body = {'model': mid, 'messages':[{'role':'user','content':'Extract fact, return JSON: "...". Format: [{"fact": "...", "category": "general"}]'}], 'max_tokens': 300, 'temperature': 0.2}
# POST https://openrouter.ai/api/v1/chat/completions with Bearer key
# Success = HTTP 200 AND regex '\[.*fact.*\]' over content (re.S). Sleep ~1.5s between models.
```

Test criteria that matter for Hermes memory/fact-extraction: JSON compliance, Russian quality, latency (<15s), no reasoning-as-text pollution.

## Recommended Cascade for Fact Extraction

`deepseek-v4-flash-0731:free` -> `nemotron-3-ultra:free` -> `openrouter/free` -> paid DeepSeek ($0.14/$0.28 — pennies) -> local fallback (Qwen 9B GGUF). Free MoE models of this class carry 100+GB total weights — none duplicate locally on an 8GB GPU; local fallback means a real quality step-down to a 9B dense, acceptable for extraction, not for generation.

## Free Vision Models — verify with a real image, then verify the ANSWER

**`capabilities.vision: true` (or "VL" in the name) is NOT proof of vision.** Live-test with a real `image_url` request and check the answer against the known image content — a model can return a fluent, confident description that is pure hallucination (a 90B vision model described "phases of the Moon" for a Google-logo test image).

**Test recipe:** one small known image (~13KB PNG with legible text + several colors), ask "что изображено? назови текст и цвета", send BOTH variants — hosted URL and base64 data URI (providers differ on which they accept) — `max_tokens` ≥200, **timeout ≥120s**. Score OK only if text AND colors match reality.

### Working free vision (image-verified, 2026-10-22)

Live-probed with a 400×200 PNG containing legible text "HELLO VISION TEST 12345" + a red square; scored OK only when the model described BOTH the text and the color correctly. 65 free candidates tested, 11 passed.

| Model | Endpoint | Latency | Notes |
|-------|----------|---------|-------|
| `meta/llama-3.2-11b-vision-instruct` | NVIDIA NIM (free by key) | ~44s | Correct |
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` | NVIDIA NIM | ~12s | Correct |
| `gemma4:31b` | Ollama Cloud (free) | ~1s | Best free; reads text+colors |
| `openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | OmniRoute/OpenRouter | ~5s | Correct |
| `openrouter/thinkingmachines/inkling-small:free` | OmniRoute/OpenRouter | ~1.5s | Correct (earlier "agentic harnesses" gate was stale) |
| `openrouter/thinkingmachines/inkling:free` | OmniRoute/OpenRouter | ~6s | Correct |
| `th/deepseek-v4-flash:free` | OmniRoute/TokenHarbor | ~4s | Correct |
| `th/deepseek-v4.1-flash:free` | OmniRoute/TokenHarbor | ~4s | Correct |
| `th/mimo-v2.5:free` | OmniRoute/TokenHarbor | ~5s | Correct |
| `deepseek-v4.1-flash:free` | TokenHarbor (direct) | ~1.5s | Correct |
| `mimo-v2.5:free` | TokenHarbor (direct) | ~6s | Correct |

### Free vision that FAILED the image probe (do not recommend)

- `th/mimo-v2.6-flash:free` — returned empty content (unusable).
- `openrouter/google/gemma-4-26b-a4b-it:free`, `gemma-4-31b-it:free` — 429 cooldown (retry later; Google AI Studio twin works).
- `openrouter/inclusionai/ling-3.0-flash-vl:free`, `nex-agi/nex-n2.5-mini:free`, `dots-studio/dots-3-note-preview:free`, `qwen/qwen3.8-27b:free` — 404 "unavailable for free".
- `nvidia/z-ai/glm-5.3-flash` (NIM) — timeout (60s).
- `meta/llama-3.2-90b-vision-instruct` (NIM) — hallucinates content; never for factual vision.
- `oc/mimo-v2.5-free`, `oc/muse-spark-*-free`, `ocgo/*-free`, `opencode-go/*-free` — 403/410/400 (gated or retired).
- `openrouter/openrouter/free`, `openrouter/nvidia/nemotron-3.5-content-safety:free` — empty/None response.
- Google AI Studio `gemini-1.5-flash/pro` — 404 (retired).

### Google AI Studio specifics

### Google AI Studio specifics

- `custom_providers` model entries go stale: `gemini-1.5-*` 404 (retired from the API). Enumerate the live roster first: `GET https://generativelanguage.googleapis.com/v1beta/models` with header `x-goog-api-key`, filter for `generateContent` in `supportedGenerationMethods`.
- For vision, use native `POST /v1beta/models/<model>:generateContent` with `contents[].parts: [{text}, {inline_data: {mime_type, data(base64)}}]` — the most reliable image path.

## NVIDIA NIM Direct-Test Rules (integrate.api.nvidia.com, free by key)

- **Strip the veneer prefix before calling NIM directly.** OmniRoute lists NIM models as `nvidia/<org>/<model>`; the real NIM ID is `<org>/<model>` (`meta/llama-3.2-11b-vision-instruct`, not `nvidia/meta/...`). The prefixed ID returns mass 404 "Function '<uuid>': Not found for account" — a whole-provider 404 wall means check ID format FIRST, not that the provider died.
- **Timeouts ≥90–200s.** NIM models legitimately take 60–120s+ (a 90B vision model: 57s image, 116s text). Short 15–30s timeouts once faked an "all models dead" verdict.
- `/v1/models` lists ~81 models but only ~a dozen answer at `/chat/completions`; most legacy catalog entries (old Gemma/Granite/Mistral/Phi-3) 404 "Not found for account" at request time. Live-test, never trust the list.
- Reasoning models (`z-ai/glm-5.3*`, `openai/gpt-oss-20b`, `nvidia/nemotron-3-super`) return `content: null` with the answer in `reasoning_content` — read both fields before scoring a model "empty".
- **Thinking-on-by-default eats the whole probe budget.** `nvidia/nemotron-3.5-super-vl-120b-a12b` and `minimaxai/minimax-m3.1-flash` answer HTTP 200 with `content: null` and `completion_tokens_details.reasoning_tokens` == `max_tokens` when the budget is small — the route is fine, the budget vanished into reasoning. When probing a new model pass `chat_template_kwargs: {enable_thinking: false}` (NIM) or `reasoning: {enabled: false}` (OpenRouter), or budget ≥300 tokens.
- **`/v1/models` is a superset of what Hermes will show.** The NIM catalog can list a model that is absent from `custom_providers[].models` (`discover_models: false`) — it still switches when called by its real id, but it is invisible in `/model`. Enumerate the catalog before telling the user a model is unavailable in Hermes.
- **Image input format: hosted https URL only.** NIM accepts an `https` `image_url` (verified: described a logo correctly) but a `data:image/png;base64,…` payload returns `415 Unsupported Media Type`. A URL whose host refuses the fetcher surfaces as `403 Forbidden` from NIM — that is the image host, not the model.
- Through OmniRoute, image payloads to NVIDIA backends arrive broken (unparseable empty bodies) even though text works — test NVIDIA vision directly against `integrate.api.nvidia.com`.
- Image-generation (`black-forest-labs/flux*`), embed/rerank/ASR/TTS and detector models reject `/chat/completions` by design — filter them from chat rosters by keyword (flux, embed, rerank, whisper, parakeet, fastpitch, tacotron, nvclip, parse, guard, reward).

## Hermes Picker Caveat

OpenRouter is a NATIVE Hermes provider (catalog from models.dev, cached in `~/.hermes/cache/model_catalog.json`) — it does NOT appear in `custom_providers` in config.yaml, and its picker list is a curated subset (59 of 447 models), which can include broken free models and omit working ones. Don't conclude 'provider missing' from the absence of an openrouter block in config.yaml; don't treat the picker list as the full catalog.

# Third-Party Aggregators: TokenHarbor & Zhipu GLM — Verified Findings

Session of 2026-09-12 (user's TokenHarbor provider, model glm-5.3-flash).
TokenHarbor (tokenharbor.ai) is NOT on OpenRouter — it's a separate aggregator
("One API for the world's leading AI models", PTE LTD, subscription "Pass" tiers:
Free / Agent Pass / Office Pass / Frontier Pass). Model IDs mirror OpenRouter-style
names but without org prefixes (e.g. `glm-5.3-flash`, `deepseek-v4-flash:free`).

## GLM-5.3-Flash reasoning levels — what's actually real

- **Native Zhipu GLM API has NO effort dial** — only thinking on/off. Any
  `reasoning_effort` is an OpenAI-compat shim layered by the aggregator.
- **OpenRouter endpoints for `z-ai/glm-5.3-flash-20260826`**: all 27 endpoint
  providers declare `reasoning_effort` in `supported_parameters`. Standard
  OpenAI-compat ladder applies: **`low / medium / high`** (default medium).
  Possibly `minimal`; NOT `xhigh` / `max` — those belong to other families
  (`xhigh` = Anthropic Opus 4.7+; `max`/`ultra` = OpenAI o-series / Hermes
  internal ladder).
- **TokenHarbor docs (all 26 pages crawled 2026-09-12): zero mention of
  `reasoning_effort`** — they don't document the parameter at all. Without a
  live key, what TokenHarbor accepts for GLM is unverified; assume low/medium/high.

## TokenHarbor plan-gating gotchas (from session request dumps)

- `glm-5.3` is **Frontier Pass only** → live 402
  `model_not_in_plan: "This model isn't included in your current subscription"`.
- `glm-5.3-flash` is included at **Agent Pass** tier (docs "Models included
  with each Pass": Agent Pass = GLM-5.3 Flash, GPT-5.6 Luna, MiMo V2.5 Pro,
  Qwen3.8 Flash). Free tier = DeepSeek V4 Flash, MiMo V2.5, `:free` IDs.
- Free models keep `:free` model IDs; Pass usage applies to paid routes.
- After Pass allowance runs out → pay-as-you-go from wallet balance
  (5%/10%/15% off by tier), NOT a second balance.

## API-key hygiene lesson (durable)

- A stored key can be **revoked server-side** without any local change. Symptom:
  every call (incl. `/v1/models`, which needs no separate permission) returns
  `401 invalid_api_key: "Invalid or revoked API key. Rotate your key at
  <provider>/dashboard"`.
- Before diagnosing deeper, grep config.yaml for the provider's `api_key` and
  curl one cheap endpoint. If 401-with-rotate-message → the answer is "key
  rotated, need new key", NOT a model/config problem. Don't burn turns on
  UA spoofing or alt auth headers — 401 was consistent.
- Also worth checking when provider calls fail: `~/.hermes/sessions/request_dump_*.json`
  records the exact request body + provider error (found the 402
  `model_not_in_plan` there).

## How Hermes sends reasoning to custom providers (source-verified)

`agent/transports/chat_completions.py`:
- Generic custom provider path: `supports_reasoning` →
  `extra_body.reasoning = {"enabled": true, "effort": <user effort>}`.
- Special-cased per-host in `agent/chat_completion_helpers.py`:
  - Kimi hosts (api.kimi.com / moonshot.*): top-level `reasoning_effort`,
    clamped to {low, medium, high}, default medium; + `extra_body.thinking`.
  - Tencent TokenHub (tokenhub.tencentmaas.com — NOT tokenharbor.ai, different
    product): top-level `reasoning_effort`, clamped to {low, medium, high},
    **default high**.
  - LM Studio: `reasoning_effort` from its published allowed_options, clamp
    max/ultra → xhigh.
- Hermes' generic effort ladder (Gemini path): {minimal, low, medium, high,
  xhigh, max, ultra}, unknown → medium. The ladder is Hermes-side; the model
  family determines what the upstream actually honors.

## Verification playbook (worked this session)

1. Check aggregator presence: `curl -s https://openrouter.ai/api/v1/models |
   python3 -c ...` grep for the provider name — confirms it's separate.
2. Model capability across endpoints:
   `curl -s https://openrouter.ai/api/v1/models/<id>/endpoints` — lists every
   endpoint provider + its `supported_parameters` (reasoning_effort etc.).
3. Live provider key test: read key from config.yaml, curl `/v1/models` (cheap),
   then per-level `/chat/completions` with `reasoning_effort` in
   {none,minimal,low,medium,high,xhigh,max}.
4. Docs sweep: download `/<docs-page>`, strip script/style/tags, regex for
   `reasoning|effort|xhigh`. TokenHarbor docs live at tokenharbor.ai/docs
   (JS-rendered but raw HTML contains the text in RSC payload — grep the raw
   file, don't rely on rendered DOM).

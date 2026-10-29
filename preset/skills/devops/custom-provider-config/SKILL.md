---
name: custom-provider-config
description: "Add custom OpenAI-compatible providers to Hermes picker."
version: 1.2.0
tags: [hermes, custom-provider, model-picker, telegram, config.yaml]
---

# Custom Provider Configuration for Hermes Model Picker

## Overview

Hermes supports custom OpenAI-compatible endpoints via `model.provider: custom` in config.yaml. To expose models in the **Telegram/Discord `/model` picker**, you must add a `custom_providers` section to config.yaml with explicit model names and display labels.

## Key Insight

The `model.provider: custom` + `model.base_url` + `model.api_key` only configures the **active model** for the agent. It does **NOT** populate the Telegram/Discord model picker. For the picker, you need `custom_providers` list with `models` array containing `{id, name}` objects.

## Standing rule: never remove or "dedupe" a `custom_providers` entry

user's instruction, restated after repeated corrections: **touch nothing in the
providers list of Hermes — a duplicate entry stays.** Two entries for the same
vendor (e.g. an inline-API-key NVIDIA block plus a `key_env`/managed one) are
intentional, not a bug to clean up. Apparent duplication is frequently the only
thing keeping one route alive when the other's credential path is broken.

This binds the whole class of provider work: do not delete, merge, rename,
reorder, or rebuild a `custom_providers` entry while investigating an unrelated
provider or model problem, and never rewrite the whole list to add one block —
splice text after an anchor line instead (see the per-model `context_length`
recipe below). If you believe an entry is genuinely wrong, say so and let user
decide; do not act.

The rule covers **route duplication, not only credential duplication**: when a
router (OmniRoute) also serves a provider directly, both representations stay —
the mirrored ids live in the router's picker row AND the direct provider keeps
its own row, and the same model appearing in both is by design, not a defect to
tidy up. Standing user ruling (restated after it was flagged as a "duplication"
question): models reachable through the router belong to the router's row,
direct providers stay direct, and the overlap between them is wanted. So do NOT
add a drop-rule / keep-list filter to the OmniRoute sync script for a live
prefix just to remove the duplicate, and do not offer to clean it up: raise it
as a question if you must, never act on it without a green light.

## Adding a NEW provider entry: `hermes config set` cannot append

`hermes config set custom_providers.<N>.<field> <value>` walks the dotted path
through the loaded structure, so a **new** index raises
`IndexError: list index out of range`. It can only mutate entries that already
exist. Appending a provider therefore means splicing text into config.yaml
yourself, before the next top-level (zero-indent) key that follows the list:

```bash
# find the end of the custom_providers list: first unindented, non-comment line after `custom_providers:`
python3 - <<'EOF'
lines = open('~/.hermes/config.yaml').read().split('\n')
start = next(i for i, l in enumerate(lines) if l.startswith('custom_providers:'))
end = next(j for j in range(start + 1, len(lines))
           if lines[j] and not lines[j][0].isspace() and not lines[j].startswith('#'))
print(lines[end - 1], '->', lines[end])
EOF
```

Then splice the block in at that index and verify with
`hermes config get custom_providers` — it must parse and the count must grow.

## `context_length` placement is load-bearing

The field only binds to a model if it sits **after** that model's `name:` line at
8-space indent, inside the model mapping:

```yaml
  - name: Example Provider
    base_url: https://example.test/v1
    key_env: EXAMPLE_API_KEY
    models:
      - id: some-model
        name: pfx/some-model
        context_length: 1048576
```

Putting `context_length` *before* the `- id:` line (at list-item indent) lands it
on the **previous** model or nowhere, and Hermes silently ignores it — YAML
parses, the count in `hermes config get` just doesn't change. Symptom to check
when a context override "didn't take": re-read the raw YAML around the entry and
compare the reported value per model id, not the total. Duplicate
`context_length` lines under one model also parse (last wins) while Hermes
reports none — remove dupes when you see them.

Bulk-writing via `hermes config set custom_providers.<N>.models.<i>.context_length`
works for **existing** models and takes ~15s per call, so for >5 models write the
YAML directly instead of looping.

## Provider slug for `model.provider`

`custom:<slug>` is derived by `custom_provider_slug()` in
`hermes_cli/providers.py`: lowercase the display name and replace spaces with
hyphens. Display name `OpenCode Go Direct` ⇒ `custom:opencode-go-direct`. For
entries written as keyed `providers:` entries the config key wins over the
display name.

## Proving a new provider actually routes

Do not trust "the config parses" as adoption. Send a real oneshot and read the
billing route it recorded:

```bash
hermes -z 'Reply exactly: DIRECT-DEFAULT-OK'
python3 - <<'EOF'
import sqlite3
con = sqlite3.connect('file:~/.hermes/state.db?mode=ro', uri=True)
print(list(con.execute(
    "SELECT model, billing_provider, billing_base_url FROM session_model_usage "
    "ORDER BY rowid DESC LIMIT 3")))
EOF
```

`billing_base_url` must equal the provider's `base_url` — that is the proof the
request bypassed the gateway/router you were trying to remove from the path.

## Configuration Pattern

```yaml
model:
  provider: custom
  base_url: "https://api.example.com/v1"
  api_key: "sk-..."
  default: "provider/model-name"

custom_providers:
  - name: "Display Name"
    base_url: "https://api.example.com/v1"
    models:
      - id: "provider/model-name"
        name: "Display Label in Picker"
      - id: "provider/other-model"
        name: "Other Label"
```

## Critical Details

1. **`id`** — must match the exact model ID the API expects (e.g., `cline-pass/glm-5.3`, `anthropic/claude-sonnet-4-6`)
2. **`name`** — shown in Telegram picker; prefix with `cp/` or similar to distinguish tiers
3. **`base_url`** — must match the API endpoint exactly
4. **Grouping** — Hermes groups custom_providers by `(base_url, credentials, api_mode, display_prefix)`. Same endpoint = single picker row.
5. **Gateway restart required** — Changes to `custom_providers` only take effect after `systemctl --user restart hermes-gateway`
6. **Probe the endpoint before adding** — `curl http://<host>:<port>/v1/models` plus a TCP check (`timeout 5 bash -c 'echo > /dev/tcp/<host>/<port>'`) tells you the model IDs to list. If the box is offline, add the entry anyway with `discover_models: true` and no `models:` list — the picker row appears immediately (custom endpoints are kept even when empty) and models auto-populate on the first successful probe. An unreachable endpoint is not a reason to refuse the request.

## Mistral AI (Free Tier via API Key)
## Google AI Studio (Gemini via Generative Language API)

Google AI Studio provides access to Gemini models through the Generative Language API.

- **Base URL:** `https://generativelanguage.googleapis.com/v1beta`
- **API key:** Obtained from [Google AI Studio](https://aistudio.google.com/apikey) (format: `AQ.Ab8...`)
- **Authentication:** API key passed as query parameter `?key=` or `Authorization: Bearer` header — Hermes uses inline `api_key` in `custom_providers` (not `key_env`)
- **Models available:** `googleai/gemini-1.5-flash`, `googleai/gemini-1.5-pro` (context: 1M tokens)

### Configuration

```yaml
custom_providers:
  - name: "Google AI Studio"
    base_url: "https://generativelanguage.googleapis.com/v1beta"
    api_key: "ВАШ_GOOGLE_AI_STUDIO_КЛЮЧ"
    models:
      - id: "googleai/gemini-1.5-flash"
        name: "cp/gemini-1.5-flash"
        context_length: 1048576
      - id: "googleai/gemini-1.5-pro"
        name: "cp/gemini-1.5-pro"
        context_length: 1048576
```

**Key difference from ClinePass/Mistral:** Uses inline `api_key` instead of `key_env` because the key format (`AQ.Ab8...`) is not a standard Bearer token and is typically passed as a query parameter. Hermes handles this when `api_key` is present in the provider entry.

---

## OpenCode Go / Zen — use the NATIVE provider, not custom_providers (2026-09-30)

Hermes ships built-in `opencode-go` and `opencode-zen` providers
(`CANONICAL_PROVIDERS` in `hermes_cli/models_catalog_static.py`), so NO
`custom_providers` block is needed — add the credential with the official CLI:

```bash
hermes auth add opencode-go --type api-key --api-key oc_sk_... --label 'OpenCode Go sub'
hermes auth status opencode-go   # → logged in
hermes -z 'Say OK' -m glm-5.2 --provider opencode-go   # real-call check
```

- Picker row **OpenCode Go** appears with the live-first catalog (42 models
  as of 2026-09-30); no gateway restart needed for the row, restart only for
  the active model side.
- The native path auto-sends `x-opencode-session` (Go rejects requests without
  it, `400 MissingSessionID`) and re-derives the wire protocol per model
  (gpt-* → Responses, qwen/minimax/claude → Anthropic Messages), which a
  plain OpenAI-compatible custom entry does NOT do.
- Do not duplicate this as a custom_providers entry pointing at
  `https://opencode.ai/zen/go/v1`: chat/completions-only custom wiring 401s on
  gpt-* and 400s without a session header.

## Mistral AI (Free Tier)
Mistral provides a standard OpenAI-compatible API with free-tier access to lightweight models.

- **Base URL:** `https://api.mistral.ai/v1`
- **API key env var:** `MISTRAL_API_KEY` (create at [console.mistral.ai](https://console.mistral.ai))
- **Has `/v1/models` endpoint** — unlike ClinePass, you can discover available models and their capabilities directly.
- **Tested working on free tier (2026-08-21):** `ministral-3b-latest`, `ministral-8b-latest`, `ministral-14b-latest`, `codestral-latest`, `mistral-small-latest`, `labs-leanstral-1-5`.

### Configuration
```yaml
custom_providers:
  - name: "Mistral"
    base_url: "https://api.mistral.ai/v1"
    key_env: MISTRAL_API_KEY
    models:
      - id: "ministral-3b-latest"
        name: "free/ministral-3b"
      - id: "ministral-8b-latest"
        name: "free/ministral-8b"
      - id: "ministral-14b-latest"
        name: "free/ministral-14b"
      - id: "codestral-latest"
        name: "free/codestral"
      - id: "mistral-small-latest"
        name: "free/mistral-small"
      - id: "mistral-medium-latest"
        name: "mistral-medium"  # Paid
      - id: "mistral-large-latest"
        name: "mistral-large"   # Paid
      - id: "labs-leanstral-1-5"
        name: "free/labs-leanstral"
```

**Naming convention used:** Prefix `free/` for models confirmed working on the free tier. Models without prefix (medium, large) likely require paid credits.

### Verification
Test the key and a model in one command:

```bash
curl -s -H "Authorization: Bearer $MISTRAL_API_KEY" \
  -H "Content-Type: application/json" \
  https://api.mistral.ai/v1/chat/completions \
  -X POST -d '{"model":"ministral-3b-latest","messages":[{"role":"user","content":"hi"}],"max_tokens":10}'
```

List all available models:

```bash
curl -s -H "Authorization: Bearer $MISTRAL_API_KEY" \
  https://api.mistral.ai/v1/models | python3 -m json.tool
```

### Free Tier Limits
- **10 requests per minute (RPM)**.
- **1000 tokens per minute (TPM)** (sum of input + output tokens).
- **No hard total token limit**, but suspicious activity may lead to account suspension.
- **Large models (medium/large) require paid credits**.
- **Has `/v1/models` endpoint** — unlike ClinePass, you can discover available models and their capabilities directly.
- **Tested working on free tier (2026-08-21):** `ministral-3b-latest`, `ministral-8b-latest`, `ministral-14b-latest`, `codestral-latest`, `mistral-small-latest`, `labs-leanstral-1-5`.

### Configuration

```yaml
custom_providers:
  - name: "Mistral"
    base_url: "https://api.mistral.ai/v1"
    key_env: MISTRAL_API_KEY
    models:
      - id: "ministral-3b-latest"
        name: "free/ministral-3b"
      - id: "ministral-8b-latest"
        name: "free/ministral-8b"
      - id: "ministral-14b-latest"
        name: "free/ministral-14b"
      - id: "codestral-latest"
        name: "free/codestral"
      - id: "mistral-small-latest"
        name: "free/mistral-small"
      - id: "mistral-medium-latest"
        name: "mistral-medium"
      - id: "mistral-large-latest"
        name: "mistral-large"
      - id: "labs-leanstral-1-5"
        name: "free/labs-leanstral"
```

**Naming convention used:** Prefix `free/` for models confirmed working on the free tier. Models without prefix (medium, large) likely require paid credits.

### Verification

Test the key and a model in one command:

```bash
curl -s -H "Authorization: Bearer $MISTRAL_API_KEY" \
  -H "Content-Type: application/json" \
  https://api.mistral.ai/v1/chat/completions \
  -X POST -d '{"model":"ministral-3b-latest","messages":[{"role":"user","content":"hi"}],"max_tokens":10}'
```

List all available models:

```bash
curl -s -H "Authorization: Bearer $MISTRAL_API_KEY" \
  https://api.mistral.ai/v1/models | python3 -m json.tool
```

### Pitfalls

- **No free tier for large models** — `mistral-large-latest`, `mistral-medium-latest` may return 402/429 on a free-tier key. Test before assuming availability.
- **Standard OpenAI API format** — no data wrapping (unlike ClinePass). Non-streaming requests work natively without a proxy.
- **Gateway restart** required: `systemctl --user restart hermes-gateway`
- **`key_env` is mandatory** in the custom_providers entry — gateway reads credentials from there, not from `model.api_key`.

## Cline / ClinePass Specifics

- **Base URL:** `https://api.cline.bot/api/v1`
- ⚠️ **Cline has NO `/v1/models` endpoint** (OpenAI-style model listing returns 404). However, Cline IDE/CLI uses a **live endpoint** for model discovery. See "Live Model Discovery" section below.
- **Free models are NOT available through the API** (only through Cline IDE Extension and CLI).
- ⚠️ **Non-streaming responses are wrapped in `{"data": {"choices": [...]}}`.** This breaks Hermes auxiliary tasks (vision, compression, title) that send non-streaming requests — the main chat works because it streams. Fix via the local unwrap proxy. Full diagnosis + fix: `references/multimodal-vision-custom-provider.md`; ready proxy: `scripts/clinepass-unwrap-proxy.py`.
- ⚠️ **Cold-start non-streaming (cron / aux tasks) — model-dependent.** Many ClinePass models (DeepSeek V4 Flash, GLM-5.3) routinely hang for 600s+ on non-streaming requests from a cold start — the underlying upstream provider takes minutes to respond. **MiniMax M3** is the exception: returns in 3-10s on cold non-streaming. When pinning a ClinePass model for a cron job that sends non-streaming requests (e.g. weekly LLM-agent review), prefer `cline-pass/minimax-m3` unless the task absolutely needs DeepSeek.
- **Regular models:** `anthropic/claude-sonnet-4-6`, `openai/gpt-4o`, `minimax/minimax-m2.5`, etc.

### ⚠️ ClinePass Model Name Format: Provider/Model Required

**Critical finding (2026-08-30):** The ClinePass API (`api.cline.bot`) **expects `provider/model` format** (e.g., `deepseek/deepseek-v4-flash`), NOT the `cline-pass/model` format shown in Cline's UI and used in older configurations.

| Format | Result |
|--------|--------|
| `deepseek/deepseek-v4-flash` | ✅ 403 (in subscription, needs Cline app auth) |
| `cline-pass/deepseek-v4-flash` | ❌ 500 "empty response content" |
| `deepseek-v4-flash` | ❌ 400 "invalid model format" |

**Action:** Update `custom_providers[].models[].id` values from `cline-pass/...` to `provider/model` format (e.g., `deepseek/deepseek-v4-flash`, `minimax/minimax-m3`, `glm/glm-5.2`, `kimi/kimi-k3`, `mimo/mimo-v2.5`, `qwen/qwen3.7-plus`).

### ⚠️ Unwrap Proxy: Model Name Mangling (3-segment names)

The **running** unwrap proxy (`~/.hermes/hermes-agent/scripts/clinepass_unwrap_proxy.py`) has model rewriting logic that corrupts 3-segment model names.

**Bug:** When Hermes sends a model name with 3+ `/`-separated segments (e.g. `cp/cline-pass/deepseek-v4-flash`), the split logic:
```python
parts = mn.split("/", 1)       # ["cp", "cline-pass/deepseek-v4-flash"]
payload["model"] = f"cline-pass/{parts[1]}"  # → "cline-pass/cline-pass/deepseek-v4-flash"
```
Result: **double prefix** → API rejects with `400: "invalid model format"`.

**Fix:** Use only 2-segment names (`cline-pass/deepseek-v4-flash`, not `cp/cline-pass/...`) — the proxy skips rewriting when model starts with `cline-pass/`.

**Better fix (2026-08-30):** Remove the model rewriting logic entirely from the proxy. The clean version in `scripts/clinepass-unwrap-proxy.py` does NOT rewrite model names — it only unwraps the `{"data": {...}}` envelope. Hermes should send the correct `provider/model` format directly.

### ⚠️ Unwrap Proxy: TLS Handshake Timeouts

Python 3.11 urllib in the running proxy can fail with TLS handshake timeouts while `curl` to the same endpoint works fine:

```
urllib.error.URLError: <urlopen error _ssl.c:999: The handshake operation timed out>
```

**Likely cause:** Portable Python runtime has a dated CA bundle or missing intermediate certs. Restarting the proxy often resolves.
**Workaround:** `systemctl --user restart clinepass-unwrap-proxy` then verify with `curl http://127.0.0.1:8765/v1/chat/completions`.

### ⚠️ Proxy Script Version Mismatch

Two divergent versions exist:

| Feature | Running systemd version (`.../scripts/clinepass_unwrap_proxy.py`) | Skill dir version (`scripts/clinepass-unwrap-proxy.py`) |
|---------|-------------------------------------------------------------------|----------------------------------------------------------|
| Model rewriting | Yes — `split("/",1)` → can mangle 3-segment names | **No** |
| Auth injection | Yes — injects CLINE_API_KEY if request has no Bearer | **No** |
| Path normalization | Yes — strips `/v1` from incoming path | **No** |
| TARGET | `https://api.cline.bot/api/v1` | `https://api.cline.bot/api` |

The skill description on this page references features of the **running** proxy. If you deploy the skill's clean script, ensure Hermes sends a valid Authorization header and uses base_url with `/v1`.

- **ClinePass models (13, tested 2026-08-19):**
  - `cline-pass/glm-5.3`, `cline-pass/glm-5.2`
  - `cline-pass/kimi-k3`, `cline-pass/kimi-k2.7-code`, `cline-pass/kimi-k2.6`
  - `cline-pass/deepseek-v4-pro`, `cline-pass/deepseek-v4-flash`
  - `cline-pass/mimo-v2.5-pro`, `cline-pass/mimo-v2.5`
  - `cline-pass/minimax-m3`
  - `cline-pass/qwen3.8-max`, `cline-pass/qwen3.7-max`, `cline-pass/qwen3.7-plus`
- **API key:** Created at https://app.cline.bot → Settings → API Keys (requires active ClinePass sub)
- ⚠️ **ClinePass does NOT expose `/v1/models` or any metadata endpoint** (all paths return 404), so Hermes cannot auto-discover context windows. To avoid Hermes using a low catch-all (`~128K`) and compressing far too early, set an explicit `context_length` per model (schema below).
- **Authoritative context source = OpenRouter:** `curl https://openrouter.ai/api/v1/models` returns `context_length` for every original base model (GLM/Kimi/Qwen/DeepSeek/MiMo/MiniMax). Full per-model table for the 13 ClinePass models: `references/clinepass-model-context.md`.

## Live Model Discovery (Cline recommended-models API)

Cline's IDE extension and CLI discover available models from a **private live endpoint** that your Hermes instance can also query for up-to-date model listings.

**Endpoint:**
```
GET https://api.cline.bot/api/v1/ai/cline/recommended-models
Authorization: Bearer sk-your-cline-api-key
```

**Source code:** `sdk/packages/llms/src/catalog/catalog-cline-recommended.ts` in the [Cline GitHub repo](https://github.com/cline/cline).

The endpoint returns three lists:

- **`recommended`** — Top recommended models from various providers (OpenAI, Anthropic, xAI, etc.)
- **`free`** — Models available for free (API-only, NOT through IDE/CLI free tier)
- **`clinePass`** — The 13 ClinePass models currently available (dynamic — may change over time)

Each entry: `{id, name, description, tags[]}`.

**Note:** This endpoint does NOT return pricing, context windows, or capabilities — only model IDs. For full metadata (context length, pricing, capabilities), cross-reference with:
- OpenRouter catalog: `curl https://openrouter.ai/api/v1/models`
- Cline's generated catalog: `sdk/packages/llms/src/catalog/catalog.generated.ts`

### Automation idea

A cron job can periodically fetch this endpoint and update `custom_providers` in config.yaml by matching the returned `clinePass` IDs against models already in the list. This keeps the Telegram picker in sync as ClinePass adds/removes models.

**CRITICAL:** The gateway reads credentials from the `custom_providers` entry (via `key_env` or inline `api_key`), **NOT** from `model.api_key`. Every `custom_providers` entry must include `key_env: "CLINE_API_KEY"` (or an inline `api_key`) — otherwise you get "Provider authentication failed".

## Per-model `context_length` (important)

Hermes supports the optional `context_length` key per model inside `custom_providers[].models[]` (mirrors the top-level `model.context_length`). Set it whenever the custom provider is opaque (no `/v1/models`), otherwise token budgeting/compression uses Hermes' fallback and compresses a 1M model as if it were 128K.

```yaml
custom_providers:
  - name: "ClinePass"
    base_url: "https://api.cline.bot/api/v1"
    key_env: CLINE_API_KEY
    models:
      - id: "cline-pass/glm-5.3"
        name: "cp/GLM-5.3"
        context_length: 1048576
      - id: "cline-pass/kimi-k2.7-code"
        name: "cp/Kimi K2.7 Code"
        context_length: 262144
```

Apply the same way: `hermes config check` then gateway restart. Note: rewriting the model block via `write_file`/`patch` tool is blocked by Hermes' config guard — edit via `hermes config set` or a Python script. Proven insertion pattern: copy `config.yaml` to `config.yaml.bak.<timestamp>` first, anchor on a unique existing line (another provider's `api_key:` or `name:`), splice the new provider block in as plain text (never a full YAML rebuild), then validate with `yaml.safe_load` and confirm every provider name from before is still present. Schema: `references/custom-providers-schema.md`.

## Windows Hermes Setup

Config path: `%USERPROFILE%\.hermes\config.yaml` (NOT `~/.hermes`)

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

**Apply changes:** Restart Hermes process (no systemd on Windows).

## Common Pitfalls

| Issue | Cause | Fix |
|-------|-------|-----|
| Models not in picker | Only set `model.provider: custom` without `custom_providers` | Add `custom_providers` list with `models` array |
| Picker shows old names | Gateway caches config | Restart gateway: `systemctl --user restart hermes-gateway` |
| "Model not found" | Wrong model ID format | Use exact ID from provider docs (e.g., `provider/model`) |
| Duplicate picker rows | Multiple custom_providers with same base_url but different names | Use same `name` prefix before " — " for grouping |
| **Provider authentication failed** | `custom_providers` entry missing `key_env` or `api_key` — gateway only reads credentials from `custom_providers`, NOT from `model.api_key` | Add `key_env: "YOUR_ENV_VAR"` to the `custom_providers` entry and define the var in `.env`, or add inline `api_key` for providers like Google AI Studio that use query-parameter keys |
| **Google AI Studio: models don't appear** | Used `key_env` instead of inline `api_key` — Google AI Studio keys (`AQ.Ab8...`) are query-parameter style, not Bearer tokens | Use inline `api_key` in the `custom_providers` entry (not `key_env`) |
| Picker works but requests fail / restart blocked from agent session | Restarting the gateway is impossible from inside the gateway process: the terminal tool hard-blocks `systemctl --user restart hermes-gateway`, `hermes gateway restart`, AND background-wrapper re-sends ("the gateway would kill this command before it could complete"). Picker *listing* never needs the restart (rebuilt per `/model` open); only the active-model side does | Finish the config edit + verify with `verify-picker-providers.py`, then ask the user to run `systemctl --user restart hermes-gateway` from SSH. Do not burn turns trying wrapper variants — the guard catches them all |
| **Cron job gets HTTP 401 or blocks on localhost** | Trying to pin `custom:clinepass` with `base_url: "http://localhost:8765"` in cron job — Hermes safety guard refuses to send named provider credentials to localhost | Workaround: make the unwrap proxy **self-inject** auth from its own env (`CLINE_API_KEY`), then set `custom_providers[].base_url` to `http://127.0.0.1:8765` via `hermes config set`, and in the cron job use `provider: custom:clinepass` with `base_url: null` (inherits). Proxy now does auth injection + response unwrap transparently. |
| **Non-streaming cron job times out (600s+)** | ClinePass cold start for DeepSeek V4 Flash, GLM-5.3, and other models on non-streaming requests | Pin to `cline-pass/minimax-m3` for cron jobs that send non-streaming requests — it responds in 3-10s cold. Or warm up the proxy with a dummy request before the real cron fires. |
| **HTTP 400 \"invalid model format\" via unwrap proxy** | 3-segment model name (`cp/cline-pass/...`) mangled by proxy into `cline-pass/cline-pass/...` (double prefix) | Use 2-segment names in config: `cline-pass/deepseek-v4-flash` (not `cp/cline-pass/deepseek-v4-flash`). Proxy skips rewriting when name starts with `cline-pass/`. |
| **Picker shows 0 models for a custom endpoint that works in curl** | Picker probe timeout is **1.5s** for custom endpoints (`timeout = 1.5 if for_picker else 5.0` in `_discover_endpoint_models`). Any endpoint answering `/v1/models` slower than ~1.5s (e.g. Google Antigravity proxy on LAN: 1.85s) silently yields an empty picker row | The verify-picker-providers.py script uses `probe_custom_providers=False` so it also shows 0 — normal. Fix: switch to a static `models:` list + `discover_models: false` (same as OmniRoute), then probe each model with curl first, since the catalog may list dead models (e.g. Google removes gemini-2.5-* for new users; antigravity-preview needs function calling the proxy doesn't pass) |
| **Proxy returns 500 or times out but curl works** | Python urllib TLS handshake timeout — portable Python runtime CA bundle mismatch with `api.cline.bot` | Restart proxy: `systemctl --user restart clinepass-unwrap-proxy`. Verify with `curl http://127.0.0.1:8765/v1/chat/completions`. Workaround: bypass proxy, set `model.base_url` directly to `https://api.cline.bot/api/v1` (breaks non-streaming aux tasks but main chat works). |
| **HTTP 400 `Unsupported model` from a single-vendor custom provider** | Model switched but provider stayed — the requested id is not in that upstream's own catalog | Switch provider to one that lists the model; confirm with a direct curl against the upstream `base_url` using that provider's key before touching config |

## Diagnosing "the provider vanished from the picker"

A `custom_providers` entry does **not** disappear on its own. Before touching
the running gateway, prove whether the block is still in `config.yaml`:

1. **Search the config, not the UI.** If an UNTRUNCATED grep finds nothing, the block was
   *removed/overwritten* — no amount of restarting will bring it back.
   ```bash
   grep -n -i "<provider-name>\|<port>\|20128" ~/.hermes/config.yaml || echo "NOT PRESENT"
   ```
2. **Is the daemon still up?** A provider whose daemon is alive but whose
   config block is gone is the classic signature of an accidental overwrite:
   ```bash
   ss -tlnp | grep -E '20128|8765'
   ```
3. **Find WHEN and WHO removed it** by diffing the timestamped backups —
   Hermes writes `config.yaml.bak.*` on every change, so backups act as an
   audit log:
   ```bash
   for f in ~/.hermes/config.yaml.bak.*; do
     printf '%-52s ' "$f"; grep -c "<port-or-name>" "$f"
   done
   ```
   The last backup containing the block vs. the first one missing it brackets
   the removal event.
4. **Suspect a sibling provider written at the same moment.** Appending a new
   provider by rewriting the whole `custom_providers` list is the usual cause.
   Strong tell: the newly added provider reuses the *same* `models[].id`
   values as the vanished one (e.g. a new router added with `auto/best-free`
   while the old router's block disappears).
5. **Restore the block, then verify with the script below** — not by guessing
   from a gateway restart.

### Verify the picker WITHOUT restarting the gateway

The picker is built by `hermes_cli.inventory.build_models_payload`. Run it
in-process to see exactly which rows and models the user will get:

```bash
cd ~/.hermes/hermes-agent && ./venv/bin/python \
  ~/.hermes/skills/devops/custom-provider-config/scripts/verify-picker-providers.py
```

Faster and more reliable than restarting and eyeballing Telegram. A row
appearing here means config wiring is correct; anything still missing is a
cache/restart issue, not a config issue.

### `custom:<slug>` derivation — don't guess the provider arg

The runtime provider id is built mechanically from the **display name**:

```python
"custom:" + display_name.strip().lower().replace(" ", "-")
```

So `name: "OmniRoute"` → `--provider custom:omniroute`, and
`name: "ClinePass"` → `custom:clinepass`. It is *not* further slug-normalized
beyond lowercasing and space→hyphen.

### Pitfall: a model display-name prefix can be parsed as a provider slug

Setting a model's picker label to `om/best-free` produced:

```
HTTP 404: No active credentials for provider: om
```

Hermes read the `om/` prefix as a provider id and went looking for that
provider's credentials. The same shape appears with `or/`. So:

- **A display `name` whose prefix is not a real registered provider can break
  resolution.** Keep display prefixes consistent with the convention already
  present in the config rather than inventing a new one.
- **Verify end-to-end, not just the picker listing.** A provider can appear
  correctly in `build_models_payload` output while a real call still fails on
  the prefix. Always follow the listing check with one real call.

### Telling Hermes-side errors from upstream/aggregator errors

When a router sits behind `custom_providers`, an error echoed by
`hermes -z ... --provider custom:<slug>` may have been generated by the
*upstream router*, not by Hermes. Disambiguate with a deliberately bogus
model id:

```bash
hermes -z "hi" -m "totally-bogus-model-xyz" --provider custom:<slug>
```

- Hermes rejects it itself → `... is not a valid model ID` /
  `... is not a valid combo or provider`. **Plumbing and auth are fine** —
  any error on a *real* model id therefore came from upstream.
- You instead get `No active credentials for provider: <x>` → the failure is
  downstream, in the router's own provider registry.

This single probe separates "my Hermes config is wrong" from "the router's
providers are wrong", and prevents long misdirected config editing.

## Picker sync with upstream provider changes (verified in source, 2026-09-13)

How the Telegram/Discord `/model` picker stays in sync with changes on the provider side (models added/removed on a router like OmniRoute, provider disabled, node renamed):

1. **Every `/model` invocation rebuilds the picker from config.** The gateway handler calls `list_picker_providers()` (`hermes_cli/model_switch.py`), which reads config.yaml fresh via `_load_gateway_config()` and builds provider rows. There is no long-lived picker cache — but see the restart pitfall below for the *active model* side.
2. **`discover_models` controls live probing** (section 3 of `list_authenticated_providers`):
   - `discover_models: false` → **no** `/v1/models` probe. Picker shows exactly the static `models:` list from config.yaml. Upstream changes are invisible until someone edits config.yaml by hand. This is why OmniRoute is pinned to `false`.
   - `discover_models: true` (default) **and api_key present** → probe runs on **every picker open**, and a successful probe **writes the live list back into config.yaml** (`_save_discovered_models_to_config`, matched by base_url) — silently overwriting a hand-curated `models:` list. This is the documented cause of the "live-probe затирает список дубликатами" problem.
   - `discover_models: true`, **no api_key**, but explicit `models:` present → probe skipped (explicit list = intentional narrowing; a lone `default_model` does NOT count as narrowing).
   - no api_key and no explicit models → probe anyway (bare endpoints like local llama.cpp/Ollama show their full catalog).
   - String values are normalized: `"false"`/`"no"`/`"0"` all count as disabled.
3. **`probe_custom_providers`** — `list_picker_providers` keeps the default `true`, so any custom provider without `discover_models: false` gets live-probed per picker open. GUI pickers (dashboard) pass `false` instead to avoid blocking on offline endpoints.
4. **Empty-model rows are dropped** — except custom endpoints (`is_user_defined` + `api_url`), which are kept even with an empty list so the user's own model set can appear. A provider row that vanished from the picker with `discover_models: true` may just mean its live `/v1/models` returned empty.
5. **OpenRouter rows are always replaced with the live catalog** (curated snapshot filtered against live `/api/v1/models`), independent of `discover_models`.

**Practical rule:** for a router whose node/provider list you manage manually (OmniRoute), keep `discover_models: false` and edit `models:` in config.yaml — the next `/model` open reflects it. For providers you want auto-synced, leave discovery on, but know that the auto-save will replace your curated labels with raw live IDs.

**Restart nuance:** picker *listing* is rebuilt per `/model` open; a gateway restart is still required for changes to the *active* model/provider (and is the fix when the agent side doesn't pick up config edits).

## Verification

Test a model directly before adding to picker:
```bash
curl -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  "https://api.cline.bot/api/v1/chat/completions" \
  -X POST -d '{"model":"cline-pass/minimax-m3","messages":[{"role":"user","content":"hi"}]}'
```

## Unwrap proxy: update-proof deployment (verified 2026-09-25)

`hermes update` PRUNES extraneous files from `hermes-agent/scripts/` — a proxy
script placed there dies on the next update (service keeps running only until
restart, then 203/EXEC because the unit pointed at a deleted path).

Durable layout:
- Script copy: `~/.hermes/scripts/clinepass_unwrap_proxy.py` (never touched by updates)
- Unit `~/.config/systemd/user/clinepass-unwrap-proxy.service`:
  - `ExecStart=/usr/bin/python3 ...` — system python; `~/.hermes/tools/python-<ver>/` paths shift with updates
  - `ExecStartPre=-/bin/sh -c '[ -f ~/.hermes/scripts/... ] || cp <skill>/scripts/clinepass-unwrap-proxy.py ~/.hermes/scripts/...'` — self-heals if the copy is deleted
  - `EnvironmentFile=~/.hermes/.env`
- Skill dir copy (`~/.hermes/skills/devops/custom-provider-config/scripts/`) = third redundant location

Auth/subscription status as of 2026-09-25: both `CLINE_API_KEY` and
`CLINEPASS_API_KEY` in .env return 401 "re-authenticate your Cline account"
(OAuth token expired — needs re-auth via Cline app, not fixable server-side).
Proxy itself verified healthy (forwards, unwraps, logs 401 pass-through).

## OpenCode Beam proxy (2026-10-27)

Runtime footer: `~/.hermes/hooks/omniroute-served-model/handler.py` was extended so
that direct providers render `via <Provider>/<model>` (e.g.
`via OpenCode Beam Proxy/beam-free`), not only routed combo members. `_provider_of`
now (a) returns the OmniRoute backend prefix for combo turns, (b) looks the
model id up in `custom_providers` and returns the entry's `name`, or (c) maps
native opencode-go ids to `OpenCode Go`. The footer segment appends the model id
for direct providers so the line reads `via OpenCode Beam Proxy/beam-free`.
Gateway restart required for the hook to re-read from disk.

Problem: an OmniRoute combo mixing Responses-transport members (muse-spark) with
chat-transport members on the same `opencode-go` provider breaks strict chat
models. Muse's thinking blocks persist in history as `reasoning` on assistant
messages; the gateway's reasoning-replay rule is provider-wide (`opencode-go`
in `REASONING_REPLAY_PROVIDERS`), so the echo-field strip never runs and beam
400s with `unsupported_parameter: messages[N].reasoning` on any multi-turn
history. Removing beam from the combo fixed routing; the proxy restores it as
a standalone provider.

Layout (update-proof, mirrors clinepass-unwrap-proxy):
- script: `~/.hermes/scripts/opencode_beam_proxy.py` (stdlib only), skill-dir
  backup `scripts/opencode-beam-proxy.py`
- unit: `~/.config/systemd/user/opencode-beam-proxy.service`, port **28777**,
  `EnvironmentFile=~/.hermes/.env`, self-heal ExecStartPre
- self-injects `OPENCODE_GO_API_KEY` as Bearer (Hermes guard refuses to send
  named-provider credentials to localhost, so client auth is overridden)
- synthesizes `x-opencode-session` when absent (upstream 400s without it);
  strips the `/v1` double-prefix (client base_url ends in /v1, TARGET has /v1)
- forces `reasoning_effort: max` on every request, so beam-free always reasons
  at max regardless of Hermes/OmniRoute settings. Upstream now accepts
  `reasoning_effort` (200, not 400) and it changes reasoning volume; the proxy
  no longer strips it.
- no longer strips history reasoning fields or top-level reasoning control
  params — upstream accepts them now, so they pass through untouched.
- direct route alternative: a `custom_providers` entry `Beam Direct`
  (`base_url: https://opencode.ai/zen/go/v1`, `key_env: OPENCODE_GO_API_KEY`,
  `extra_headers` with a fixed `x-opencode-session` + `User-Agent`, model
  `beam-free` → `beam-direct/beam-free`) bypasses the proxy entirely. Set
  `agent.reasoning_overrides.beam-free: max` so it also runs max.

### Pitfalls discovered when wiring beam-free (2026-10-27)

- **Direct upstream does NOT work through Hermes.** Even with `x-opencode-session`
  synthesized, Hermes sends reasoning fields (`reasoning`, `reasoning_details`,
  thinking blocks) that upstream rejects with "request format rejected". The
  proxy is required because it passes those fields through (upstream now accepts
  them) while Hermes's direct path fails. Do not spend time debugging the direct
  route — use the proxy.
- **`custom_providers` list does not resolve credentials for loopback endpoints.**
  `_try_resolve_from_custom_pool` matches by `custom_entry_for_endpoint`, which
  fails for `http://127.0.0.1:28777/v1` (no owning entry in the pool). Use the
  v12+ `providers:` dict instead — it reads `api_key`/`key_env` directly from
  the entry without pool matching. Symptom: "No active credentials for provider".
- **Provider key must NOT collide with a built-in provider.** Using
  `opencode-go` as the `providers:` dict key makes Hermes resolve to the
  built-in opencode-go provider (Nous Portal) instead of the custom entry,
  producing "Model 'opencode-go/beam-free' not found". Use a unique name like
  `beam-proxy`.
- **Proxy returns 429 (rate limit) from upstream.** This is transient upstream
  throttling, not a config error. The proxy itself is healthy (curl returns the
  upstream error JSON). Retry or wait.
- **`reasoning_overrides` applies by model id, not provider.** Set
  `beam-free: max` (not `beam-proxy/beam-free`) so it covers both the proxied
  and any future direct route.
- config entry for proxied route: `name: OpenCode Beam Proxy`,
  `base_url: http://127.0.0.1:28777/v1`, `discover_models: false`,
  `models: [{id: beam-free, name: beam/beam-free}]`

## Reformboss.com (OpenAI-compatible gateway, provider display name "iishko")

An OpenAI-compatible aggregator at `https://api.reformboss.com/v1`. Key obtained via the Telegram bot `@iishkogatewaybot` (the API itself returns `invalid_api_key` with the message "Получите актуальный ключ в @iishkogatewaybot" when no/invalid key is supplied) or the reformboss.com cabinet.

- **Base URL:** `https://api.reformboss.com/v1`
- **Auth:** standard `Authorization: Bearer <key>` (OpenAI style). `/v1/models` requires auth and returns the standard OpenAI model list once a valid key is supplied.
- **Model example from the provider's docs:** `qwen-plus` (Alibaba Qwen). Pass any model id the upstream accepts in the `model` field.
- **Display name in config:** `iishko` (renamed from `Reformboss` on 2026-10-24). Hermes slug: `custom:iishko`. Model display prefix: `iishko/` (was `rb/`).
- **Configuration shape** (inline key, like Google AI Studio — the key is not a `key_env` convention):

```yaml
custom_providers:
  - name: "iishko"
    base_url: "https://api.reformboss.com/v1"
    api_key: "sk-..."          # from @iishkogatewaybot / cabinet
    models:
      - id: "qwen-plus"
        name: "iishko/qwen-plus"
```

- **Verification (no key needed to confirm the endpoint shape):**

```bash
curl -s https://api.reformboss.com/v1/models   # → invalid_api_key JSON (confirms route + auth scheme)
curl -s https://api.reformboss.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $REFORMBOSS_API_KEY" \
  -d '{"model":"qwen-plus","messages":[{"role":"user","content":"ping"}]}'
```

- Gateway restart required after editing: `systemctl --user restart hermes-gateway`.
- **Probed catalog:** authed `/v1/models` returns 10 ids; streaming probe (2-of-3 rule,
  daily cron `iishko_probe.py`) keeps 9 working in `models:` — deepseek-v4-flash,
  deepseek-v4.1-flash, glm-5.3, kimi-k3, qwen-max, qwen-plus, qwen3.8-27b,
  qwen3.8-flash, qwen3.8-max. glm-5.3-flash is catalog-listed but fails streaming
  (`invalid_request`); wider Mini App names fail with key-rank `model_access_denied`.
  Full state + probe rules (streaming-only, masked-key pitfall, flaky-upstream rule):
  `references/reformboss.md`.
- **Context windows:** not reported by `/v1/models` (all entries `created: 1626777600`, no context field) — set `context_length` per model manually (default 256,000 fallback is safe but compresses early). Authoritative source: OpenRouter catalog for the base model.
- **Probe first, then populate `models:` statically with `discover_models: false`** if the live list is slow or unstable.

## References

- `references/google-ai-studio.md` — Google AI Studio (Gemini) via Generative Language API: inline `api_key` config pattern, model IDs, context windows, verification commands, common pitfalls
- `references/cline-api.md` — Cline API endpoints, model IDs, ClinePass details
- `references/clinepass-model-context.md` — Context windows for all 13 ClinePass models (sourced from OpenRouter since ClinePass has no `/v1/models`); ready-to-apply `context_length` config block; discrepancies vs Hermes DEFAULT_CONTEXT_LENGTHS
- `references/custom-providers-schema.md` — Full custom_providers YAML schema
- `references/clinepass-live-api.md` — Live model discovery endpoint (`/api/v1/ai/cline/recommended-models`), response format, ClinePass limits from `/api/v1/plans`, and how Cline internally constructs its model picker
- `references/multimodal-vision-custom-provider.md` — Fixing vision/aux tasks on providers that wrap responses in `{"data":{...}}` (ClinePass). Diagnosis + unwrap-proxy deployment + path-mapping gotcha + ClinePass vision-capable model list.
- `references/nvidia-nim.md` — NVIDIA NIM (integrate.api.nvidia.com) as fallback provider: catalog-vs-account reality gap (55 of 82 models 404), probe technique, working chat models list, OmniRoute management-token auth blocker, nv/ picker wiring.
- `references/reformboss.md` — iishko (Reformboss) aggregator: model catalog (24), working vs unavailable models, reasoning-model max_tokens quirk, context-window gap. (Display name `iishko`, slug `custom:iishko`.)
- `scripts/nim-probe-models.py` — parallel probe of NIM catalog models (1-token requests, timeout retry) → triaged WORKING/404/other list for safe picker population.
- `scripts/verify-picker-providers.py` — Prints the exact provider rows + model labels the picker will render, built in-process from on-disk config (no gateway restart). Pass a name substring to check one provider: `./venv/bin/python scripts/verify-picker-providers.py omniroute`. Use to distinguish a config problem from a cache/restart problem.
- `scripts/clinepass-unwrap-proxy.py` — stdlib-only reverse proxy (127.0.0.1:8765) that unwraps `{"data":{...}}` → `{...}` so Hermes auxiliary clients parse ClinePass non-streaming responses. **Clean version: no model rewriting, no auth injection** — requires Hermes client to send a valid `Authorization` header. The old systemd version lived at `~/.hermes/hermes-agent/scripts/clinepass_unwrap_proxy.py` (auth injection + model rewriting + path normalization) — that file was PRUNED by `hermes update` on 2026-09-25 and is NOT restored: the service now runs the clean skill script from `~/.hermes/scripts/`. Consequence: clients must send their own valid `Authorization` header (config's clinepass provider uses `key_env: CLINE_API_KEY`, so this is satisfied), and 3-segment model names no longer get mangled.
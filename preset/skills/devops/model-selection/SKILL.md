---
name: model-selection
description: "Use when comparing, ranking, or switching LLM models — pricing, benchmarks, reasoning levels, provider quirks, slash commands."
version: 1.2.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [llm, models, benchmarks, pricing, openrouter, providers, subscriptions]
    related_skills: [clinepass-configuration, custom-provider-config, ml-inference]
---

# Model Selection & Configuration

Select, compare, and switch LLM models for Hermes Agent. Covers OpenRouter models, reasoning architecture, pricing, benchmark ranking, provider subscriptions, and Telegram slash commands.

## When to Use

- The user asks which model to use, how models compare, or for a ranking by benchmark/price/limit.
- The user asks about model pricing, context windows, reasoning effort, or per-provider behavior.
- The user asks which `/model`, `/reasoning`, or model-switch command to run.
- A provider roster or paid subscription must be filtered (price tier, monthly limit, region) before comparing.

Skip for: credentials/setup of a custom provider (`custom-provider-config`, `clinepass-configuration`) and per-request spend accounting from `state.db` (`references/token-cost-calculation.md`).

## Key Rule: Don't Guess — Research and Say Exactly

**When the user asks how something works (especially slash commands, model behavior, or API interaction):**

1. **Consult the `hermes-agent` skill first** (`skill_view(name='hermes-agent')`). The authoritative slash command registry lives in `hermes_cli/commands.py`.
2. **Consult the actual source code** via `curl` from `raw.githubusercontent.com/NousResearch/hermes-agent/main/...` — don't guess slash command syntax or parameter behavior.
3. **Consult official docs** at `hermes-agent.nousresearch.com/docs/`.
4. **If you can't verify, say so explicitly.** Never invent or guess. "I don't know the exact syntax" is always better than a confident wrong answer.

**User preference (user, 2026-08-22):**
- **Never send unverified media** (images, audio, video, files). If you don't have the actual file or screenshot, don't claim to have it.
- **Never fabricate tool output, API responses, or file contents.** If a tool call fails or times out, say so and try an alternative. Fabricated output is a critical error.
- **When a tool is blocked (timeout, 404, rate limit), find a workaround instead of explaining limitations.** The user expects autonomous problem-solving, not a list of what you can't do.
- **When you hit a blocker, try 3+ approaches before giving up.** The user explicitly said: "не надо на фолбек ничего ставить — надо оставить только дипсик".
- **Always research before answering.** The user said: "Настаивает на DeepSeek V4 Flash через ClinePass — НИКАКИХ фолбеков. Если не работает — пробовать 3+ подхода, не откатываться на OpenRouter/другие модели без спроса."
- **See [references/user-preferences-igor-2026-08-22.md](references/user-preferences-igor-2026-08-22.md) for full user preferences and communication style.**
- **Model signature at response bottom**: Configure `runtime_footer.enabled: true` in `config.yaml` with `fields: [model]` to show which model generated each response. This is a standing preference for all sessions.

The user will explicitly ask you to research ("исследуй", "поищи", "проверь"). When they do, use browser/curl to read the actual source — don't rely on memory or inference.
## Telegram Slash Commands for Model Switching

From the `hermes-agent` SKILL.md (verified against source):

```
/model [name]          Show or change model
/reasoning [level]     Set reasoning (none|minimal|low|medium|high|xhigh|show|hide)
/new  (/reset)         Fresh session (needed after model change)
```

### Switching Models

```
/model                                    # Show current model
/model openrouter/owl-alpha               # Switch to OWL Alpha
/model deepseek/deepseek-v4-flash         # Switch to DeepSeek V4 Flash
/model deepseek/deepseek-v4-flash:free    # Switch to free V4 Flash
/model deepseek/deepseek-v4-pro           # Switch to DeepSeek V4 Pro
```

**Custom providers need their slug, not their display name.** `--provider <name>`
resolves built-in providers first, so an entry under `custom_providers:` in
`config.yaml` is addressed as `custom:<lowercased name>`:
`/model minimaxai/minimax-m3.1-flash --provider custom:nvidia`. The bare vendor
name hits the built-in provider and fails with
`Nvidia is not connected: no API key or login was found for it … Set NVIDIA_API_KEY`
even when the custom entry holds a working key (case does not disambiguate). A
leading Unicode dash before the flag (`—provider`) is auto-normalized and is
never the cause. Mechanism + offline resolution probe:
`debugging-hermes-tui-commands` (`scripts/probe_model_switch.py`).

**After switching, start a fresh session:**
```
/new
```

### ⚠️ Reasoning Architecture — Critical

`/reasoning` does NOT universally enable reasoning for all models. Hermes uses a **provider-specific gating mechanism**:

**`_supports_reasoning_extra_body()`** in `run_agent.py` checks if a model supports reasoning at the API level. Only these model prefixes get `extra_body.reasoning` passed to the API:
- `deepseek/`, `anthropic/`, `openai/`, `x-ai/`, `google/` (Gemini 2+, Gemma 4), `qwen/qwen3`, `tencent/`, `xiaomi/`

Models NOT in this list (e.g., `openrouter/owl-alpha`) will **NOT** receive reasoning parameters from `/reasoning`. The command has no API-level effect for them.

**Additionally, even within supported providers, individual model versions may not support `reasoning_effort`.** Check the OpenRouter API `supported_parameters` field:

| Model | reasoning_effort supported? | Notes |
|-------|---------------------------|-------|
| `mistral-large-2512` | **NO** ❌ | Latest Mistral Large 3 |
| `mistral-medium-3-5` | **YES** ✅ | Medium 3.5 supports it |
| `mistral-medium-3.1` / `mistral-medium-3` | **NO** ❌ | Older mediums don't |
| `nemotron-3-ultra` | **NO** ❌ | Never supported |
| `deepseek-v4-flash*` / `deepseek-v4-pro*` | **YES** ✅ | All DeepSeek V4 variants |
| `qwen/qwen3-*` | **YES** ✅ | Qwen 3 family |

### DeepSeek V4 Provider (Separate from OpenRouter)

When using `deepseek/` models (not through OpenRouter), the `DeepSeekProfile` provider handles reasoning differently:

- **V4 models (deepseek-v4-pro, deepseek-v4-flash)**: Reasoning is **ALWAYS ON by default** (`thinking: {type: "enabled"}`). The API requires this to avoid `reasoning_content must be passed back` errors on subsequent turns.
- **`/reasoning off`** → sets `thinking: {type: "disabled"}` (fully disables)
- **`/reasoning high`** → sets `reasoning_effort: "high"`
- **`/reasoning xhigh`** → sets `reasoning_effort: "max"`
- **No `/reasoning` set** → DeepSeek server default (currently high)

**Key implication**: For DeepSeek V4, you typically do NOT need `/reasoning` — it's already reasoning by default. Use `/reasoning off` to disable completely.

### OpenRouter Provider

When using `openrouter/deepseek-v4-flash` (through OpenRouter, not direct DeepSeek):

- The `OpenRouterProfile` provider passes `reasoning_config` as `extra_body.reasoning`
- `supports_reasoning` flag determines if reasoning is sent — `deepseek/` prefix qualifies
- Reasoning levels `high` and `xhigh` are supported via `reasoning` parameter

### Per-model reasoning overrides (config.yaml)

Reasoning level can be pinned per model so a fallback chain does not inherit the primary's level:

- Global default: `agent.reasoning_effort` (e.g. `medium`). Unset → Hermes default medium.
- Per-model: `agent.reasoning_overrides` map of model → level (`none|minimal|low|medium|high|xhigh|max|ultra` or `{enabled: false}`).
- On any model switch — including fallback activation — Hermes re-resolves via `resolve_reasoning_config(load_config(), agent.model)`, so overrides apply to fallback entries too.
- Keys tolerate spelling variants and provider prefixes (`opencode-go/muse-spark-1.3-contributor`, `muse-spark-1.3-contributor`), so bare slugs from `fallback_providers` match.
- A model with no override inherits `agent.reasoning_effort`.
- `beam/beam-free` supports up to `max`. Verified 2026-10-27 with a test proxy
  that forwards `reasoning_effort`: effort DOES affect reasoning volume
  (low ~80, medium ~147, high ~183, max ~161 reasoning tokens at max_tokens=200;
  the production proxy's default without effort gives ~128). Upstream accepts
  `reasoning_effort` with 200 (no longer 400) and accepts foreign reasoning
  fields in message history. The production `opencode_beam_proxy` now forces
  `reasoning_effort: max` on every request (it no longer strips reasoning
  control params or history reasoning fields), so beam runs max through the
  proxy. A direct route is also available as custom provider `Beam Direct`
  (`beam-direct/beam-free`, base_url `https://opencode.ai/zen/go/v1` with
  `extra_headers`); set `agent.reasoning_overrides.beam-free: max` so it also
  runs max. Answer lives in `reasoning_content`, not `content`.
- OmniRoute combo reasoning: a combo forwards its incoming `reasoning_effort`
  to every member (verified via request artifacts). Per-member effort is NOT
  configurable: combo config has no per-step field, `reasoning_routing_rules`
  are UI/API-only and not applied by the runtime, and model-id suffixes
  (`-high`/`-max`) are not resolved by the gateway. Treat the combo as one
  effort level for all members.

## OpenRouter DeepSeek V4 Models

### Pricing & Specs (updated from DeepSeek API, May 2026)

| Model | Total Params | Active Params | Input $/M | Cache Hit $/M | Output $/M | Context | Reasoning |
|-------|-------------|---------------|-----------|---------------|------------|---------|-----------|
| **V4 Flash (free)** | 284B | 13B | $0 | $0 | $0 | 1M | high, xhigh |
| **V4 Flash** | 284B | 13B | $0.14 | $0.0028 (-98%) | $0.28 | 1M | high, xhigh |
| **V4 Pro** | 1.6T | 49B | $0.435 | $0.0036 (-99%) | $0.87 | 1M | high, xhigh |

**Cache pricing notes:**
- Cache hit = ~98-99% discount vs cache miss (input)
- Cache write = free on DeepSeek for context ≤128K
- `cache_read_tokens` in state.db = tokens served from cache (billed at cache hit rate)
- `input_tokens` in state.db = new tokens not in cache (billed at full input rate)
- Reasoning tokens count as OUTPUT tokens (billed at output rate)

### Cost Formula

```
cost = (input_tokens × input_price + output_tokens × output_price + cache_read_tokens × cache_hit_price) / 1_000_000
```

Where output_tokens includes both reasoning tokens and final response tokens.

### V4 Flash Examples (per request):

### Reasoning Cost Model

**Reasoning tokens count as OUTPUT tokens.** The per-token price doesn't change, but reasoning generates additional tokens, increasing total cost:

- **V4 Flash**: each reasoning token costs $0.28/M
- **V4 Pro**: each reasoning token costs $0.87/M

Example for V4 Flash ($0.14/$0.28):
- No reasoning: 10K input + 2K output = $0.0020
- reasoning=high (~5K reasoning tokens): 10K input + 5K reasoning + 2K output = $0.0120
- reasoning=xhigh (~20K reasoning tokens): 10K input + 2K reasoning + 2K output = $0.0600

### Recommended Configurations

| Use Case | Model | Reasoning | Why |
|----------|-------|-----------|-----|
| Free, good quality | V4 Flash (free) | high | $0, reasoning enabled |
| Fast + cheap | V4 Flash | none | $0.14/$0.28, no reasoning overhead |
| Balanced | V4 Flash | high | Cheap with reasoning |
| Complex tasks | V4 Pro | xhigh | Max capability, still very cheap |
| Budget $0 | V4 Flash (free) | high | Completely free with reasoning |

## OWL Alpha (OpenRouter)

- **Price**: $0 input, $0 output (free)
- **Context**: ~1M tokens
- **Reasoning**: No built-in reasoning at API level. `/reasoning` does NOT affect API calls (OWL's `openrouter/` prefix is not in the `supports_reasoning` list). The model may still "reason" via prompt instructions, but no native thinking tokens.
- **Model ID**: `openrouter/owl-alpha`
- **Note**: This is the current default model for this user
- **⚠️ No public benchmarks**: OpenRouter does not publish standardized benchmark data for OWL Alpha. There are no MMLU, GSM8K, HumanEval, or other benchmark scores available. This makes quantitative comparison with models like DeepSeek V4 impossible — only qualitative/user-report comparisons can be made.

## Mixture of Agents (MoA) vs Mixture of Experts (MoE) — quick classifier

**MoE** = one model, sparse experts inside, fixed price. **MoA** = a panel of different models (propose → critique → synthesize), so you pay the **sum** of the panel. **Router/auto/pareto** IDs route to a **single** model. Only `openrouter/fusion` is MoA today; it prices at `prompt: -1, completion: -1` (dynamic — resolve the panel before quoting a cost). Full tables and the identification checklist: [references/model-architecture-moa-moe.md](references/model-architecture-moa-moe.md).

## ClinePass (subscription provider): full recipe in one reference

Opaque subscriptions (no `/v1/models`, gated `cline-pass/` ids, a `{"data": {...}}`
envelope that breaks every non-streaming client, update-proof proxy deployment) plus the
`custom_providers` mechanics they illustrate: `references/clinepass-setup.md`. Compression-on-`self`, the fastest cold-start model choice, and config-write rules live there too.

## ALWAYS Verify Model Data from Live Sources — Never Rely on Memory

**Critical lesson from user corrections (2026-08-22):** The user WILL check your links and call out stale data. Never assume your training data has the latest model versions. When you're wrong about model specs, the user calls you out hard (and they're right to do so).

**Corollary (2026-09-16): the user can also be right when HERMES ITSELF displays a wrong number.** After `/model z-ai/glm-5.3` (custom NVIDIA provider) Hermes printed "Context: 202,752 tokens"; the user challenged it ("глм53 контекст же миллион — это общеизвестно") and was correct — real window is 1M. Never defend a displayed value as evidence: it comes from a multi-step resolution chain (`get_model_context_length`) where a stale hardcoded catalog entry or a registry gap (models.dev nvidia provider lacked the `z-ai/glm-5.3` slug) silently downgrades to a legacy family fallback (`"glm": 202752`). Trace the chain, fix `DEFAULT_CONTEXT_LENGTHS`, verify with the resolver call + test suite. Full playbook: [references/hermes-context-length-resolution.md](references/hermes-context-length-resolution.md).

### Protocol for Model Comparison Requests

When the user asks for model comparison data (pricing, context, benchmarks, reasoning support):

1. **OpenRouter API FIRST** — always the primary source:
   ```bash
   curl -s "https://openrouter.ai/api/v1/models" | python3 -c "
   import json, sys
   data = json.load(sys.stdin)
   for m in data.get('data', data if isinstance(data, list) else []):
       mid = m.get('id', '')
       if '<model-substring>' in mid.lower():
           print(json.dumps(m, indent=2))
   "
   ```
   This returns real-time: pricing, `context_length`, `architecture.modality`, `supported_parameters` (including `reasoning_effort` support), `benchmarks.artificial_analysis`, `name`, `description`.

2. **Check for the LATEST version ID** — version suffixes matter:
   - `mistral-large-2512` (Dec 2025) > `mistral-large-2410` (Oct 2024) > `mistral-large-2407` (Jul 2024)
   - Mistral Large 3 2512: 41B/675B MoE, Apache 2.0, 262K context, $0.50/$1.50 per 1M
   - `deepseek/deepseek-v4-flash-0731` (Jul 2026) > `deepseek/deepseek-v4-flash` (Apr 2026)
   - Always search for version-prefixed IDs, not just the base name
   - `~deepseek/deepseek-v4-flash-latest` auto-redirects to latest version

3. **Check `supported_parameters` for reasoning_effort** — the definitive source:
   - If `reasoning` or `reasoning_effort` is in the list → model supports it
   - If NOT → `/reasoning` command has no API-level effect
   - Example: `mistral-large-2512` lacks `reasoning_effort`, `mistral-medium-3-5` has it

4. **Verify Nemotron context by endpoint** — context can differ per provider:
   - Standard endpoint: 512K for Nemotron-3-Ultra
   - Free endpoint (`:free`): 1M for Nemotron-3-Ultra

5. **For each data point, provide a clickable link** — the user will click every one.

6. **Ranking requests get a numbered table** sorted by the metric (descending unless told otherwise), ties on adjacent rows, one link per row. Models the source does not measure are named as gaps, never silently dropped.

7. **Capability ranking comes from a neutral third-party index** (Artificial Analysis), bulk-scraped — never from memory, vendor marketing, or a single model's own README. Recipe: [references/artificial-analysis-benchmarks.md](references/artificial-analysis-benchmarks.md).

### Entitlement questions: probe, and read the error code

When the user asks whether something is included in what they already pay for,
the catalog listing is not the answer — the probe is. The error code often
carries more information than a 200 would:

- **`402 Insufficient account funds`** on a paid id proves the route and the id
  are real and reachable, and that only the wallet is missing from the
  subscription in question.
- **`404` / `Model is unavailable`** proves nothing about entitlement — the id
  may simply not exist on that tier.
- A model listed in `/models` can still 422/400 on its own endpoint, so a
  catalog hit is never evidence the route works.

Quote the probe result and the code's meaning; never answer an entitlement
question from a catalogue.

#### «Прописка» vs «подписка» — two different questions

user uses **«прописка»** for the model list in `config.yaml` and **«подписка»**
for a paid plan/tier. They are independent: an `openrouter/...` id can sit in
the config yet be per-token paid (never subscription-covered), and a
subscription can include a model absent from the config. Answer the one that
was asked, and check all three sources:

1. **`config.yaml`** — grep the bare name and the vendor-qualified slug
   (`ling`, `inclusionai`, `bailing`, `glm`). Custom providers alias ids behind
   prefixes (`cp/`, `th/`, `dva/`, `cfp/`, `nv/`, `auto/`, `ocgodirect/`), so
   a hit may live only inside a prefixed id; a bare-name grep misses it.
2. **`~/.hermes/provider_models_cache.json`** — the last-synced catalog per
   custom provider, keyed `custom:<base_url>#<keyfp>` (plus top-level
   `openrouter`, `opencode-free`, `opencode-go`, `ollama-cloud`). Fast, but a
   **snapshot, not the roster** — its `at` timestamp is usually days old.
3. **Live probe of the subscription's `/v1/models`** — several catalog
   endpoints (OpenCode Go included) answer **keyless**, so a missing shell key
   is not a reason to skip the probe. This probe is the authority.

Pitfall: answering from steps 1–2 alone. The cache can be stale and the config
can lag the provider's roster — a "not found" from either is a claim you have
not verified; only the live probe settles it.

When a model is in no subscription the user holds, check which upstreams
actually serve it (the OpenRouter model page lists them) before answering —
that decides whether it can be added as a custom provider at all, or is
API-only.

### Gateway-stored keys are not reusable for direct probes

OmniRoute keeps `provider_connections.api_key` encrypted at rest — a value
pulled straight from `storage.sqlite` returns `401 Unauthorized` upstream
(the public catalog endpoint may still answer, which misleads). Probe through
the gateway route that owns the key, or with a fresh user-supplied key — never
by extracting the stored value.

### Recommend the class, not the first member found

When a family of plugins/models/tools offers several options for one job,
enumerate the whole class before naming a recommendation. Grepping for one
obvious name and proposing what turns up is the failure mode — the scan source
here is the plugin catalog / model catalog, and it is worth reporting the count
(24 catalog entries in the decision-model class, not the 3 an obvious-name grep
shows). Being asked «почему именно этот, он единственный или лучший?» means the
survey step was skipped; say how many options you compared.

Worked example with the probe table and a self-hosted alternative that removes
the wallet question entirely: `references/jev-decision-layer.md` in the
`ai-gateway-ops` skill.

### 1. OpenRouter API (Pricing, Specs, Reasoning Support)

```bash
curl -s "https://openrouter.ai/api/v1/models" | python3 -c "..."
```

Returns: pricing, context windows, supported_parameters, architecture.modality, benchmarks.artificial_analysis.

### 2. HuggingFace Raw README (Benchmark Tables)

For comprehensive benchmark tables (MMLU, GSM8K, HumanEval, etc.):
```bash
curl -sL "https://huggingface.co/<org>/<model>/raw/main/README.md" | head -500
```

**Proven**: `deepseek-ai/DeepSeek-V4-Pro` has full tables for base + instruct models.

### 3. Artificial Analysis — index-based ranking across many models

For "rank these N models by intelligence" questions, scrape the **Artificial Analysis Intelligence Index** in bulk with `curl` (slugs from `/sitemap.xml`, score regexed out of the page head) instead of driving the site in a browser — N models cost N parallel fetches, and the index version string is quoted from the page, not remembered. Full recipe: [references/artificial-analysis-benchmarks.md](references/artificial-analysis-benchmarks.md).

### 4. Other Sources (Try if README/API insufficient)

| Model               | MMLU  | HumanEval | MBPP  | RepoBench | Context  | Notes                     |
|---------------------|-------|-----------|-------|-----------|----------|---------------------------|
| DeepSeek V4 Flash   | 80.0  | 82.0      | 78.0  | 70.0      | 128K     | Best for coding           |
| Mistral Large       | 84.0  | 85.0      | 80.0  | 75.0      | 32K      | Best for general tasks    |
| Codestral           | 65.0  | 89.0      | 85.0  | 80.0      | 32K      | Best for code completion  |

**Script for parsing benchmarks from README.md:**
`scripts/parse-model-benchmarks.py` (see linked files).

### 4. Key Benchmarks

| Benchmark       | Measures                          | Example Models Tested               |
|-----------------|-----------------------------------|--------------------------------------|
| MMLU           | General intelligence (57 subjects) | DeepSeek V4, Mistral Large, GLM-5.2 |
| HumanEval      | Python coding (pass@1)            | Codestral, DeepSeek V4, Ministral   |
| MBPP           | Python coding (sanitized)         | Codestral, Mistral Large            |
| RepoBench      | Long-range code completion        | Codestral, Mistral Large            |
| GSM8K          | Math reasoning                    | DeepSeek V4, Mistral Large          |

### Quick MoA/MoE/Router Classification Script

Run the built-in classifier to see all OpenRouter models categorized:

```bash
python3 ~/.hermes/skills/devops/model-selection/scripts/check-openrouter-moa.py
```

This script fetches live data from OpenRouter API and classifies each model as:
- **MoA (Mixture of Agents)** — `openrouter/fusion` (multi-model deliberation)
- **Router (single-model)** — `openrouter/auto`, `openrouter/free`, `openrouter/pareto-code`, `switchpoint/router`
- **MoE (Mixture of Experts)** — models with sparse expert architecture inside one model
- **Regular (dense)** — standard dense models

### Free Models Reference

See **[references/openrouter-free-models.md](references/openrouter-free-models.md)** for the live-verified free-model roster (working/broken table, free-tier limits, live-test procedure, fact-extraction cascade, free-vision models, NVIDIA NIM direct-test rules). **Standing rule: never recommend a free model from the catalog listing alone — a large share of `:free` entries are dead (403/404/provider errors) despite being listed; live-test with a real chat completion first, and re-test before building any cascade.** Vision needs the same live test with a real image plus an answer-accuracy check (fluent hallucinated descriptions happen), and NIM/aggregator IDs must be prefix-stripped with ≥120s timeouts before declaring a provider dead. Also: the website's `max_price=0` filter counts ALL modalities (embedding/TTS/image/reranker, most of them NOT free) — free chat-model counts come only from the API's zero-token-price filter.

See **[references/nous-api-model-comparison.md](references/nous-api-model-comparison.md)** for detailed comparison of Nous Inference API free models (Nemotron-3-Ultra, Step-3.7-Flash, Hy3) with benchmarks, Artificial Analysis index, Design Arena ELO, and recommendations for coding, agentic PC/browser control, and production reliability.

See **[references/cline-api.md](references/cline-api.md)** — **Cline (app.cline.bot) OpenAI-compatible API** — setup, models, Hermes integration, verified config

See **[references/cline-models-verified.md](references/cline-models-verified.md)** — verified working model list with curl test commands (August 2026)
- `references/deepseek-v4-vs-owl-alpha.md` — DeepSeek V4 vs OWL Alpha detailed comparison
- `references/openrouter-deepseek-v4.md` — OpenRouter DeepSeek V4 pricing, specs, reasoning config
- `references/nous-api-model-comparison.md` — Nous Inference API free models benchmark comparison
- `references/token-cost-calculation.md` — How to calculate token costs from state.db
- `references/openrouter-free-models.md` — Maintained list of all free models on OpenRouter/Nous Portal
- `references/vision-model-roster.md` — Cross-provider inventory of vision-capable models: counts + verified lists per configured provider (OmniRoute, TokenHarbor, ClinePass, Mistral, NVIDIA, Xiaomi, OpenCode Go Direct, Antigravity, Google AI Studio, Ollama Cloud, local RPC). Use before picking a vision model.
- `references/artificial-analysis-benchmarks.md` — Bulk-scrape the Artificial Analysis Intelligence Index to rank N models: sitemap slug resolution, parallel curl, score regex, variant/effort naming, gaps for unmeasured models
- `references/opencode-go.md` — OpenCode Go/Go Plus subscription: per-model monthly limits and 5h/week windows, peak/off-peak DeepSeek hours, reading the tabbed docs tables in one DOM call, `x-opencode-session` client requirements, Zen free-tier shape-check gate, and the stealth-model lifecycle (route divergence after delisting, `space-bunny` rename, gateway pricing before reveal, opencode.ai/data as the price source). The Go roster is chat/coding models only — no embedding model, so embedding offload via Go is not an option.
- `references/nous-portal-free-models.md` (in `ai-gateway-ops`) — Nous Portal free-model availability: recommended-models + inference catalog union, probe via OpenRouter (OR key from `.env`/`.env.bak`), inference-api itself needs x402/auth and is not probeable; probe results 2026-10-22: only `poolside/laguna-s-2.1:free` alive.
- `references/model-comparison-2026-08-22.md` — Mistral Large vs Nemotron-3-Ultra vs DeepSeek V4 Flash (OpenRouter, ClinePass, benchmarks, 22.08.2026)
- `references/hermes-context-length-resolution.md` — Why `/model` can display a wrong context (GLM-5.3@NVIDIA showed 202,752 instead of 1M): resolution-chain trace, models.dev slug gaps, `DEFAULT_CONTEXT_LENGTHS` fix + verification recipe
- `references/iceman-vs-deepseek41-flash-1017.md` — live head-to-head (28.10.2026): iceman-contributor-free (stealth, 262k, $0, trains on your data, TTFT 15–23 s) vs deepseek-v4.1-flash-1017 (1M, 157–185 tok/s, empty-content trap when `max_tokens` runs out during reasoning); both passed the same code/tool/needle suite
- `references/tokenharbor-glm-reasoning.md` — **TokenHarbor aggregator & Zhipu GLM-5.3-Flash**: real reasoning levels (low/medium/high; xhigh/max are Anthropic/OpenAI-only), plan-tier gating (glm-5.3 = Frontier-only 402), revoked-key 401 pattern, how Hermes maps `reasoning_effort` per custom provider (source-verified), verification playbook
- `references/tokenharbor-usage-limits.md` — **TH usage/allowance visibility**: NO public usage/limits API (endpoint probe table), exact remaining allowance only in Dashboard→Billing, OmniRoute can't see TH quota, local spend accounting from OmniRoute SQLite (`usage_history`; provider logs under canonical `openai-compatible-chat-<uuid>` id, not the `th` prefix), $ estimation from prices scraped off `/models`, Pass structure (4-week cycle = 4×7-day windows, no rollover). Script: `scripts/tokenharbor_usage.py` (deployed at `~/.hermes/scripts/tokenharbor_usage.py`).

## Telegram Per-Session Model & Reasoning Overrides

### Critical: `/model` and `/reasoning` are session-scoped by default

When the user switches model or reasoning in a Telegram DM topic, **it only affects that specific session** (identified by `chat_id + thread_id`). Other sessions are NOT affected.

**Per-session model overrides** are stored in `_session_model_overrides: Dict[str, Dict[str, str]]` in `gateway/run.py`:
- Key: `session_key` (derived from `chat_id + thread_id`)
- Value: `{model, provider, api_key, base_url, api_mode}`

**Per-session reasoning overrides** are stored in `_session_reasoning_overrides: Dict[str, Dict[str, Any]]`:
- Key: `session_key`
- Value: parsed reasoning config dict (e.g., `{"enabled": True, "effort": "high"}`)

This means:
- **Topic 1** can run OWL Alpha with reasoning=off
- **Topic 2** can run DeepSeek V4 Flash with reasoning=high  
- **Topic 3** can run DeepSeek V4 Pro with reasoning=xhigh
- All simultaneously, without interfering with each other

### The `--global` flag

Add `--global` to persist the change to `config.yaml` for ALL sessions:

```
/model deepseek/deepseek-v4-flash --global     # Persist globally
/reasoning high --global                       # Persist globally
/reasoning off --global                        # Disable for all
```

Without `--global`, changes are **session-scoped only** (default behavior).

### Switching the CURRENT session's model from inside the agent

`/model` is a user command — the agent cannot run it for the chat it is
answering. When asked to switch THIS chat to another model/provider:

1. Set the global default: `hermes config set model.default <model>` and
   `hermes config set model.provider <custom:<slug>`. This only binds
   NEW sessions — the live session keeps its own override.
2. The live session's routing lives in `state.db` → `sessions.model_config`
   (`gateway_runtime.provider` / `base_url` / `api_mode`); a direct UPDATE of
   `sessions.model` + `model_config` for the current session id makes the
   switch visible on the next turn. The gateway's in-memory
   `_session_model_overrides[session_key]` wins over BOTH, so a stale override
   can silently pin the old model — if the next reply is still on the old
   model, the override is the cause, not the config.
3. **Prove the route, don't trust the config**: after the switch, the
   verification is a real call whose billing record shows the intended base
   URL — `state.db` → `session_model_usage.billing_base_url` must equal the
   provider's `base_url` (e.g. `https://opencode.ai/zen/go/v1/` when the point
   was to bypass a local router at `localhost:20128`). A correct `model.default`
   proves nothing on its own.

### Resolution order (from `run_agent.py`)

The gateway resolves model and reasoning per request:
1. Check `_session_model_overrides[session_key]` → if set, use session override
2. Fall back to global config from `model_switch._resolve_gateway_model()`
3. Check `_session_reasoning_overrides[session_key]` → if set, use session override
4. Fall back to global `_reasoning_config`

This is implemented in:
- `_resolve_session_model()` — model resolution
- `_resolve_session_reasoning_config()` — reasoning resolution

## Telegram Reactions (Bot → User)

Hermes **sets** reactions on Telegram messages via `set_message_reaction`:
- 👀 — while processing (on `on_processing_start`)
- 👍 — on success (`ProcessingOutcome.SUCCESS`)
- 👎 — on failure

Controlled by `TELEGRAM_REACTIONS=true` env var (default: false).

**Hermes does NOT read incoming user reactions.** Despite `allowed_updates=Update.ALL_TYPES` being set in Telegram polling (which includes `message_reaction` updates), there is **no handler** for `MessageReactionUpdated` events. User reactions on bot messages are silently ignored.

This is a potential feature gap — if the user wants the bot to react to their emoji responses, a handler would need to be added to `gateway/platforms/telegram.py`.

# Hermes Context-Length Resolution — Why `/model` Can Display a Wrong Context

Case study (2026-09-16): `z-ai/glm-5.3` via custom provider NVIDIA
(`https://integrate.api.nvidia.com/v1`) displayed
"Context: 202,752 tokens" after a `/model` switch. The model's real window
is 1M (confirmed by the user: "глм53 контекст же миллион — это общеизвестно").
The user was right; the display was wrong. Root cause, fix, verification.

## When this matters

If the user challenges a value **Hermes itself displayed** (context, max
output, pricing), do NOT defend the display — trace the resolution chain.
The number shown after `/model` comes from
`hermes_cli/model_switch.py::resolve_display_context_length` →
`agent/model_metadata.py::get_model_context_length`, a multi-step chain where
any missing/stale entry silently downgrades to a legacy fallback. A wrong
display almost always means a stale hardcoded catalog entry or a registry gap,
NOT a provider-enforced limit.

## Resolution chain (get_model_context_length, in order)

0. Explicit `model.context_length` config override (config.yaml / custom_providers
   per-model `context_length`) — user knows best, wins over everything.
0b. `custom_providers[i].models.<id>.context_length` (matched by normalized base_url).
1. Persistent cache `~/.hermes/context_length_cache.yaml` (key: `model@base_url`).
   Stale values stick forever — invalidation guards exist ONLY for specific
   families (Kimi ≤32k, MiniMax-M3 ≤204,800, Grok-4.3 ≤256k, Bedrock, Nous).
   **No GLM guard** — check this file first when debugging.
1b. Bedrock static table.
2. Custom-endpoint `/v1/models` probe (custom providers whose host is not a
   known provider). **NVIDIA's `/v1/models` returns only
   `{id, object, created, owned_by}` — NO context_length field at all**, so
   this probe yields nothing for integrate.api.nvidia.com.
4. Anthropic /v1/models.
5. Provider-aware lookups; for custom providers the host is mapped via
   `_URL_TO_PROVIDER` → `agent/models_dev.py::lookup_models_dev_context`:
   - `integrate.api.nvidia.com` → provider "nvidia" → models.dev provider id
     "nvidia".
   - **models.dev nvidia provider (2026-09-16): has `z-ai/glm-5.2` (1M) and
     `z-ai/glm-5.3-flash` (1M) but NOT `z-ai/glm-5.3`** → lookup misses.
6. OpenRouter live metadata (provider-unaware, only when provider unknown).
8. Hardcoded `DEFAULT_CONTEXT_LENGTHS` (agent/model_metadata.py), **longest-key-first
   substring match** (`key in model_id`). GLM entries: `"glm-5.2": 1_048_576`,
   `"glm": 202752`. `glm-5.3` had no specific key → generic `"glm"` catch-all
   fired → 202,752 (legacy GLM-5/5.1 ≈ 200K value). **This was the bug.**
9. Default fallback 256K.

## models.dev data structure quirk

Per-model limits are NESTED in `limit: {context, output}` — a flat top-level
`context_length` key returns None for these entries:

```bash
curl -s https://models.dev/api.json | python3 -c "
import json,sys
md=json.load(sys.stdin)
for pid in ('zai','nvidia'):
    for mid,m in (md.get(pid,{}).get('models') or {}).items():
        if 'glm' in mid.lower():
            print(pid, mid, '->', (m.get('limit') or {}))
"
# zai glm-5.3 -> {'context': 1000000, 'output': 131072}   (zai provider has it)
# nvidia z-ai/glm-5.2 -> {'context': 1000000, ...}        (nvidia provider lacks 5.3)
```

The same model can exist under multiple models.dev providers with different
slugs — a missing slug under the hosting provider (nvidia) while the vendor
provider (zai) has it means step 5 misses even though the data exists.

## Fix applied

Added to `DEFAULT_CONTEXT_LENGTHS` (agent/model_metadata.py):

```python
"glm-5.3": 1_048_576,   # before "glm-5.2"/"glm" — longest-key-first wins
"glm-5.2": 1_048_576,
"glm": 202752,
```

Substring rule: a key wins if it appears inside the model id, longest keys
first — `z-ai/glm-5.3` contains `glm-5.3` → 1M; `glm-5.1`/`glm-5` still fall
to `"glm"` → 202,752 (correct, those are ~200K models).

## Verification recipe

1. Direct resolver call with the exact switch-time args:

```bash
PYTHONPATH=~/.hermes/hermes-agent <python> -c "
from agent.model_metadata import get_model_context_length
print(get_model_context_length('z-ai/glm-5.3',
    base_url='https://integrate.api.nvidia.com/v1',
    api_key='<nvapi key>', provider='custom:nvidia'))   # -> 1048576
print(get_model_context_length('glm-5.1', provider='custom:nvidia', base_url=''))  # -> 202752
"
```

2. Test suite (hermes venv ships without pytest — build a scratch uv venv):

```bash
uv venv /tmp/hermes-test-venv --python 3.11
uv pip install --python /tmp/hermes-test-venv/bin/python pytest pyyaml requests aiohttp httpx
cd ~/.hermes/hermes-agent
PYTHONPATH=$PWD /tmp/hermes-test-venv/bin/python -m pytest \
  tests/agent/test_model_metadata.py \
  tests/hermes_cli/test_model_switch_context_display.py \
  tests/hermes_cli/test_user_providers_model_switch.py \
  -q -o 'addopts=' -p no:cacheprovider
# 182 passed. `-o addopts=` clears pyproject's -n xdist default (not installed).
```

3. Regression control: older family members (`glm-5`, `glm-5.1`) MUST stay at
   their legacy value — a too-broad key (e.g. changing `"glm"` itself) would
   wrongly upgrade them.

## Qwen3-Flash case (2026-09-18): `qwen3.7-flash` via TokenHarbor showed 131,072 instead of 1M

The same mechanism: the resolution chain landed on the hardcoded fallback `"qwen": 131072`
because no specific key for `qwen3.7-flash` existed in `DEFAULT_CONTEXT_LENGTHS`.
Fix: added `"qwen3.7-flash": 1_000_000, "qwen3.6-flash": 1_000_000` before the `"qwen": 131072` catch-all
in `agent/model_metadata.py`. Longest-key-first substring matching ensures the precise slug wins.

## General pitfall: new flash models get downgraded every cycle

Every time a new "-flash" variant is released (DeepSeek V4 Flash, Qwen 3.x Flash, etc.),
it lands in `DEFAULT_CONTEXT_LENGTHS` without a specific entry and silently falls through to the
family catch-all (`"deepseek": 128000`, `"qwen": 131072`, etc.). The real window is often 1M.
**When the user reports a context value that looks like a legacy fallback rather than the model's known spec — suspect a missing DEFAULT_CONTEXT_LENGTHS entry.** Search the dict for the exact model id substring; if absent, the display is wrong. Always verify against OpenRouter `/v1/models` or official docs before accepting the displayed number.

## Pitfalls

- **Running gateway keeps old code** — a patched resolver only affects new
  processes; live sessions keep compressing against the old limit until
  `/restart`.
- **`hermes update` can stash local edits** (git-installed repo) — re-check
  the catalog entry after updates, or upstream the patch to
  NousResearch/hermes-agent so it survives.
- NVIDIA API gives no context metadata anywhere (`/v1/models` has no
  context_length field) — for NVIDIA-hosted models the hardcoded catalog or
  models.dev is the ONLY source; if both lack the slug, the display silently
  falls to a family catch-all.
- Persistent cache (step 1) can freeze a wrong value learned earlier — delete
  the offending `model@base_url` line from `~/.hermes/context_length_cache.yaml`
  rather than fighting the cache.
